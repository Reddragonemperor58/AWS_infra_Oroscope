# Security review (October 2026)

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| F1 | SQL parameters (patient names/phones) could appear in error logs | Medium | Fixed: `hide_parameters=True` |
| F2 | No length limits on request bodies | Medium | Fixed: constrained `PatientCreate`/clinical models, tests |
| F3 | Password-only login | High | Fixed: TOTP MFA required, live and checked Oct 24 |
| F4 | Where the session token lives | Medium | Decided: sessionStorage + 30-min idle logout + strict CSP; refresh token 1 day, revoked on logout |
| F5 | Dependency CVEs | Low | `pip-audit` clean; weekly audit job and Dependabot |
| F6 | Per-user rate limiting | Medium | Open: needs AWS WAF (whole-API throttling exists) |
| F7 | No audit log of who viewed which patient | Medium | Fixed: `audit_events`, ADR 0016 |
| F8 | SES/custom domain for reset mail at scale | Low | Open: blocked on a domain |
| F9 | Lost authenticator device has no self-service recovery | Low | Runbook procedure (verify on a test account before relying on it) |

Checked OK: every record query filters by `doctor_id` (BOLA), signed upload/photo links expire
(300 s / 600 s), upload policy caps size at 10 MB and type at image/*, S3 private, database encrypted
with deletion protection, secrets not tracked.
Run `scripts/security_audit.sh` before releases.
