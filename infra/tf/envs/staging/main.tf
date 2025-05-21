terraform {
  required_version = ">= 1.8.0"
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
  name    = "space-core-staging" # Changed name for Staging
  cidr    = "10.30.0.0/16"       # Changed CIDR for Staging
  azs     = slice(data.aws_availability_zones.available.names, 0, 2) # Using 2 AZs for staging
  private_subnets = ["10.30.1.0/24", "10.30.2.0/24"]
  enable_dns_hostnames = true
  # Consider NAT Gateway for staging if needed, possibly single for cost saving
  enable_nat_gateway = true
  single_nat_gateway = true 
}

module "db" {
  source  = "terraform-aws-modules/rds/aws"
  identifier        = "space-staging-db"

  engine            = "postgres"
  engine_version    = "16.1"
  instance_class    = var.db_instance_class # Use variable for staging
  allocated_storage = 20 # Smaller storage for staging
  storage_encrypted = true
  multi_az          = var.db_multi_az # Use variable for staging

  db_name  = "space_staging" # Database name for staging
  username = "spaceadmin"
  password = var.db_password
  
  create_db_option_group    = false
  create_db_parameter_group = false
  
  vpc_security_group_ids = [aws_security_group.db.id]
  subnet_ids             = module.vpc.private_subnets

  backup_retention_period = 3 # Shorter retention for staging
  # skip_final_snapshot     = true # Consider for non-prod environments

  tags = {
    Project = "space"
    Env     = "staging"
    Service = "database"
  }
} 