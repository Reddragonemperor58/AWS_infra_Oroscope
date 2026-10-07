resource "aws_s3_bucket" "terraform_state" {
  bucket = "vamsi-terraform-state-20260725"

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "enabled" {
  bucket = aws_s3_bucket.terraform_state.id
  versioning_configuration {
    status = "Enabled"
  }
}