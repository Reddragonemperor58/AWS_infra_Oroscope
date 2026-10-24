# ADR 0015: Doctor MFA, browser session storage, input hardening

Status: accepted (amends ADR 0013 session handling)

## Context
The app holds real patient data. A password alone is the weakest link, and doctors use
phones/tablets and refresh the page often.

## Decisions
1. **TOTP MFA is mandatory** (Cognito `mfa_configuration = "ON"`, authenticator app). SMS MFA rejected: costs money, SIM-swap risk.
2. **Session lives in `sessionStorage`**: survives refresh, dies when the tab closes. `localStorage` rejected (persists after the clinic PC is left; any XSS could read it for months). Mitigation of XSS: strict CSP, no inline script, DOM built with createElement.
3. **30-minute inactivity sign-out** in the browser; refresh token validity 1 day.
4. **Request models mirror DB column limits** (422 instead of DB error / unbounded payload). Responses stay unconstrained.
5. **`hide_parameters=True`** on the SQLAlchemy engine so patient values never appear in logged errors.
6. **Weekly `pip-audit` + Dependabot** for dependency CVEs.

## Consequences
Every doctor enrols an authenticator at first login. Scripts need `COGNITO_MFA_CODE`. SES email stays blocked until a custom domain is verified (Cognito default sender is ~50 mails/day).
