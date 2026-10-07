# 05 – DynamoDB & RDS – Database Services

Two managed databases for two different jobs. DynamoDB is a serverless key-value/document (NoSQL) store you query by key; RDS is a managed relational (SQL) database engine you query with SQL. Most real systems use both: RDS for the transactional core, DynamoDB for high-volume simple lookups (sessions, carts, counters, Terraform state locks).

---

## DynamoDB

### NoSQL
No fixed schema, no joins, no SQL. You model data around *access patterns* ("get a user by id", "list a user's orders newest first") and the database gives you single-digit-millisecond reads and writes at any scale, with no servers, patches or capacity planning (on-demand mode) and automatic replication across 3 AZs. Trade-off: ad-hoc queries that are not by key need a secondary index or a full table scan.

### Tables
The top-level object, created per region with a name, a primary key definition, and a capacity mode:
- **On-demand**: pay per request, scales instantly – default for new/unpredictable workloads.
- **Provisioned**: fixed read/write capacity units (RCU/WCU), cheaper for steady traffic, with auto scaling.

Table-level features: TTL (auto-expire items), point-in-time recovery (35 days), streams (change feed → Lambda), global tables (multi-region active-active), encryption with KMS by default.

```hcl
resource "aws_dynamodb_table" "orders" {
  name         = "orders"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "customer_id"      # partition key
  range_key    = "order_ts"         # sort key
  attribute { name = "customer_id"; type = "S" }
  attribute { name = "order_ts";    type = "S" }
  ttl { attribute_name = "expires_at"; enabled = true }
}
```

### Items
An item is one record (a row), up to **400 KB**, stored as a map of attributes. Items in the same table can have completely different attributes; only the key attributes are mandatory.

```json
{ "customer_id": "C123", "order_ts": "2026-10-07T15:30:00Z",
  "status": "PAID", "total": 1499.00, "lines": [{"sku": "A1", "qty": 2}] }
```

### Attributes
Name/value pairs inside an item. Types: scalar (`S` string, `N` number, `B` binary, `BOOL`, `NULL`), document (`L` list, `M` map), set (`SS`, `NS`, `BS`). Only key and index attributes are declared in the table definition; everything else is free-form. Reads can be eventually consistent (default, cheaper) or strongly consistent.

### Partition key
The attribute whose hashed value decides **which physical partition** stores the item. Every `GetItem`/`PutItem` must supply it. Choose something with many distinct, evenly accessed values (user id, order id, device id); a low-cardinality key (`country`) creates a *hot partition* and throttling.

- Partition key alone = simple primary key: one item per key value.

### Sort key
Optional second key attribute. Items with the same partition key are stored together, **ordered by the sort key**, which enables `Query` operations like "all orders for customer C123 between two dates" (`begins_with`, `between`, `<`, `>`), newest-first with `ScanIndexForward=false`, and the single-table pattern of composite keys such as `ORDER#2026-10-07#A17`.

- Partition key + sort key = composite primary key: the pair must be unique.
- **Global Secondary Index (GSI)**: a different partition/sort key over the same items (query orders by `status`). **Local Secondary Index (LSI)**: same partition key, different sort key, must be created with the table.

### Use cases
- Session stores, shopping carts, user profiles, feature flags.
- High-write event ingestion (IoT telemetry, clickstreams) with TTL for expiry.
- Leaderboards, counters, idempotency keys, rate limiting.
- Serverless backends (API Gateway + Lambda + DynamoDB).
- **Terraform state locking** (`dynamodb_table` in the S3 backend) – the one almost every DevOps team touches.
- Not for: complex joins/reporting, multi-item transactions beyond 100 items, large blobs (put those in S3 and store the key).

---

## RDS (Relational Database Service)

### Relational database
Tables with fixed columns, primary/foreign keys, joins, transactions (ACID) and SQL. RDS runs a *real* database engine on EC2-like infrastructure that AWS manages for you: provisioning, OS and engine patching, automated backups, failover, monitoring. You still own the schema, queries, indexes and parameter tuning; you do **not** get SSH access to the host.

### Supported engines
| Engine | Notes |
|---|---|
| **PostgreSQL** | most popular for new apps; extensions (PostGIS, pgvector) |
| **MySQL** | classic LAMP/WordPress |
| **MariaDB** | MySQL fork |
| **Oracle** | bring-your-own or included licence |
| **SQL Server** | Express/Web/Standard/Enterprise editions |
| **Db2** | IBM |
| **Aurora** (MySQL/PostgreSQL compatible) | AWS's own storage layer, 6 copies across 3 AZs, up to 15 read replicas, Serverless v2 autoscaling, faster failover |

