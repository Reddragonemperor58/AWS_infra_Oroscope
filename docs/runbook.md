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
See "Build and deploy the Lambda" below; `build_lambda.sh` does the packaging.
Inside it, `--only-binary=:all:` is required, not optional — without it, pip may silently fall back to compiling a package from source using your local toolchain, producing a binary built for your machine instead of Lambda's, defeating the whole point of `--platform`.

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
- The Data API cannot return Postgres `CHAR` columns (`UnsupportedResultException`); cast them in the query, e.g. `confdeltype::text`.
- The database name is `oroscope_aurora` (not `oroscope`): `database "oroscope" does not exist` means the wrong `--database`.
- `terraform fmt` only rewrites formatting; `terraform validate` checks syntax and references. Neither changes infrastructure.
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

## Deploy the frontend

Edit files in `frontend/`, then:
```bash
cd infra && terraform plan && terraform apply
terraform output -raw frontend_url
```
Terraform uploads the changed files (`no-cache`; CloudFront caching is disabled), so a hard refresh (Ctrl+Shift+R) shows the change. Never create `frontend/config.js`: Terraform generates it from outputs. After the form fields or the rules table change, re-run `python3 scripts/export_clinical_options.py` (writes `frontend/options.json` from the live database) and commit the result.

## Test users (Cognito)

Doctors are admin-created only (ADR 0004):
```bash
aws cognito-idp list-users --user-pool-id <pool id> --region ap-south-2
aws cognito-idp admin-create-user --user-pool-id <pool id> --username <email> --region ap-south-2
aws cognito-idp admin-set-user-password --user-pool-id <pool id> --username <email> --password '<password>' --permanent --region ap-south-2
```
Create the doctor with the `email` attribute (the ID token must carry it):
```bash
aws cognito-idp admin-create-user --user-pool-id <pool id> --username <email> \
  --user-attributes Name=email,Value=<email> Name=email_verified,Value=true \
  --message-action SUPPRESS --region ap-south-2
```
No database step is needed: the `users` row is created automatically on the doctor's first request (ADR 0010). To remove a doctor, delete the Cognito user and then `DELETE FROM users WHERE email = '<email>'` (their patients and diagnoses cascade).

## Scripts

| Script | Purpose |
|---|---|
| `scripts/test_optical_flow.py` | End-to-end optical test (needs exported `API_URL` and `ID_TOKEN`) |
| `scripts/test_clinical_lookup.py` | Checks that the lookup is case- and whitespace-insensitive on provisional_diagnosis |
| `scripts/export_clinical_options.py` | Builds `frontend/options.json` (dropdown values) from the database |
| `scripts/get_token.py` | Prints a doctor's Cognito ID token. Password comes from the `COGNITO_PASSWORD` environment variable, never a file or argument |
| `scripts/test_records_flow.py` | Live test of patients, search, history, detail and photo links (19 checks; 5 more other-doctor checks when `ID_TOKEN_2` is set) |

## Getting a token without typing the password into a command

```bash
read -s -p "Password: " COGNITO_PASSWORD; export COGNITO_PASSWORD; echo
export ID_TOKEN=$(python scripts/get_token.py <email>)
export API_URL="<api url>"
python3 scripts/test_records_flow.py
```
For the other-doctor checks, create a second doctor and also `export ID_TOKEN_2=$(python scripts/get_token.py <second email>)`. If a password ever ends up in a command line, it is in the shell history: change it and clear the history.

## Testing "Forgot password"

The reset code is emailed by Cognito, so the doctor's email must be a real inbox and marked verified. `someone@example.com` will show "A password reset is not available for this account". For testing, use your own address with a plus suffix (`yourname+doc1@gmail.com` delivers to `yourname@gmail.com`) and create the doctor with `email_verified=true` as above. Cognito's built-in sender is capped at about 50 emails a day and looks generic; use SES before real clinics.

## Alembic against Aurora (Data API)

Run from the repository root (where `alembic.ini` is), after exporting the database URL:
```bash
export DATABASE_URL="postgresql+auroradataapi://:@/oroscope_aurora?aurora_cluster_arn=<cluster arn>&secret_arn=<secret arn>"
alembic upgrade head
alembic current          # expect 5e12d1392533 (head)
```
`script_location` errors mean you are in the wrong folder; `KeyError: 'url'` means `DATABASE_URL` is not exported.

## Git Bash on Windows

