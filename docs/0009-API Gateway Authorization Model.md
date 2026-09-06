# ADR 0009: API Gateway Authorization Model

## Context
Routes need to reject unauthenticated requests before reaching the Lambda,
using the Cognito User Pool and App Client from Stage 2.

## Decision
HTTP API (v2) native JWT authorizer, applied per-route rather than globally.
`/health` is explicitly `authorization_type = "NONE"`; `/patients` and
`/diagnoses/clinical-match` require `"JWT"` against the Cognito authorizer.

## Rationale
- JWT signature/expiry/issuer/audience validation happens at the API Gateway
  layer, before Lambda ever invokes — an invalid token never incurs compute cost.
- Per-route (not per-API) authorization was chosen specifically so a health
  check can stay open for infrastructure monitoring without weakening
  protection on any route that touches real data.
- CORS is configured natively on the API resource itself, not via FastAPI's
  `CORSMiddleware` — see the earlier decision that OPTIONS preflights should
  never wake the Lambda at all.

## Consequences
- `cors_configuration.allow_origins` is currently `["*"]` — a deliberate,
  temporary placeholder. **Must be locked to the real frontend domain before
  any real user traffic**, or any website can call this API cross-origin.
- `aws_lambda_permission` is a separate, easy-to-forget grant — without it,
  every route returns an internal error even though the Lambda itself is fine.