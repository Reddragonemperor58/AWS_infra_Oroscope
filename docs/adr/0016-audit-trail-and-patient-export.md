# ADR 0016: Audit trail, account activity and patient export

Status: accepted (Oct 2026)

## Context
The app holds patient names, phone numbers and clinical photos. We need to answer "who looked at
or changed this record, and when", and a patient (through their doctor) can ask for a copy of their data.

## Decisions
1. **`audit_events` table**, written by the API itself, one row per patient/diagnosis action
   (create, list, search, view, update, export, case history, case detail, lookup, upload, analysis).
2. **Same transaction as the action** for writes (a change and its audit row succeed or fail
   together). Reads add the row and commit straight away. If the audit insert fails, the request fails
   (fail-closed): an unlogged read of patient data is worse than a retry.
3. **Ids and field names only**: never names, phones, search text or findings. The search text is not
   logged because it can be a phone number. Source IP is kept (API Gateway supplies it).
4. **No foreign keys** on the table, so the trail survives deleting a patient or a doctor.
5. **Doctors see only their own activity** (`GET /me/activity`, Account screen). Reading all doctors'
   activity is a database query for the owner, not an API.
6. **Export = one JSON document** (`GET /patients/{id}/export`), itself audited. Photos are links that
   expire after 10 minutes, not embedded files.
7. Rejected: CloudTrail-style logging only (does not know patients), log lines in CloudWatch (hard to
   query, retention is short), deleting old rows (no retention rule yet; lawyer question).

## Consequences
- One extra small write per request; negligible at current scale, and Aurora is already awake for the read.
- Read failures can now come from the audit insert; the 503 retry logic already covers the cold start.
- Retention of audit rows is undecided (ask the lawyer together with patient-data retention).
- Not covered: failed attempts and logins (Cognito keeps its own sign-in logs), and who-saw-what
  across doctors' accounts (not a feature while each clinic has a single login).
