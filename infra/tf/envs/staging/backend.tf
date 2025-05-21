terraform {
  backend "s3" {
    bucket         = "space-tfstate-staging"
    key            = "envs/staging/terraform.tfstate"
    region         = "eu-north-1"
    dynamodb_table = "space-tf-locks"
    encrypt        = true
  }
} 