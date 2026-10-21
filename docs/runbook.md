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

## AWS CLI Binary Format (Lambda Invoke Gotcha)
AWS CLI v2 defaults to assuming any `--payload` value is already base64-encoded, and rejects a plain JSON file with `Invalid base64`. Either pass the flag explicitly per call:
```bash
aws lambda invoke --function-name <name> --payload file://event.json --cli-binary-format raw-in-base64-out response.json
```
or set it once, permanently, so plain JSON files work by default going forward:
```bash
aws configure set cli_binary_format raw-in-base64-out
```

---

## Testing a Lambda Directly (Bypassing API Gateway)

### Minimal Mangum-Compatible Test Event
Mangum builds its ASGI scope from the full API Gateway v2 event shape. `requestContext.http.sourceIp` is **required unconditionally** — omitting it (along with other fields Mangum reads) throws a raw `KeyError` before your route code ever runs. Use this as the base template, editing `routeKey`/`rawPath`/`http.path`/`http.method` per route:

```json
{
  "version": "2.0",
  "routeKey": "GET /your-route",
  "rawPath": "/your-route",
  "rawQueryString": "",
  "headers": {
    "accept": "*/*",
    "host": "example.com"
  },
  "requestContext": {
    "accountId": "123456789012",
    "apiId": "api-id",
    "domainName": "example.com",
    "domainPrefix": "example",
    "http": {
      "method": "GET",
      "path": "/your-route",
      "protocol": "HTTP/1.1",
      "sourceIp": "127.0.0.1",
      "userAgent": "test-client"
    },
    "requestId": "test-request-id",
    "routeKey": "GET /your-route",
    "stage": "$default",
    "time": "23/Aug/2026:00:00:00 +0000",
    "timeEpoch": 1755907200000
  },
  "isBase64Encoded": false
}
```
Keep one dedicated file per route/scenario (e.g. `test-event-health.json`, `test-event-patients.json`) rather than reusing and overwriting one filename — reusing a name makes it impossible to tell which version of the event produced which response after the fact.

### Invoke and Read Logs Together
```bash
aws lambda invoke --function-name oroscope-dev-fastapi --payload file://test-event.json response.json
cat response.json
aws logs tail /aws/lambda/oroscope-dev-fastapi --follow
```
A clean rejection (a real HTTP status your own code returned, e.g. `401` with a specific `detail` message) means the stack is working as designed. A raw Python traceback in the logs means something upstream of your application logic broke — check that first, don't assume it's a business-logic bug.

---

## Packaging the Control-Plane Lambda
See ‘Build and deploy the Lambda’ below
`--only-binary=:all:` is required, not optional — without it, pip may silently fall back to compiling a package from source using your local toolchain, producing a binary built for your machine instead of Lambda's, defeating the whole point of `--platform`.

---

## Adding a New Postgres ENUM Column
This project has hit the same SQLAlchemy/Postgres ENUM-ownership conflict twice — once in a raw Alembic migration, once in an ORM model. The fix is the same both times: **explicitly tell SQLAlchemy the type already exists and it should not try to manage its lifecycle.**

**In a migration**, create the type with idempotent raw SQL rather than SQLAlchemy's own `.create()`:
```python
op.execute("""
    DO $$ BEGIN
        CREATE TYPE your_type_name AS ENUM ('value1', 'value2');
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;
""")
```

**In the ORM model**, name the type explicitly and disable creation:
```python
class YourStatus(str, enum.Enum):  # str mixin avoids Pydantic serializing as "YourStatus.value1"
    value1 = "value1"
    value2 = "value2"

status = Column(Enum(YourStatus, name="your_type_name", create_type=False), nullable=False)
```
Skipping `create_type=False` causes SQLAlchemy to attempt creating the type a second time whenever `create_table()` runs, colliding with a type that already exists.

---

## Working Across Two Machines
- `.terraform/`, provider binaries, and `*.tfstate` never travel with git — they are regenerated per machine. Run `terraform init` fresh on a new machine every time.
- Provider binaries are OS-specific — a Linux build won't run on Windows, which is why a stale copied `.terraform/` folder fails; re-init fixes it.
- **Discipline:** `git pull` before editing, `git push` after. State safety is already handled by the S3 backend + native lock regardless of which machine you're on.
- Check `aws configure get region` on any new machine before running region-sensitive commands — a mismatched default region produces silent "not found" errors that look like missing resources, not configuration problems.

