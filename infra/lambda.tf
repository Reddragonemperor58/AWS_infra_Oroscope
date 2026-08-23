# 1. IAM Role for the Lambda Function
resource "aws_iam_role" "fastapi_lambda_role" {
  name = "${local.name_prefix}-fastapi-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = local.common_tags
}

# 2. Basic Execution (CloudWatch Logs)
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.fastapi_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# 3. Custom Policy: Allow Lambda to talk to Aurora Data API and Secrets Manager
resource "aws_iam_role_policy" "lambda_aurora_access" {
  name   = "${local.name_prefix}-aurora-access"
  role   = aws_iam_role.fastapi_lambda_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "rds-data:BatchExecuteStatement",
          "rds-data:BeginTransaction",
          "rds-data:CommitTransaction",
          "rds-data:ExecuteStatement",
          "rds-data:RollbackTransaction"
        ]
        Resource = aws_rds_cluster.aurora_db.arn
      },
      {
        Effect = "Allow"
        Action = "secretsmanager:GetSecretValue"
        Resource = aws_rds_cluster.aurora_db.master_user_secret[0].secret_arn
      }
    ]
  })
}

# 4. The actual Lambda Function
resource "aws_lambda_function" "fastapi_backend" {
  function_name    = "${local.name_prefix}-fastapi"
  role             = aws_iam_role.fastapi_lambda_role.arn
  
  handler          = "app.main.handler" 
  runtime          = "python3.13"
  
  filename         = "../services/control-plane/fastapi_backend.zip"
  source_code_hash = filebase64sha256("../services/control-plane/fastapi_backend.zip")
  
  timeout          = 10
  memory_size      = 256

  environment {
    variables = {
      AURORA_CLUSTER_ARN = aws_rds_cluster.aurora_db.arn
      AURORA_SECRET_ARN  = aws_rds_cluster.aurora_db.master_user_secret[0].secret_arn
    }
  }

  tags = local.common_tags
}

output "lambda_function_arn" {
  value = aws_lambda_function.fastapi_backend.arn
}