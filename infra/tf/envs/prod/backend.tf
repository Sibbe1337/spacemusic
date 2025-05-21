terraform {
  backend "s3" {
    bucket         = "space-tfstate-prod" # Example bucket name, ensure it's unique
    key            = "envs/prod/terraform.tfstate"
    region         = "eu-north-1" # Specify the region where the S3 bucket and DynamoDB table exist
    dynamodb_table = "space-tf-locks" # Example table name
    encrypt        = true
  }
} 