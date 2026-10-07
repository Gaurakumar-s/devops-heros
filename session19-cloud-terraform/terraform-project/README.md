# Session 19 – Cloud & Terraform in Action

End-to-end AWS infrastructure with Terraform: a VPC with a public subnet, an internet gateway and route table, a security group, an EC2 web server that installs nginx through user data, and a private, versioned S3 bucket.

## Architecture

```text
                         Internet
                             │
                     ┌───────┴────────┐
                     │ Internet GW    │  aws_internet_gateway.main
                     └───────┬────────┘
   ┌─────────────────────────┼───────────────────────────────────────┐
   │ VPC 10.20.0.0/16        │                 aws_vpc.main          │
   │                         │                                       │
   │   route table "public"  │  0.0.0.0/0 → igw                      │
   │   aws_route_table.public + association                          │
   │                         │                                       │
   │  ┌──────────────────────┴───────────────────────┐               │
   │  │ public subnet 10.20.1.0/24 (ap-south-1a)      │               │
   │  │ aws_subnet.public  (map_public_ip_on_launch)  │               │
   │  │                                               │               │
   │  │   ┌───────────────────────────────┐           │               │
   │  │   │ EC2 t3.micro  aws_instance.web│ ◀── SG ───┼── 22 (my IP)  │
   │  │   │ Amazon Linux 2 + nginx        │   web     │   80, 443 (*) │
   │  │   │ public IP, 8 GB gp3 encrypted │           │   egress all  │
   │  │   └───────────────────────────────┘           │               │
   │  └───────────────────────────────────────────────┘               │
   └─────────────────────────────────────────────────────────────────┘

                 S3 bucket  aws_s3_bucket.app_data
                 versioning on, public access blocked
```

## Files

| File | Purpose |
|---|---|
| `versions.tf` | required Terraform version and the `hashicorp/aws ~> 6.0` provider |
| `provider.tf` | provider config: region from a variable, `default_tags` applied to every resource |
| `variables.tf` | region, project name, CIDRs, instance type, SSH CIDR, bucket name (with types and descriptions) |
| `terraform.tfvars` | my values; `terraform.tfvars.example` is the template |
| `main.tf` | the 10 resources + the AMI data source |
| `outputs.tf` | VPC id, subnet id, SG id, instance id/IP, website URL, bucket name |
| `.gitignore` | `.terraform/`, state files, plans |

## What the project demonstrates

- **Providers** – `provider "aws"` with `default_tags`, version-pinned in `versions.tf`, locked in `.terraform.lock.hcl`.
- **Variables** – every tunable is a typed `variable` with a description; values come from `terraform.tfvars`.
- **Resources** – `aws_vpc`, `aws_subnet`, `aws_internet_gateway`, `aws_route_table`, `aws_route_table_association`, `aws_security_group`, `aws_instance`, `aws_s3_bucket`, `aws_s3_bucket_versioning`, `aws_s3_bucket_public_access_block` (10 resources, `Plan: 10 to add`).
- **Data source** – `data "aws_ami" "amazon_linux"` looks the AMI up by name instead of hard-coding a region-specific id.
- **Outputs** – the values a human or another module needs after apply (`website_url`, `instance_public_ip`, …).
- **Dependencies** – implicit through references (`aws_subnet.public.id`, `aws_security_group.web.id`, `aws_vpc.main.id`) and one explicit `depends_on` on the instance so the internet route exists before user data runs `yum`. `terraform graph` in the screenshot shows the resulting edges.
- **State** – `terraform.tfstate` created on apply, inspected with `terraform show` / `terraform state list`, emptied by `destroy`.
- **Workflow** – `init → fmt -check → validate → plan -out → apply → output → destroy`.

## Running it

```bash
terraform init
terraform fmt -recursive -check
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
terraform output
terraform state list
terraform destroy -auto-approve
```

### Environment note
No AWS account credentials were available on my laptop, so the run in the screenshots targets a local AWS-compatible mock (`moto_server` on port 4566) via `AWS_ENDPOINT_URL`, which the AWS provider supports natively. The Terraform code is unchanged; against real AWS you unset `AWS_ENDPOINT_URL`, run `aws configure`, set `ssh_allowed_cidr` to your own `/32`, and the same `apply` creates billable resources (the `t3.micro` and 8 GB disk are free-tier eligible; remember `terraform destroy`).

## Screenshots

init, fmt, validate and the plan (10 resources to add):

![terraform init / fmt / validate / plan](/assets/s19-terraform-01.png)

apply, outputs, state list, dependency graph, show, destroy:

![terraform apply / output / state / graph / show / destroy](/assets/s19-terraform-02.png)

## Observations
- The AMI data source resolved to an `amzn2-ami-hvm-*` image; on real AWS this is the newest Amazon Linux 2 image in the region on the day you apply, so `plan` can show an AMI change months later. Pin `most_recent = false` + a specific name if that matters.
- `map_public_ip_on_launch` on the subnet plus the `0.0.0.0/0 → igw` route is what makes the subnet *public*; the instance received `54.x.x.x` and the `website_url` output is built from it.
- The security group opens 22 to `ssh_allowed_cidr`; the default in `terraform.tfvars` is `0.0.0.0/0` for the lab and must be narrowed for anything real.
- Destroy order is the reverse of the dependency graph (instance before subnet before VPC); Terraform works that out from the same references that drove creation.
