resource "aws_cognito_user_pool" "user_pool" {
  name = "${local.name_prefix}-user-pool"

  user_pool_tier = "ESSENTIALS"

  # Fix 1: Must be a list of strings
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  # Enforce Admin-only creation (No public sign-ups)
  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  # Enable MFA (Optional for the user, but supported by the pool)
  mfa_configuration = "OPTIONAL"
  software_token_mfa_configuration {
    enabled = true
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  # Fix 3: Removed password_history_size to prevent Advanced Security billing
  password_policy {
    minimum_length    = 16
    require_symbols   = true
    require_lowercase = true
    require_numbers   = true
    require_uppercase = true
    password_history_size = 5
  }

  # Prevent Terraform from fighting AWS over background schema injections
  lifecycle {
    ignore_changes = [schema]
  }

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-user-pool" })
}

resource "aws_cognito_user_pool_client" "userpool_client" {
  name         = "${local.name_prefix}-user-pool-client"
  user_pool_id = aws_cognito_user_pool.user_pool.id

  # CRITICAL: Browsers cannot securely hold client secrets
  generate_secret = false

  prevent_user_existence_errors = "ENABLED"

  # Fix 2: Allow standard secure browser login (SRP) and token refreshes
  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH"
  ]

  # Your token rotation settings are perfect!
  refresh_token_rotation {
    feature                    = "ENABLED"
    retry_grace_period_seconds = 10
  }
}