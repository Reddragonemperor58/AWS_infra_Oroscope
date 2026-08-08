# Runbook

## Running a migration
alembic upgrade head
- Applies every migration not yet recorded in `alembic_version`, in order.
- If `upgrade()` fails partway through, `alembic_version` only updates after success —
  a failure leaves the recorded version unchanged, and (Postgres DDL being
  transactional) any partial changes from that migration roll back automatically.
  It doesn't "revert" anything — it simply never advances past the failed step.

alembic downgrade -1
- Reverses exactly one migration, running its downgrade().

## Querying the database directly (bypassing the app)
aws rds-data execute-statement \
  --resource-arn "$(terraform output -raw aurora_cluster_arn)" \
  --secret-arn "$(terraform output -raw aurora_secret_arn)" \
  --database "oroscope_aurora" \
  --sql "YOUR SQL HERE" \
  --region ap-south-2

## Finding a valid, current Aurora engine version
Never hardcode one — versions get deprecated for new-cluster creation without
warning (13.6 to a flat "not found" on 16.4 is exactly how this bit us).
aws rds describe-db-engine-versions --engine aurora-postgresql \
  --query "DBEngineVersions[?starts_with(EngineVersion, '17.')].EngineVersion" \
  --output table --region ap-south-2 --no-cli-pager
Ignore any version with "-limitless" — a separate Aurora product, not a version
variant. Avoid the newest major version number too; let it mature first.

## AWS CLI pager
Long output pages by default (space = next page, q = quit). Skip with
--no-cli-pager, or filter server-side with --query using JMESPath, e.g.
--query "DBEngineVersions[?starts_with(EngineVersion,'17.')]".

## Working across two machines
- .terraform/, provider binaries, and *.tfstate never travel with git — regenerated
  per machine. Run `terraform init` fresh on a new machine every time.
- Provider binaries are OS-specific — a Linux build won't run on Windows, which is
  why a stale copied .terraform/ fails; re-init fixes it.
- Discipline: git pull before editing, git push after. State safety is already
  handled by the S3 backend + native lock regardless of which machine you're on.

## Gotchas
- Security group `description` fields are ASCII-only — em dashes/smart quotes fail
  creation with InvalidParameterValue.
- Postgres `DatabaseName` must be letters/numbers/underscores only — no hyphens.

## Checking what something actually cost
Console → Billing and Cost Management → Cost Explorer → group by Service,
filtered to the relevant date range. Don't guess — check.