### DB instances
The managed server: instance class (`db.t3.micro` free tier, `db.r6g.large` memory optimised…), storage type (gp3 / io1, 20 GB–64 TB, autoscaling), engine version, parameter group (engine config), option group, a **DB subnet group** (which private subnets it can live in), security groups, and a maintenance window. Each instance has an endpoint like `yatri-db.cxyz.ap-south-1.rds.amazonaws.com:5432`.

```hcl
resource "aws_db_instance" "postgres" {
  identifier             = "session18-postgres"
  engine                 = "postgres"
  engine_version         = "16"
  instance_class         = "db.t3.micro"
  allocated_storage      = 20
  db_name                = "yatri"
  username               = "yatri_admin"
  password               = var.db_password            # from a secret, never in Git
  db_subnet_group_name   = aws_db_subnet_group.private.name
  vpc_security_group_ids = [aws_security_group.db.id]
  multi_az               = true
  backup_retention_period = 7
  storage_encrypted      = true
  skip_final_snapshot    = false
  deletion_protection    = true
}
```

### Security
- **Network**: put the instance in **private subnets** (`publicly_accessible = false`); the DB security group allows the DB port only from the app's security group.
- **Encryption at rest** with KMS (must be enabled at creation; snapshots inherit it); **in transit** with TLS (`rds.force_ssl=1` parameter for PostgreSQL).
- **Credentials**: master password in **Secrets Manager** with automatic rotation, or **IAM database authentication** (short-lived tokens instead of passwords). The Session 12 lesson applies: never bake the password into a manifest or a Secret built with `echo` without `-n`.
- **IAM** controls who can create/modify/delete instances and snapshots; the engine's own GRANTs control what SQL users can do.
- Auditing: CloudTrail for API calls, engine logs (slow query, audit) to CloudWatch Logs, Enhanced Monitoring and Performance Insights.

### Backups
- **Automated backups**: daily snapshot + transaction logs, retention 0–35 days, enable **point-in-time recovery** to any second in the window. Taken from the standby in Multi-AZ, so no I/O pause.
- **Manual snapshots**: kept until you delete them; copy to another region/account for DR; a *final snapshot* on deletion unless `skip_final_snapshot`.
- Restores always create a **new** instance (new endpoint) – update the app config or use a CNAME.
- Aurora adds continuous backup to S3 and *backtrack* (rewind in place).

### Multi-AZ
High availability, not scaling. AWS keeps a **synchronous standby replica in a second AZ**. On instance failure, AZ outage, or patching, RDS fails over automatically (typically 60–120 s; Aurora ~30 s) and the **same DNS endpoint** now points to the standby. The standby cannot serve reads (except with *Multi-AZ DB cluster* deployments, which have 2 readable standbys). Doubles the instance cost; mandatory for production.

### Read replicas
Scaling for read-heavy workloads. **Asynchronous** copies of the primary (same region, cross-region, or cross-account), each with its own endpoint; the app sends `SELECT`s to replicas and writes to the primary. Replication lag is usually sub-second but not zero. A replica can be **promoted** to a standalone instance (manual DR, or splitting a workload). Up to 15 for Aurora/MySQL/PostgreSQL. Replicas can themselves be Multi-AZ.

```text
app writes ──▶ primary (AZ a) ══sync══▶ standby (AZ b)   [Multi-AZ, failover]
app reads  ──▶ read replica 1 (AZ c) ◀──async──┘
           ──▶ read replica 2 (other region)      [DR / local reads]
```

### Use cases
- The system of record for web apps: users, orders, payments, anything that needs joins and transactions (the Session 21 TaskBoard backend uses PostgreSQL this way).
- Lift-and-shift of on-prem Oracle/SQL Server workloads.
- WordPress/Drupal/Django/Rails stacks (MySQL/PostgreSQL).
- Analytics copies via read replicas so BI queries do not slow production.
- Aurora Serverless v2 for spiky or dev/test workloads that should scale to near zero.

---

## DynamoDB vs RDS – quick chooser

| Question | DynamoDB | RDS |
|---|---|---|
| Data model | key-value / document, schema-less | relational, fixed schema |
| Query style | by key, GSIs; no joins | SQL, joins, aggregations |
| Scaling | automatic, horizontal, practically unlimited | vertical (bigger instance) + read replicas |
| Ops | none (serverless) | managed, but you pick instance/storage/versions |
| Latency | single-digit ms at any size | depends on instance and query |
| Consistency | eventual by default, strong on request, transactions limited | full ACID |
| Pricing | per request / per capacity unit + storage | per instance-hour + storage + IOPS |
| Typical | sessions, carts, IoT, Terraform locks | orders, accounting, reporting, legacy apps |
