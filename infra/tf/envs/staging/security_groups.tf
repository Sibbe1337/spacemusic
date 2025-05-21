resource "aws_security_group" "db" {
  name        = "space-staging-db-sg"
  description = "Allow Postgres from VPC internal an private subnets for Staging"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = module.vpc.private_subnets_cidr_blocks
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name    = "space-staging-db-sg"
    Project = "space"
    Env     = "staging"
  }
} 