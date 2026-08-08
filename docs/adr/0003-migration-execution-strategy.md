# ADR 0003: Schema Migration Execution Strategy

## Context
The Aurora cluster lives in a private VPC with no Internet Gateway and no NAT Gateway. Alembic migrations require a real database connection (SQLAlchemy/psycopg2 or a compatible dialect), unlike the Data API's stateless HTTPS application queries — raising the question of how to run migrations from a local machine with no network path into the VPC.

## Options Considered
1. **Temporarily allow the local machine's public IP into the DB security group, connect via standard `psycopg2`.**
   Ruled out — physically impossible as designed, not merely undesirable. The cluster has no public IP, `publicly_accessible` was never set to `true`, and there's no Internet Gateway in the VPC. A security group rule only filters traffic that physically arrives; it can't make an unroutable private-subnet address reachable from the public internet. A real fix would require adding an Internet Gateway, a `0.0.0.0/0` route for the database subnets, `publicly_accessible = true`, the IP rule, then tearing all of it back down — a real, if temporary, weakening of a database holding patient data.
2. **AWS CloudShell VPC environment**, attached to the private subnets, running standard `psycopg2` from inside the VPC.
   Ruled out for this VPC specifically — CloudShell VPC environments only get internet access via a NAT Gateway route, which this VPC deliberately doesn't have. Without it, even `pip install psycopg2-binary` fails, and sessions have no persistent storage regardless.
3. **`sqlalchemy-aurora-data-api`** — a community SQLAlchemy dialect translating ORM/Alembic operations into Data API HTTPS calls.
   **Chosen.**

## Decision
Migrations run locally via Alembic using `sqlalchemy-aurora-data-api`, tunneling over the Data API with IAM authentication — the same connection path already proven for application queries.

## Reasoning
Zero new infrastructure, zero new cost, zero temporary weakening of network isolation. Reuses a path already empirically proven against this specific cluster.

## Risk Encountered and Resolved
ENUM types and composite indexes were flagged upfront as the highest-risk DDL for this dialect, and deliberately tested in isolation — a trivial single-table migration first, before the full schema — rather than risked inside one large migration. The isolated test caught a real failure: `type "diagnosis_status" already exists`.

Initially suspected as a Data API wrapper limitation. Investigated directly instead of assumed: querying `information_schema.tables` and `pg_type` after the failure confirmed the transaction had rolled back cleanly. Root cause was a standard, dialect-agnostic SQLAlchemy gotcha — explicitly creating the ENUM with `.create(checkfirst=True)` and also passing that same type into `create_table()`, which independently tries to create it again via its own hook. Fixed with `create_type=False` plus an idempotent `DO $$ ... EXCEPTION WHEN duplicate_object` block. Not a Data API defect — identical over standard `psycopg2`.

## Trade-offs Accepted
Fallback if it ever proves genuinely unworkable: a temporary Session Manager
port-forwarding bastion — a small EC2 instance as a pure network bridge, paired
with three VPC interface endpoints (ssm, ssmmessages, ec2messages) for Session
Manager connectivity itself. Session Manager connectivity alone does not grant
internet access — pip installing psycopg2/alembic/sqlalchemy still requires
reaching PyPI, a non-AWS service unreachable via PrivateLink. To avoid a NAT
Gateway for this too, required Python packages are pre-downloaded locally and
staged in S3 ahead of time, pulled onto the bastion via a free VPC S3 Gateway
endpoint rather than installed live from PyPI. All infrastructure (instance,
interface endpoints, S3 objects) torn down immediately after the migration
session. Not the public-IP or CloudShell paths — both genuinely unworkable
given this VPC's design, detailed earlier in this document.