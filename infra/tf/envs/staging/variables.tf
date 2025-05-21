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

variable "db_instance_class" {
  description = "RDS instance class for staging"
  type        = string
  default     = "db.t3.medium" # Smaller default for staging
}

variable "db_multi_az" {
  description = "Enable Multi-AZ for RDS in staging"
  type        = bool
  default     = false # Disabled for staging by default for cost
} 