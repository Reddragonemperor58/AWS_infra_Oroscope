# Static frontend: private S3 bucket served through CloudFront (origin access control).
# ADR 0013. Reuses data.aws_caller_identity.images from s3.tf for the account id.

locals {
  frontend_origin = "https://${aws_cloudfront_distribution.frontend.domain_name}"

  mime_types = {
    html = "text/html; charset=utf-8"
    js   = "application/javascript; charset=utf-8"
    css  = "text/css; charset=utf-8"
    json = "application/json; charset=utf-8"
    svg  = "image/svg+xml"
    ico  = "image/x-icon"
    png  = "image/png"
  }
}

resource "aws_s3_bucket" "frontend" {
  bucket = "${local.name_prefix}-frontend-${data.aws_caller_identity.images.account_id}"
  tags   = local.common_tags
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket                  = aws_s3_bucket.frontend.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "${local.name_prefix}-frontend-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# Security headers. connect-src uses a wildcard for the API host on purpose: naming the exact API
# here would make CloudFront depend on the API while the API's CORS depends on CloudFront (cycle).
resource "aws_cloudfront_response_headers_policy" "frontend" {
  name = "${local.name_prefix}-frontend-security-headers"

  security_headers_config {
    content_security_policy {
      override = true
      content_security_policy = join("; ", [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' blob: data:",
        "connect-src 'self' https://cognito-idp.ap-south-2.amazonaws.com https://*.execute-api.ap-south-2.amazonaws.com https://s3.ap-south-2.amazonaws.com",
        "object-src 'none'",
        "base-uri 'none'",
        "frame-ancestors 'none'",
        "form-action 'self'",
      ])
    }
    strict_transport_security {
      override                   = true
      access_control_max_age_sec = 31536000
      include_subdomains         = true
    }
    content_type_options {
      override = true
    }
    frame_options {
      override     = true
      frame_option = "DENY"
    }
    referrer_policy {
      override        = true
      referrer_policy = "no-referrer"
    }
  }
}

resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  default_root_object = "index.html"
  price_class         = "PriceClass_200" # includes Asia (India); PriceClass_100 does not
  comment             = "${local.name_prefix} frontend"

  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "frontend-s3"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  default_cache_behavior {
    target_origin_id       = "frontend-s3"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true
    # Managed policy "CachingDisabled": during the prototype every deploy is visible immediately.
    cache_policy_id            = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
    response_headers_policy_id = aws_cloudfront_response_headers_policy.frontend.id
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = local.common_tags
}

# Only this CloudFront distribution may read the bucket.
resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowCloudFrontRead"
      Effect    = "Allow"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.frontend.arn}/*"
      Condition = {
        StringEquals = { "AWS:SourceArn" = aws_cloudfront_distribution.frontend.arn }
      }
    }]
  })
}

# Everything under ../frontend is published as-is.
resource "aws_s3_object" "frontend" {
  for_each = fileset("${path.module}/../frontend", "**")

  bucket        = aws_s3_bucket.frontend.id
  key           = each.value
  source        = "${path.module}/../frontend/${each.value}"
  etag          = filemd5("${path.module}/../frontend/${each.value}")
  content_type  = lookup(local.mime_types, reverse(split(".", each.value))[0], "application/octet-stream")
  cache_control = "no-cache"
}

# Runtime config generated from live resources (never hand-edited, no secrets: all public identifiers).
resource "aws_s3_object" "frontend_config" {
  bucket        = aws_s3_bucket.frontend.id
  key           = "config.js"
  content_type  = "application/javascript; charset=utf-8"
  cache_control = "no-cache"
  content = "window.OROSCOPE_CONFIG = ${jsonencode({
    apiUrl     = trimsuffix(aws_apigatewayv2_stage.default.invoke_url, "/")
    region     = "ap-south-2"
    userPoolId = aws_cognito_user_pool.user_pool.id
    clientId   = aws_cognito_user_pool_client.userpool_client.id
  })};\n"
}

# The browser POSTs images straight to S3 (presigned POST), so the images bucket must allow
# cross-origin POST from the frontend, and only from it.
resource "aws_s3_bucket_cors_configuration" "images" {
  bucket = aws_s3_bucket.images.id
  cors_rule {
    allowed_methods = ["POST"]
    allowed_origins = [local.frontend_origin]
    allowed_headers = ["*"]
    max_age_seconds = 3000
  }
}

output "frontend_url" {
  value = local.frontend_origin
}
