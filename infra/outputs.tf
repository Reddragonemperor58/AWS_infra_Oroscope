output "aurora_cluster_arn" {
  description = "ARN of the Aurora cluster, needed for Data API calls"
  value       = aws_rds_cluster.aurora_db.arn
}

output "aurora_secret_arn" {
  description = "ARN of the auto-generated master user secret"
  value       = aws_rds_cluster.aurora_db.master_user_secret[0].secret_arn
}

output "cognito_user_pool_id" {
  description = "The ID of the Cognito User Pool"
  value       = aws_cognito_user_pool.user_pool.id
}

output "cognito_app_client_id" {
  description = "The ID of the Cognito App client"
  value       = aws_cognito_user_pool_client.userpool_client.id
}