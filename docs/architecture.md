# Oroscope Architecture

## Infrastructure Components
1. VPC (Virtual Private Cloud) — 10.0.0.0/16
2. Database — Aurora Serverless v2 cluster (see below)
3. Two private subnets across two Availability Zones (private-subnet-a, private-subnet-b), grouped via the `aws_db_subnet_group` resource and assigned to the database
4. Security group attached to the database

## Database
**Type:** Aurora Serverless v2 — one `aws_rds_cluster` (storage/orchestration) plus one `aws_rds_cluster_instance` (`db.serverless`, the compute actually running queries).

**Version:** PostgreSQL 17.9 — not 16.4, the original choice; see `runbook.md` for why hardcoded engine versions go stale and how to check current ones.

**Scaling configuration:** `min_capacity = 0`, `max_capacity = 2`, `seconds_until_auto_pause = 3600`.

**User credentials:** Managed automatically by AWS Secrets Manager (`manage_master_user_password = true`) — no password ever appears in Terraform files, application code, or terminal history.

**Querying:** Done through the Data API, which uses IAM (SigV4-signed requests) to verify request authenticity.

## Data API
An AWS-managed API for accessing the database. It enables external compute — specifically, a non-VPC-attached Lambda — to query the Aurora database inside the private subnets via HTTPS, without requiring VPC attachment or a NAT Gateway.

1. **Empirically confirmed:** a real query executed successfully via the Data API against this cluster while the database security group had zero ingress rules, proving the connection path doesn't route through the VPC's customer-facing network layer.
2. It uses Secrets Manager-stored credentials to authenticate to the database once the request's IAM identity has been verified — the caller's IAM role needs both `rds-data:ExecuteStatement` (scoped to the cluster ARN) and `secretsmanager:GetSecretValue` (scoped to the secret ARN); the secret value itself is never returned to the caller.
3. The Data API is not free — $0.20-0.70 per million requests depending on region/volume, with 1 million requests/month free for the account's first year. See `cost-notes.md`.

## Compute (Inference)
The ML inference workload runs as an **AWS Lambda function packaged as a container image** (via ECR) — not on Kubernetes/EKS. No persistent worker nodes, no always-on compute, consistent with this architecture's goal of near-zero cost at rest.

## Naming Convention
Format: `{project}-{environment}-{component}`
Tag set applied to every resource: `Environment`, `ManagedBy`, `Project`, `Name`.
Maintained centrally via a `locals` block, so every resource references `local.name_prefix` and `local.common_tags` rather than composing names manually.

## Networking
There is currently no NAT Gateway and no Internet Gateway anywhere in this VPC. Nothing inside the VPC ever needs outbound internet access — the database only responds to inbound Data API queries (security groups are stateful; no egress rules are needed for this to work), and the Lambda that needs to reach S3 or other AWS services is kept entirely outside the VPC, so it never requires a NAT Gateway or a VPC endpoint to reach anything.

Designed so the Stage 3 Lambda will query the database via the Data API without VPC attachment or a NAT Gateway.