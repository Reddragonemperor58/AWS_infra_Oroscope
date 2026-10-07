resource "aws_rds_cluster" "aurora_db" {
  cluster_identifier          = "${local.name_prefix}-aurora-cluster"
  engine                      = "aurora-postgresql"
  engine_mode                 = "provisioned"
  engine_version              = "17.9"
  database_name               = var.database_name
  manage_master_user_password = true
  master_username             = var.master_username_db
  storage_encrypted           = true
  enable_http_endpoint        = true
  db_subnet_group_name        = aws_db_subnet_group.db_subnet_group.name
  vpc_security_group_ids      = [aws_security_group.db_sg.id]

  serverlessv2_scaling_configuration {
    max_capacity             = 2.0
    min_capacity             = 0.0
    seconds_until_auto_pause = 300
  }

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-aurora-cluster" })
}

resource "aws_rds_cluster_instance" "starter_db" {
  identifier         = "${local.name_prefix}-aurora-instance"
  cluster_identifier = aws_rds_cluster.aurora_db.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.aurora_db.engine
  engine_version     = aws_rds_cluster.aurora_db.engine_version
  tags               = merge(local.common_tags, { Name = "${local.name_prefix}-aurora-instance" })

}