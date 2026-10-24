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


  # --- added: protect patient records ---
  backup_retention_period   = 7    # keep daily backups for a week (was the 1-day minimum)
  deletion_protection       = true # a destroy or console delete fails until this is switched off on purpose
  copy_tags_to_snapshot     = true
  final_snapshot_identifier = "${local.name_prefix}-final-snapshot" # taken automatically if the cluster is ever deleted
  apply_immediately         = true                                  # do not wait for the weekly maintenance window
  # ---------------------------------------


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