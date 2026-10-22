# Cost guard: emails when real or forecast spend passes a monthly limit.
# The first two AWS Budgets per account are free.
variable "alert_email" {
  description = "Email address that receives AWS Budgets alerts"
  type        = string
}

variable "monthly_budget_usd" {
  description = "Monthly spend limit in USD that triggers alerts"
  type        = string
  default     = "5"
}

resource "aws_budgets_budget" "monthly" {
  name         = "${local.name_prefix}-monthly"
  budget_type  = "COST"
  limit_amount = var.monthly_budget_usd
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
  }
}
