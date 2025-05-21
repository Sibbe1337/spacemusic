terraform {
  required_version = ">= 1.8.0"
  # Backend configuration will be in backend.tf
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  name    = "space-core-prod" # Added -prod suffix for clarity
  cidr    = "10.20.0.0/16"
  azs     = slice(data.aws_availability_zones.available.names, 0, 3)
  private_subnets = ["10.20.1.0/24", "10.20.2.0/24", "10.20.3.0/24"]
  # public_subnets  = ["10.20.101.0/24", "10.20.102.0/24", "10.20.103.0/24"] # Example if needed
  enable_dns_hostnames = true
  # enable_nat_gateway = true # If private subnets need outbound internet
  # single_nat_gateway = true # For cost saving in dev/staging
}

module "db" {
  source  = "terraform-aws-modules/rds/aws"
  identifier        = "space-prod-db"

  engine            = "postgres"
  engine_version    = "16.1"
  instance_class    = "db.m6g.large" # Consider smaller for staging/dev
  allocated_storage = 50
  storage_encrypted = true
  multi_az          = true # Consider false for staging/dev for cost

  db_name     = "space" # Database name
  username = "spaceadmin" # Changed from space to be more specific as admin
  password = var.db_password
  # port     = 5432 # Default

  create_db_option_group    = false # Using default
  create_db_parameter_group = false # Using default
  # db_parameter_group_name = aws_db_parameter_group.postgres16.name # Example for custom params
  
  vpc_security_group_ids = [aws_security_group.db.id]
  subnet_ids             = module.vpc.private_subnets

  # Backup and Maintenance
  backup_retention_period = 7 # Days, adjust as needed
  # backup_window           = "03:00-04:00" # UTC
  # maintenance_window      = "Mon:04:00-Mon:05:00" # UTC

  # Logging - enable as needed
  # enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  tags = {
    Project = "space"
    Env     = "prod"
    Service = "database"
  }
} 