# 02 – EC2 (Elastic Compute Cloud) – Compute

## What is EC2?
EC2 is AWS's virtual machine service: you rent a VM (an **instance**) in a region/availability zone, pick its CPU/RAM shape, its disk, its network placement and its firewall, and pay per second while it runs. Everything else on AWS that "runs code" (EKS nodes, ECS EC2 launch type, Elastic Beanstalk, even many managed services) is EC2 underneath.

```text
AMI  +  instance type  +  key pair  +  security group  +  subnet  (+ EBS volumes, IAM role, user data)
                                   │
                                   ▼
                              EC2 instance
```

## AMI (Amazon Machine Image)
The template an instance is launched from: OS, pre-installed software and the root volume snapshot.

- AWS-provided: Amazon Linux 2023, Ubuntu 22.04/24.04, Windows Server, …
- Marketplace AMIs (vendor images), community AMIs, and **your own** (`aws ec2 create-image` from a configured instance, or built with Packer).
- AMI IDs are **region specific** (`ami-0c…` in `ap-south-1` is a different ID in `us-east-1`), which is why Terraform uses a `data "aws_ami"` lookup with filters instead of a hard-coded id:

```hcl
data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]
  filter { name = "name"; values = ["al2023-ami-*-x86_64"] }
}
```

## Instance types
`family + generation + size`, e.g. `t3.micro`, `m7i.large`, `c7g.xlarge`.

| Family | Optimised for | Example use |
|---|---|---|
| **t** (t3, t4g) | burstable, cheap | dev boxes, small web apps, this course |
| **m** | general purpose, balanced | app servers |
| **c** | compute (high CPU per GB) | batch, CI runners, game servers |
| **r / x** | memory | databases, caches, Spark |
| **i / d** | local NVMe storage | NoSQL, data warehouses |
| **p / g / inf** | GPU / ML accelerators | training, inference |

Suffixes: `g` = Graviton (ARM, cheaper), `a` = AMD, `i` = Intel, `n` = more network, `d` = local disk. `t3.micro`/`t2.micro` are free-tier eligible (750 h/month for 12 months).

Purchase options: On-Demand (default), Reserved / Savings Plans (1–3 year commitment, up to ~72 % off), Spot (spare capacity, up to 90 % off, can be interrupted with 2 min notice), Dedicated Hosts.

## Key pairs
An SSH key pair for Linux (or the password-decryption key for Windows). AWS stores the **public** key and injects it into the instance at first boot (`~/.ssh/authorized_keys` for the default user: `ec2-user`, `ubuntu`, …). You keep the **private** key (`.pem`); AWS never has it and cannot recover it.

```bash
aws ec2 create-key-pair --key-name session18 --query KeyMaterial --output text > session18.pem
chmod 400 session18.pem
ssh -i session18.pem ubuntu@<public-ip>
```

Modern alternative: **SSM Session Manager** / **EC2 Instance Connect**, no open port 22 and no key files to lose.

## Security Groups
A **stateful virtual firewall attached to the instance's network interface**. Rules are *allow only*; anything not allowed is dropped. Because it is stateful, the reply to an allowed inbound request is automatically allowed out.

| Direction | Protocol | Port | Source/Destination | Meaning |
|---|---|---|---|---|
| Inbound | TCP | 22 | my IP/32 | SSH only from me |
| Inbound | TCP | 80, 443 | 0.0.0.0/0 | public web |
| Inbound | TCP | 5432 | sg-app | DB accepts traffic only from instances in the *app* SG (SG-to-SG reference) |
| Outbound | all | all | 0.0.0.0/0 | default: everything out |

Several SGs can be attached to one instance; rules are unioned. SG = instance level; NACL (see VPC notes) = subnet level and stateless.

## EBS (Elastic Block Store)
Network-attached persistent disks for EC2, living in one AZ.

