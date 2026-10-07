# Terraform S3 Demo – Session 18

Create one S3 bucket with Terraform and walk the full workflow: `init → fmt → validate → plan → apply → show → output → destroy`.

## Project structure

```text
terraform-s3-demo/
├── terraform.tf              # required Terraform + provider versions
├── providers.tf              # provider "aws" { region = var.aws_region }
├── variables.tf              # aws_region, bucket_name
├── terraform.tfvars          # my values (region ap-south-1, bucket gaurav-session18-tf-demo)
├── terraform.tfvars.example  # template for others
├── main.tf                   # resource "aws_s3_bucket" "devops553"
├── outputs.tf                # bucket_name, bucket_arn, bucket_region
├── .terraform.lock.hcl       # provider version lock (commit it)
├── .gitignore                # .terraform/, *.tfstate, tfplan
└── README.md
```

## How the files fit together

```text
terraform.tf ──▶ provider plugin (hashicorp/aws ~> 6.0)
providers.tf ──▶ region comes from var.aws_region
variables.tf ──▶ declares inputs ──▶ terraform.tfvars supplies values
main.tf      ──▶ aws_s3_bucket.devops553 { bucket = var.bucket_name, tags }
outputs.tf   ──▶ exposes name / ARN / region after apply
terraform.tfstate ──▶ Terraform's memory of what it created (never edit, never commit)
```

## Environment note
There are no AWS credentials on my laptop for this course, so I ran the identical configuration against a local AWS-compatible mock (`moto_server` listening on port 4566) by exporting:

```bash
export AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test
export AWS_ENDPOINT_URL=http://localhost.localstack.cloud:4566   # resolves to 127.0.0.1
```

The AWS provider honours `AWS_ENDPOINT_URL`, so **no Terraform file changes** were needed; against a real account you simply unset those variables and run `aws configure` (or set `AWS_PROFILE`). Every command, plan and state transition below is real Terraform output.

## Workflow

### 1. `terraform init`
Downloads the AWS provider declared in `terraform.tf` into `.terraform/`, writes `.terraform.lock.hcl`, and sets up the (local) backend.

### 2. `terraform fmt`
Rewrites files into canonical HCL style. `-diff` shows what changed, `-check` is what CI uses to fail on unformatted code.

### 3. `terraform validate`
Checks syntax, references, types and required arguments without contacting AWS. `Success! The configuration is valid.`

![init, fmt, validate](/assets/s18-terraform-01.png)

### 4. `terraform plan -out=tfplan`
Reads the state, refreshes real resources, and prints the diff: `Plan: 1 to add, 0 to change, 0 to destroy.` Saving the plan guarantees `apply` does exactly what was reviewed.

### 5. `terraform apply tfplan`
Creates the bucket: `aws_s3_bucket.devops553: Creation complete after 3s [id=gaurav-session18-tf-demo]` → `Apply complete! Resources: 1 added`.

### 6. `terraform show`
Dumps the state in human-readable form: every attribute Terraform now knows about the bucket (ARN, region, domain names, tags).

### 7. `terraform output`
Prints the values from `outputs.tf`; `terraform output -raw bucket_arn` is handy in scripts.

### 8. `terraform state list`
Lists tracked resources (`aws_s3_bucket.devops553`). A direct `curl` of the S3 endpoint also listed the bucket.

### 9. `terraform destroy -auto-approve`
Deletes everything in the state: `Destroy complete! Resources: 1 destroyed.` `terraform state list` is then empty.

![plan, apply, show, output, destroy](/assets/s18-terraform-02.png)

## Things I noted
- `force_destroy = true` on the bucket lets `destroy` succeed even if objects were uploaded; without it, S3 refuses to delete a non-empty bucket.
- Bucket names are global, so the default `yatri1107` from the course would collide with the instructor's; `terraform.tfvars` overrides it to `gaurav-session18-tf-demo`.
- `*.tfvars` is git-ignored by default because it often holds secrets; here it only holds a region and a name, so `terraform.tfvars` is explicitly un-ignored and committed next to a `.example`.
- The state file contains everything about the resource (including sensitive values for other resource types) – the next step in a team is an S3 backend with versioning and locking, which is exactly what the S3 + DynamoDB notes in `../aws-services/` describe.

## Commands at a glance
```bash
terraform init
terraform fmt -recursive -diff
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
terraform show
terraform output
terraform state list
terraform destroy -auto-approve
```
