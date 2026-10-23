# Monitoring: alarms that email you when something breaks, plus log retention.
# Free-tier friendly: the first 10 CloudWatch alarms and 1,000 SNS emails a month cost nothing.

variable "log_retention_days" {
  description = "Days to keep Lambda logs. Logs can contain patient ids and search text, so do not keep them forever. 30 is a placeholder until the retention policy is decided."
  type        = number
  default     = 30
}

variable "api_5xx_threshold" {
  description = "Alarm when API Gateway returns this many 5xx responses in 5 minutes. One cold start returns several 503s while the database wakes up, so keep this well above that."
  type        = number
  default     = 20
}

# ---------- Where alarms send email ----------
resource "aws_sns_topic" "alerts" {
  name = "${local.name_prefix}-alerts"
  tags = local.common_tags
}

# After the first apply AWS emails a "Confirm subscription" link. Alarms stay silent until you click it.
resource "aws_sns_topic_subscription" "alerts_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# ---------- Log retention ----------
# Lambda created this log group by itself the first time it ran, so Terraform adopts it
# instead of creating it. The import block is idempotent: once adopted it does nothing.
import {
  to = aws_cloudwatch_log_group.fastapi
  id = "/aws/lambda/${local.name_prefix}-fastapi"
}

resource "aws_cloudwatch_log_group" "fastapi" {
  name              = "/aws/lambda/${aws_lambda_function.fastapi_backend.function_name}"
  retention_in_days = var.log_retention_days
  tags              = local.common_tags
}

# ---------- Count unhandled exceptions from the logs ----------
# Mangum turns an unhandled FastAPI exception into an HTTP 500, which Lambda does NOT count as a
# function error. A Python traceback in the log is the reliable signal. The expected "database is
# resuming" case is handled in code (a 503 without a traceback), so it does not trigger this.
resource "aws_cloudwatch_log_metric_filter" "unhandled_exceptions" {
  name           = "${local.name_prefix}-unhandled-exceptions"
  log_group_name = aws_cloudwatch_log_group.fastapi.name
  pattern        = "Traceback"

  metric_transformation {
    name          = "UnhandledExceptions"
    namespace     = local.name_prefix
    value         = "1"
    default_value = "0"
  }
}

# ---------- Alarms ----------
resource "aws_cloudwatch_metric_alarm" "unhandled_exceptions" {
  alarm_name          = "${local.name_prefix}-unhandled-exceptions"
  alarm_description   = "The API hit an unhandled exception (a 500). Look at the Lambda log for the traceback."
  namespace           = local.name_prefix
  metric_name         = "UnhandledExceptions"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  tags                = local.common_tags

  depends_on = [aws_cloudwatch_log_metric_filter.unhandled_exceptions]
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${local.name_prefix}-lambda-errors"
  alarm_description   = "The Lambda crashed or timed out (not a normal 4xx/5xx response)."
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.fastapi_backend.function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  tags                = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  alarm_name          = "${local.name_prefix}-lambda-throttles"
  alarm_description   = "Requests were rejected because the account's Lambda concurrency limit was hit."
  namespace           = "AWS/Lambda"
  metric_name         = "Throttles"
  dimensions          = { FunctionName = aws_lambda_function.fastapi_backend.function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  tags                = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "lambda_slow" {
  alarm_name          = "${local.name_prefix}-lambda-near-timeout"
  alarm_description   = "A request took over 25 s; the Lambda timeout is 30 s, so the optical analysis is close to failing."
  namespace           = "AWS/Lambda"
  metric_name         = "Duration"
  dimensions          = { FunctionName = aws_lambda_function.fastapi_backend.function_name }
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 25000
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  tags                = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "${local.name_prefix}-api-5xx"
  alarm_description   = "API Gateway returned many 5xx responses in 5 minutes (a wider outage, for example the database not coming back)."
  namespace           = "AWS/ApiGateway"
  metric_name         = "5xx"
  dimensions          = { ApiId = aws_apigatewayv2_api.main.id }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = var.api_5xx_threshold
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  tags                = local.common_tags
}

output "alerts_topic_arn" {
  value = aws_sns_topic.alerts.arn
}
