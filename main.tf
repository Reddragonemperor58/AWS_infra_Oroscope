terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
  
  # --- ADD THIS BACKEND BLOCK ---
  backend "s3" {
    bucket         = "vamsi-terraform-state-20260725"
    key            = "global/s3/terraform.tfstate"
    region         = "ap-south-2"
    use_lockfile   = true
    encrypt        = true
  }
  # ------------------------------
}

provider "aws" {
  region = "ap-south-2"
}

# 1. The S3 Bucket for the state file
resource "aws_s3_bucket" "terraform_state" {
  # Change this name if it's already taken! It must be globally unique.
  bucket = "vamsi-terraform-state-20260725" 
  
  # This protects you from accidentally deleting the bucket later
  lifecycle {
    prevent_destroy = true
  }
}

# Turn on versioning so you can recover corrupted state files
resource "aws_s3_bucket_versioning" "enabled" {
  bucket = aws_s3_bucket.terraform_state.id
  versioning_configuration {
    status = "Enabled"
  }
}
