# Runbook

## Running a Migration

### Apply Migrations
```bash
alembic upgrade head
```
- Applies every migration not yet recorded in `alembic_version`, in order.
- If `upgrade()` fails partway through, `alembic_version` is only updated *after* success — a failure leaves the recorded version unchanged, and (since Postgres DDL is transactional) any partial changes from that migration roll back automatically. It doesn't "revert" anything — it simply never advances past the failed step.

### Roll Back Migration
```bash
alembic downgrade -1
```
- Reverses exactly one migration, running its `downgrade()`.

---

## Querying the Database Directly (Bypassing the App)
```bash
aws rds-data execute-statement \
  --resource-arn "$(terraform output -raw aurora_cluster_arn)" \
  --secret-arn "$(terraform output -raw aurora_secret_arn)" \
  --database "oroscope_aurora" \
  --sql "YOUR SQL HERE" \
  --region ap-south-2
```

---

## Finding a Valid, Current Aurora Engine Version
Never hardcode a version — versions get deprecated for new-cluster creation without warning (going from `13.6` straight to a "not found" on `16.4` is exactly how this bit us).

```bash
aws rds describe-db-engine-versions --engine aurora-postgresql \
  --query "DBEngineVersions[?starts_with(EngineVersion, '17.')].EngineVersion" \
  --output table --region ap-south-2 --no-cli-pager
```

> **Note:** Ignore any version with `-limitless` — that is a separate Aurora product, not a version variant. Avoid the newest major version number too; let it mature first.

---

## AWS CLI Pager
Long CLI output pages by default (`Space` = next page, `q` = quit). Skip it with `--no-cli-pager`, or filter server-side with `--query` using JMESPath:

```bash
aws rds describe-db-engine-versions \
  --engine aurora-postgresql \
  --query "DBEngineVersions[?starts_with(EngineVersion,'17.')]" \
  --no-cli-pager
```

---

## Working Across Two Machines
- `.terraform/`, provider binaries, and `*.tfstate` never travel with git — they are regenerated per machine. Run `terraform init` fresh on a new machine every time.
- Provider binaries are OS-specific — a Linux build won't run on Windows, which is why a stale copied `.terraform/` folder fails; re-init fixes it.
- **Discipline:** `git pull` before editing, `git push` after. State safety is already handled by the S3 backend + native lock regardless of which machine you're on.

---

## Gotchas
- Security group `description` fields (`GroupDescription`) are ASCII-only — em dashes and smart quotes fail creation with `InvalidParameterValue`.
- Postgres `DatabaseName` must be letters, numbers, and underscores only — **no hyphens**.

---

## Checking What Something Actually Cost
Go to: **Console → Billing and Cost Management → Cost Explorer → group by Service**, filtered to the relevant date range. Don't guess — check.