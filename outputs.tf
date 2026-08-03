output "aurora_cluster_arn" {
  description = "ARN of the Aurora cluster, needed for Data API calls"
  value       = aws_rds_cluster.aurora_db.arn
}

output "aurora_secret_arn" {
  description = "ARN of the auto-generated master user secret"
  value       = aws_rds_cluster.aurora_db.master_user_secret[0].secret_arn
}