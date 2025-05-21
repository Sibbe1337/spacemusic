variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  # default     = "eu-north-1" # Or set via TF_VAR_aws_region
}

variable "db_password" {
  description = "Master password for RDS"
  type        = string
  sensitive   = true
  # No default, should be provided securely
} 