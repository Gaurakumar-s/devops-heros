provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = "taskboard-final-project"
      ManagedBy = "Terraform"
      Owner     = "gaurav"
    }
  }
}
