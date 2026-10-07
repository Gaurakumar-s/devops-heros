# Reformatted: the original single-line block was invalid HCL ("Invalid single-argument block definition").
terraform {
  required_version = ">= 1.7.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }
}
