resource "aws_security_group" "db" {
  name        = "space-prod-db-sg"
  description = "Allow Postgres from VPC internal an private subnets"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    # Restrict to VPC CIDR or specific subnets if possible
    # For simplicity, module.vpc.private_subnets_cidr_blocks can be used if available
    # or define specific security group IDs that can access the DB.
    cidr_blocks = module.vpc.private_subnets_cidr_blocks # More restrictive than full VPC CIDR
    # security_groups = [module.app_sg.id] # Example if app has its own SG
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1" # Allow all outbound
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name    = "space-prod-db-sg"
    Project = "space"
    Env     = "prod"
  }
} 