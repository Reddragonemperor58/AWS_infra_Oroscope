# Optical images uploaded by clinicians (red / blue light photos).
data "aws_caller_identity" "images" {}

resource "aws_s3_bucket" "images" {
  # Account id keeps the globally-unique S3 name collision-free.
  bucket = "${local.name_prefix}-images-${data.aws_caller_identity.images.account_id}"
  tags   = local.common_tags
}

resource "aws_s3_bucket_public_access_block" "images" {
  bucket                  = aws_s3_bucket.images.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "images" {
  bucket = aws_s3_bucket.images.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Cost + privacy: patient images are not kept forever. 30 days is a PLACEHOLDER retention -
# confirm the real retention period with the clinic before real patient data is used.
resource "aws_s3_bucket_lifecycle_configuration" "images" {
  bucket = aws_s3_bucket.images.id
  rule {
    id     = "expire-optical-images"
    status = "Enabled"
    filter {}
    expiration {
      days = 30
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

output "images_bucket_name" {
  value = aws_s3_bucket.images.bucket
}
