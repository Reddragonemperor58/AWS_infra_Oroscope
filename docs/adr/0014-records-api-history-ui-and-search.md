# ADR 0014: Records API, case history UI and substring search

## Status
Accepted. Built and verified against the live system (19 API checks, plus 5 other-doctor checks, and the browser).

## Context
After ADR 0013 a doctor could create a patient and run one diagnosis, but could not find a patient
again, see past cases, fix a typo in a name, or recover a forgotten password. A clinic cannot use the
app without those. None of it needs a clinical decision, so it was built before the items that wait
on dentist answers.

## Decision
- **A separate router, `app/records.py`,** holds the read and edit endpoints (patient list/search,
  get, patch; case history; case detail) so `main.py` keeps the diagnosis workflow only.
  Four new JWT-protected routes in `infra/apigateway_records.tf`.
- **Ownership on every query.** Each lookup filters by the calling doctor's id. A missing record and
  another doctor's record both return 404 (BOLA, ADR 0009). Proven live with a second doctor.
- **Store the provisional diagnosis.** New nullable column `diagnoses.provisional_diagnosis`
  (migration `5e12d1392533`), written by the lookup and optical steps. History can then show what
  each score was computed from. Older cases show "provisional diagnosis not recorded".
- **Photos by signed link.** Case detail returns presigned GET URLs (10 minutes, regional S3
  endpoint, SigV4). The CSP `img-src` allows that one S3 host. An expired photo shows a plain message.
- **Search is `strpos`, not `ILIKE`.** First version used `ILIKE ... ESCAPE '\'` to match wildcards
  literally. Through the RDS Data API it failed with `syntax error at or near ":"` (HTTP 500)
  because the Data API's parameter parser misreads the backslash literal. `strpos(lower(name), lower(q)) > 0`
  OR `strpos(phone, q) > 0` has no wildcards to escape, so "%" and "_" are searched literally. A test
  checks that the compiled SQL contains no `ESCAPE`, `LIKE` or backslash.
- **Paging.** `limit` (1 to 200, default 50) and `offset`, sorted by `lower(name), id`.
- **Edit is partial.** `PATCH /patients/{id}` changes only the fields sent; blank name and age outside
  0 to 120 are rejected with 422.
- **Forgot password uses Cognito's emailed code,** called from the browser with the public client.
  It needs a verified email that can receive mail.

## Consequences
- Search scans the doctor's own patients with no index. Fine for a clinic; add a trigram index if
  one doctor reaches many thousands of patients.
- Any future query must be tried through the Data API, not only through a normal Postgres driver.
- Cognito's built-in email is capped (about 50 per day) and generic; SES is needed before real clinics
  (on the readiness checklist).
- Staying logged in across a refresh is still not done: it would mean storing tokens, which weakens
  ADR 0013's in-memory choice, so it needs a decision.
- Case history and edit endpoints are not yet audited (no audit log); listed on the readiness checklist.
