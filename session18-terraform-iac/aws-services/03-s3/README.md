# 03 – S3 (Simple Storage Service) – Storage

## What is S3?
S3 is AWS's object storage: you upload files (**objects**) into **buckets** and get them back over HTTPS by key. There are no disks to size, no filesystem to mount; capacity is effectively unlimited, durability is designed for 99.999999999 % (11 nines) by replicating every object across at least 3 availability zones, and you pay per GB stored, per request, and per GB transferred out.

It is *not* a filesystem: there are no real directories (the `/` in a key is just a character), objects are immutable (you overwrite, you do not edit), and you cannot run a database on it. It *is* the default place for backups, logs, images, build artifacts, static websites, data lakes and Terraform state.

## Buckets
- A bucket is a container for objects, created in **one region**, with a name that is **globally unique across all AWS accounts** (`gaurav-session18-tf-demo` worked in the demo because nobody else has it).
- Naming: 3–63 chars, lowercase letters, numbers, dots, hyphens; no uppercase, no underscores, must not look like an IP.
- Flat namespace inside; "folders" in the console are just key prefixes (`logs/2026/10/07/app.log`).
- Settings live on the bucket: versioning, encryption default, lifecycle rules, public-access block, policy, logging, replication, Object Lock.
- Soft limit of 100 buckets per account (can be raised); a bucket must be empty to delete it (`force_destroy = true` in Terraform empties it first).

```bash
aws s3 mb s3://gaurav-session18-tf-demo --region ap-south-1
aws s3 ls
```

## Objects
- Object = **key** (the full path-like name) + **data** (0 bytes to 5 TB) + **metadata** (Content-Type, user metadata) + version id + tags.
- Addressed as `s3://bucket/key` or `https://bucket.s3.ap-south-1.amazonaws.com/key`.
- Uploads over 100 MB should use **multipart upload** (the CLI does it automatically); reads support byte-range `GET`s.
- Strong read-after-write consistency since 2020: a `PUT` is immediately visible to the next `GET`/`LIST`.
- Presigned URLs give temporary access to one object without making the bucket public.

```bash
aws s3 cp report.pdf s3://gaurav-session18-tf-demo/reports/report.pdf
aws s3api head-object --bucket gaurav-session18-tf-demo --key reports/report.pdf
aws s3 presign s3://gaurav-session18-tf-demo/reports/report.pdf --expires-in 3600
```

## Storage classes
Same API, different price/availability/retrieval trade-off, chosen per object:

| Class | For | Notes |
|---|---|---|
| **Standard** | hot data, frequent access | default, ms latency, 3+ AZ |
| **Intelligent-Tiering** | unknown/changing patterns | auto-moves between tiers, small monitoring fee |
| **Standard-IA** | infrequent but must be instant | cheaper storage, per-GB retrieval fee, 30-day minimum |
| **One Zone-IA** | re-creatable infrequent data | single AZ, ~20 % cheaper than Standard-IA |
| **Glacier Instant Retrieval** | archives needing ms access quarterly | 90-day minimum |
| **Glacier Flexible Retrieval** | archives, minutes-to-hours retrieval | 90-day minimum |
| **Glacier Deep Archive** | compliance archives, 12 h retrieval | cheapest (~$1/TB-month), 180-day minimum |
| **Express One Zone** | single-digit-ms, high-request workloads | directory buckets |

## Versioning
Turned on per bucket (cannot be turned off again, only suspended). Every overwrite creates a new version; a delete adds a *delete marker* instead of removing data, so accidental deletes and overwrites are recoverable. Required for replication and Object Lock. Costs: every version is billed, so pair it with a lifecycle rule that expires old versions.

```hcl
resource "aws_s3_bucket_versioning" "demo" {
  bucket = aws_s3_bucket.devops553.id
  versioning_configuration { status = "Enabled" }
}
```

## Lifecycle policies
Rules that move or delete objects automatically based on age, prefix, tags or size:

```hcl
resource "aws_s3_bucket_lifecycle_configuration" "demo" {
  bucket = aws_s3_bucket.devops553.id
  rule {
    id     = "logs"
    status = "Enabled"
    filter { prefix = "logs/" }
    transition { days = 30;  storage_class = "STANDARD_IA" }
    transition { days = 90;  storage_class = "GLACIER" }
    expiration { days = 365 }
    noncurrent_version_expiration { noncurrent_days = 30 }
    abort_incomplete_multipart_upload { days_after_initiation = 7 }
  }
}
```

Typical: logs → IA after 30 days → Glacier after 90 → delete after a year; old versions deleted after 30 days; abandoned multipart uploads cleaned up.

## Encryption
- **At rest**: every new object is encrypted by default with **SSE-S3** (AES-256, AWS-managed keys). Options: **SSE-KMS** (your KMS key, per-key audit trail in CloudTrail, can be required by policy), **DSSE-KMS** (double), **SSE-C** (you supply the key per request), or client-side encryption before upload.
- **In transit**: HTTPS. A bucket policy with `"Condition": {"Bool": {"aws:SecureTransport": "false"}}` + `Deny` rejects plain HTTP.

```hcl
resource "aws_s3_bucket_server_side_encryption_configuration" "demo" {
  bucket = aws_s3_bucket.devops553.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.s3.arn
    }
  }
}
```

## Bucket policies
A **resource-based** IAM policy attached to the bucket (JSON, with a `Principal`). It controls who, from which accounts/services/IPs, may do what to the bucket and its objects. Evaluated together with the caller's identity policies; an explicit Deny here beats everything.

Also relevant: **Block Public Access** (account- and bucket-level switches that override any policy that would make data public; keep them on), **ACLs** (legacy, disabled by default on new buckets), **access points**.

Example: allow CloudFront only, deny non-TLS, let another account's role read:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Sid": "DenyInsecureTransport", "Effect": "Deny", "Principal": "*",
      "Action": "s3:*", "Resource": ["arn:aws:s3:::my-bucket", "arn:aws:s3:::my-bucket/*"],
      "Condition": { "Bool": { "aws:SecureTransport": "false" } } },
    { "Sid": "CrossAccountRead", "Effect": "Allow",
      "Principal": { "AWS": "arn:aws:iam::222222222222:role/log-reader" },
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": ["arn:aws:s3:::my-bucket", "arn:aws:s3:::my-bucket/*"] }
  ]
}
```

## Common use cases
- **Static website / SPA hosting** behind CloudFront (`index.html`, React build output).
- **Backups and snapshots**: database dumps, EBS snapshots live on S3, cross-region replication for DR.
- **Logs and audit trails**: ALB/CloudFront access logs, CloudTrail, VPC Flow Logs, then Athena to query them.
- **Build artifacts and container layers**: CI uploads, ECR stores layers on S3.
- **Data lake**: Parquet/CSV under `s3://lake/` queried by Athena, Glue, EMR, Redshift Spectrum.
- **Terraform remote state** (`backend "s3"` with versioning on, plus DynamoDB or S3 native locking) – the natural follow-up to this session's demo.
- **Event-driven pipelines**: `s3:ObjectCreated` → Lambda/SQS/EventBridge (thumbnailing, ETL).
- **Media and user uploads** with presigned URLs so the browser uploads directly.

## What the Session 18 demo actually did
`terraform-s3-demo/` created one bucket with tags, printed its name/ARN/region from `outputs.tf`, and destroyed it again. Everything above (versioning, lifecycle, encryption, policy) attaches to that same `aws_s3_bucket.devops553` resource as separate `aws_s3_bucket_*` resources, which is how the AWS provider v4+ models bucket settings.
