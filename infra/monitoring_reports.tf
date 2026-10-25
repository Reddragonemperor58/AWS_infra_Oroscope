# Emails the alert address when a doctor files a "Report a problem". The API prints
# "PROBLEM_REPORT id=... doctor=..." (never the message text); this filter counts those lines.
resource "aws_cloudwatch_log_metric_filter" "problem_reports" {
  name           = "${local.name_prefix}-problem-reports"
  log_group_name = aws_cloudwatch_log_group.fastapi.name
  pattern        = "PROBLEM_REPORT"

  metric_transformation {
    name          = "ProblemReports"
    namespace     = local.name_prefix
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_metric_alarm" "problem_reports" {
  alarm_name          = "${local.name_prefix}-problem-report"
  alarm_description   = "A doctor sent a problem report from the app. Read it with the SQL in the runbook (Problem reports)."
  namespace           = local.name_prefix
  metric_name         = "ProblemReports"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn] # no ok_actions: the "back to OK" mail is noise here
  tags                = local.common_tags

  depends_on = [aws_cloudwatch_log_metric_filter.problem_reports]
}
