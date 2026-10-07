variable "aws_region" {
  type        = string
  description = "AWS region for all resources."
  default     = "ap-south-1"
}

variable "project_name" {
  type        = string
  description = "Prefix used in resource names and tags."
  default     = "taskboard"
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR block of the VPC."
  default     = "10.20.0.0/16"
}

variable "public_subnet_cidr" {
  type        = string
  description = "CIDR block of the public subnet."
  default     = "10.20.1.0/24"
}

variable "instance_type" {
  type        = string
  description = "EC2 instance type for the web server."
  default     = "t3.micro"
}

variable "ssh_allowed_cidr" {
  type        = string
  description = "CIDR allowed to SSH into the instance (use your own IP/32)."
  default     = "0.0.0.0/0"
}

variable "bucket_name" {
  type        = string
  description = "Globally unique name of the S3 bucket for application data."
}