---

## Gotchas
- Security group `description` fields (`GroupDescription`) are ASCII-only — em dashes and smart quotes fail creation with `InvalidParameterValue`.
- Postgres `DatabaseName` must be letters, numbers, and underscores only — **no hyphens**.
- Terraform only prompts `yes/no` for backend (state location) changes — not for provider version bumps or plain resource changes. Both proceed silently if the plan looks otherwise correct.
- Never change a live resource's `name` argument once applied if other live resources reference it (e.g. a DB subnet group or security group attached to a running Aurora cluster) — many AWS resource identifiers are immutable, forcing a destroy-and-recreate. Only `tags` are reliably safe to change on an already-applied resource.
- A route returning a generic internal error with *no* CloudWatch log entry
  at all for that Lambda usually means `aws_lambda_permission` is missing —
  API Gateway was never granted permission to invoke the function. This looks
  identical to a broken Lambda from the outside; check for the permission
  grant before debugging the function itself.
---

## Checking What Something Actually Cost
Go to: **Console → Billing and Cost Management → Cost Explorer → group by Service**, filtered to the relevant date range. Don't guess — check.


## Build and deploy the Lambda

Run from the repo root. Lambda zips are Linux-only, so `build_lambda.sh` fetches Linux wheels even on Windows/macOS.

```bash
services/control-plane/build_lambda.sh      # builds fastapi_backend.zip (~32 MB zipped; limits 50 MB / 250 MB unzipped)
cd infra && terraform plan                   # read it: expect only the Lambda code hash to change
terraform apply
```

- `services/control-plane/package/` and `fastapi_backend.zip` are build output and are git-ignored. Never commit them.
- boto3 is deliberately left out of the zip (the Lambda runtime provides it).
- **Two clones of the repo exist (Windows laptop + Linux).** Always `git pull` before editing; a stale clone caused a broken `main.py` once.

## End-to-end test of the optical flow

```bash
pip install requests pillow numpy
export API_URL="https://jy3bq91s6k.execute-api.ap-south-2.amazonaws.com"
export ID_TOKEN="<IdToken printed by test_login.py>"      # must be EXPORTED; expires after ~1 hour
python3 scripts/test_optical_flow.py <image1> <image2> "Fibroma"
```
Expected: every step 200/204, final line `MATCH` (API SSIM equals a local recomputation). Test photos stay out of git (`scripts/*.png`, `scripts/*.jpg` are ignored).

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `404 {"message":"Not Found"}` | API Gateway route missing. `aws apigatewayv2 get-routes --api-id jy3bq91s6k --region ap-south-2 --query 'Items[].RouteKey'` should list 7 routes |
| `401` | Missing/expired token (ID tokens last ~1 h); re-run `test_login.py` |
| `503` + `Retry-After: 5` | Aurora auto-paused and resuming (scale-to-zero); retry in a few seconds |
| `KeyError: 'ID_TOKEN'` | Variable set without `export` |
| S3 upload `403` | Presigned form expired (5 min), file over 10 MB, or Content-Type not `image/*` |
| `409` on PATCH optical | Images not uploaded yet; request upload URLs and upload both |
| `422` on PATCH optical | An uploaded file is not a decodable image |
| `warning: ... not in the scoring sheet` | Provisional diagnosis name has no scoring row; `final_score` is cleared and status returns to `pending` |
| Terraform shows route/Lambda destroys | Stop; do not apply. Compare against `get-routes` and state |

## Clean up test data

Test patients are named "Optical Test". Delete them (diagnoses cascade) through the Data API:
```bash
aws rds-data execute-statement --region ap-south-2 --database oroscope_aurora \
  --resource-arn "$(terraform -chdir=infra output -raw aurora_cluster_arn)" \
  --secret-arn "$(terraform -chdir=infra output -raw aurora_secret_arn)" \
  --sql "DELETE FROM patients WHERE name = 'Optical Test';"
```
Images expire from S3 automatically after 30 days.

## Open items
- Dentist to confirm: aliases IRRITATION FIBROMA -> Fibroma and APTHOUS STOMATITIS -> Apthous Ulcer; the 7 scored diagnoses with no clinical_rules rows.
- `clinical_rules.provisional_diagnosis` has inconsistent case/whitespace; scoring matching ignores both, the rules lookup does not (verify before relying on it for non-uppercase names).