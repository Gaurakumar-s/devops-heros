provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = "session19-cloud-terraform"
      ManagedBy = "Terraform"
      Owner     = "gaurav"
    }
  }
}
