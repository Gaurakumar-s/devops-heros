# Terraform – infrastructure for the final project

Provisions the cloud footprint the TaskBoard platform would run on: a VPC with a public subnet, internet gateway and route table, a security group (22/80/443), a `t3.small` EC2 host (nginx bootstrapped by user data; in a real deployment this is where a kubeadm/k3s node or the bastion for an EKS cluster would live) and a private, versioned S3 bucket for build artifacts and backups.

```text
VPC 10.30.0.0/16 ── public subnet 10.30.1.0/24 ── EC2 taskboard-web (SG: 22, 80, 443)
                 └─ IGW + route 0.0.0.0/0
S3 gaurav-taskboard-artifacts (versioned, public access blocked)
```

```bash
terraform init && terraform fmt -check && terraform validate
terraform plan -out=tfplan && terraform apply tfplan
terraform output
terraform destroy -auto-approve
```

Same code base as `session19-cloud-terraform/terraform-project`; run and verified against a local AWS mock because no AWS credentials exist on this machine (see that README for the screenshots and the `AWS_ENDPOINT_URL` note).
