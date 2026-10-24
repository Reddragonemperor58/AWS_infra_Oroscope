# Security review (October 2026)

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| F1 | SQL parameters (patient names/phones) could appear in error logs | Medium | Fixed: `hide_parameters=True` |
| F2 | No length limits on request bodies | Medium | Fixed: constrained `PatientCreate`/clinical models, tests |
| F3 | Password-only login | High | Fixed: TOTP MFA ON (needs Terraform apply) |
| F4 | Token stored where? | Medium | Decided: sessionStorage + idle logout + strict CSP |
| F5 | Dependency CVEs | Low | `pip-audit` clean today; weekly audit + Dependabot |
| F6 | Per-user rate limiting | Medium | Open: needs WAF (whole-API throttling exists) |
| F7 | No audit log of who viewed which patient | Medium | Open |
| F8 | SES/custom domain for reset mail at scale | Low | Open: blocked on domain |

Checked OK: every record query filters by `doctor_id` (BOLA), presigned URLs expire in 300 s, S3 private, DB encrypted + deletion protection, secrets not tracked.
Run `scripts/security_audit.sh` before releases.