- `aws logs tail /aws/lambda/oroscope-dev-fastapi ...` fails because Git Bash rewrites the leading `/`. Prefix the command with `MSYS_NO_PATHCONV=1`.
- `terraform output` only works inside `infra/` (or use `terraform -chdir=infra output`). Empty ARNs in an `aws rds-data` call mean you ran it from the wrong folder.
- SQL typed at the prompt is run by bash, not the database. Wrap it in `aws rds-data execute-statement --sql "..."`.
- pip `WinError 32` is a file lock; re-run the command.
- Put `alert_email` in a git-ignored `infra/terraform.tfvars`, otherwise Terraform asks for it every time and a missing value would blank the budget alert.

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
| `404 {"message":"Not Found"}` | API Gateway route missing. `aws apigatewayv2 get-routes --api-id jy3bq91s6k --region ap-south-2 --query 'Items[].RouteKey'` should list 11 routes |
| `401` | Missing/expired token (ID tokens last ~1 h); re-run `test_login.py` |
| `503` + `Retry-After: 5` | Aurora auto-paused and resuming (scale-to-zero); retry in a few seconds |
| `KeyError: 'ID_TOKEN'` | Variable set without `export` |
| S3 upload `403` | Presigned form expired (5 min), file over 10 MB, or Content-Type not `image/*` |
| `409` on PATCH optical | Images not uploaded yet; request upload URLs and upload both |
| `422` on PATCH optical | An uploaded file is not a decodable image |
| `warning: ... not in the scoring sheet` | Provisional diagnosis name has no scoring row; `final_score` is cleared and status returns to `pending` |
| Browser console: CORS error on an API call | `allow_origins` does not match the page origin. Open the `frontend_url` address, not another domain |
| Browser console: CORS error on the S3 upload | Images bucket CORS missing the CloudFront origin (`aws_s3_bucket_cors_configuration.images`) |
| Browser console: CSP violation | Something inline or from another host was added; keep scripts and styles as files in `frontend/` |
| Login fails with the right password | User missing or password reset: check `list-users`, re-run `admin-set-user-password` |
| Page loads but is unstyled / old | Hard refresh (Ctrl+Shift+R); confirm `terraform apply` uploaded the file |
| `401` "Token has no email claim" | An access token was sent; the API needs the Cognito ID token |
| `409` "email is already registered to a different account" | A Cognito user was deleted and recreated with the same email (new `sub`). Delete the stale `users` row for that email |
| `500` on `GET /patients?q=...`, log says `syntax error at or near ":"` | `ILIKE ... ESCAPE '\'` reached the Data API, whose parser misreads the backslash. Search uses `strpos` instead (ADR 0014); do not reintroduce `ESCAPE` |
| `NotAuthorizedException` from `get_token.py` | Wrong password, or the user's password was never set permanent (`admin-set-user-password --permanent`) |
| `InvalidPasswordException` | The pool policy needs upper and lower case, digits, symbols and a long password (shorter ones were rejected in testing); check `password_policy` in the Cognito Terraform |
| "Password reset is not available for this account" | The user has no verified email that can receive mail (see Testing "Forgot password") |
| Terraform shows route/Lambda destroys | Stop; do not apply. Compare against `get-routes` and state |

## Clean up test data

Test patients are named "Optical Test", "Lookup Test" or "Records Test ..." (and the UI test patients you add by hand). Delete them (diagnoses cascade) through the Data API (run from the repo root; the `Records Test` ones need `LIKE 'Records Test%'` instead of the name list):
```bash
aws rds-data execute-statement --region ap-south-2 --database oroscope_aurora \
  --resource-arn "$(terraform -chdir=infra output -raw aurora_cluster_arn)" \
  --secret-arn "$(terraform -chdir=infra output -raw aurora_secret_arn)" \
  --sql "DELETE FROM patients WHERE name IN ('Optical Test', 'Lookup Test');"
```
Images expire from S3 automatically after 30 days.

## Open items
- Dentist to confirm: aliases IRRITATION FIBROMA -> Fibroma and APTHOUS STOMATITIS -> Apthous Ulcer (**unconfirmed**); the 7 scored diagnoses with no `clinical_rules` rows (they can be picked in the dropdown and give "no rule matches" on lookup).
- Confirm with the original app that two or more ticks should collapse to `Multiple symptoms` / `Multiple habits` / `Multiple areas` (confirmed working only for oral mapping against the table).
- Image retention (30 days) is a placeholder; confirm with the clinic.
- `clinical_rules.provisional_diagnosis` has inconsistent case/whitespace in the source; both scoring and the rules lookup now ignore it (lookup compares `upper(btrim())`; zero conflicts proven). `rules_engine.py` is a database lookup only.
- Not built: DL inference, SQS/SNS async processing.
- AWS Budgets alert is in place (`infra/budget.tf`); its email comes from `alert_email`.
- Add `httpx` to `requirements-dev.txt` (the route tests use FastAPI's TestClient).