- Volume types: `gp3` (default SSD, 3000 IOPS baseline, tune IOPS/throughput separately), `gp2` (older), `io2` (provisioned IOPS for databases), `st1`/`sc1` (HDD, throughput/cold).
- The **root volume** comes from the AMI; by default it is deleted on termination (`delete_on_termination = true`), extra data volumes are not.
- **Snapshots** are incremental backups to S3 and can be copied across regions; AMIs are built from snapshots.
- Can be resized while attached (then grow the filesystem), encrypted with KMS, and detached/reattached to another instance *in the same AZ*.
- **Instance store** is the opposite: local NVMe on the host, very fast, wiped on stop/terminate.

## Public vs private IP
- **Private IP** (`10.x.x.x` from the subnet CIDR): always present, stable for the life of the instance, used inside the VPC.
- **Public IP**: assigned from AWS's pool only if the subnet has `map_public_ip_on_launch` (or you ask for it) *and* the subnet routes to an Internet Gateway. **It changes on every stop/start.**
- **Elastic IP**: a public IPv4 you own and can move between instances; stays the same across stop/start (small hourly charge when not attached to a running instance).
- An instance in a private subnet has no public IP and reaches the internet (updates, Docker Hub) through a **NAT Gateway**.
- IPv6 addresses are globally routable and are not NAT-ed.

```text
ap-south-1a
┌─ public subnet 10.0.1.0/24 ────────┐   ┌─ private subnet 10.0.2.0/24 ─┐
│ web  private 10.0.1.12            │   │ db   private 10.0.2.40       │
│      public  13.233.x.x (or EIP)  │   │      no public IP            │
└─────────────┬──────────────────────┘   └──────────────┬───────────────┘
              ▼ Internet Gateway                        ▼ NAT Gateway (in public subnet)
```

## Instance lifecycle
```text
pending ──▶ running ──▶ stopping ──▶ stopped ──▶ (start) ──▶ pending ──▶ running
                 │                                  
                 └──▶ shutting-down ──▶ terminated   (gone; EBS root deleted by default)
```

- **Stop**: no compute charge, EBS kept, private IP kept, public IP released (unless EIP), instance may land on a different host. Instance-store data is lost.
- **Reboot**: same host, same IPs, like an OS restart.
- **Hibernate**: RAM saved to the EBS root; resumes where it left off.
- **Terminate**: permanent. Enable *termination protection* on anything important.
- **User data** runs once at first boot (cloud-init) – perfect for installing nginx/Docker; **metadata** is available at `http://169.254.169.254/latest/meta-data/` (use IMDSv2 tokens).
- Status checks: *system* (AWS hardware/network) and *instance* (OS reachable); CloudWatch alarms can auto-recover or auto-reboot.

## Common use cases
- Web/app servers behind an ALB in an Auto Scaling Group (min/max/desired, health-check based replacement).
- Self-hosted CI runners (GitHub Actions `self-hosted`, Jenkins agents), often Spot.
- Bastion/jump host in a public subnet to reach private resources (or SSM instead).
- Kubernetes worker nodes (EKS managed node groups are ASGs of EC2).
- Batch/HPC, GPU training jobs, game servers, legacy lift-and-shift VMs.
- Learning labs like this course: one `t3.micro`, Docker installed through user data, security group with 22/80.

## Terraform snippet
```hcl
resource "aws_instance" "web" {
  ami                         = data.aws_ami.al2023.id
  instance_type               = "t3.micro"
  subnet_id                   = aws_subnet.public.id
  vpc_security_group_ids      = [aws_security_group.web.id]
  key_name                    = "session18"
  associate_public_ip_address = true
  user_data = <<-EOT
    #!/bin/bash
    dnf install -y nginx && systemctl enable --now nginx
    echo "Hello from Terraform EC2" > /usr/share/nginx/html/index.html
  EOT
  root_block_device { volume_type = "gp3"; volume_size = 8; encrypted = true }
  tags = { Name = "session19-web" }
}
```
