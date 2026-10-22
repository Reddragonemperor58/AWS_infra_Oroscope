# ADR 0010: Cognito-to-Database User Sync Gap

## Status
Resolved by lazy provisioning (see Resolution). Was open through the frontend release (ADR 0013).

## Context
A real Cognito-authenticated identity — a genuine JWT, correctly validated
by API Gateway — can exist with no corresponding row in `users`, since
nothing currently creates that row automatically. Discovered testing
`/patients` with a real (non-mock) user for the first time: the app
correctly returned 401 rather than silently trusting an unrecorded identity.

## Current State
No automated sync exists. New Cognito users require a manual `INSERT INTO
users` via the Data API before using any authenticated endpoint.

## Considered, Not Yet Implemented
Cognito Post-Confirmation triggers are the standard fix — but they fire on
**self-service signup confirmation**, and this project deliberately uses
`allow_admin_create_user_only = true` (ADR 0004). Whether Post-Confirmation
fires for an `admin-create-user` + `admin-set-user-password --permanent`
account is unconfirmed and needs verifying before building on it.

## Decision (Interim)
Accept the manual-insert workaround. Do not build the trigger until its
behavior for admin-created users is confirmed — an unverified sync mechanism
that silently doesn't fire is worse than an honest manual step.

## Consequences
Every real doctor account currently needs a manual database insert alongside
Cognito creation. Must be resolved before this becomes multi-user.
## Resolution
`get_current_user` now creates the `users` row on the first authenticated request from a new Cognito identity: it inserts `id` = the verified `sub` and `email` from the token claims with `INSERT ... ON CONFLICT DO NOTHING`, then re-reads the row.
- **Why this is safe:** API Gateway has already verified the token, and the pool is admin-create-only (ADR 0004), so a valid token can only belong to a doctor an admin created.
- **Why not a Post-Confirmation trigger:** it fires on self-service signup confirmation, and we could not confirm it fires for admin-created accounts. Lazy provisioning does not depend on that.
- **Races:** two simultaneous first requests cannot create duplicates or crash (`ON CONFLICT DO NOTHING`).
- **Edge cases:** a token without an `email` claim (an access token) gets 401 with a message to send the ID token; an email already owned by a different `sub` (a recreated Cognito user) gets 409.
- **Trade-off:** the first request from a new doctor does one extra write. Deleting a Cognito user does not delete their `users` row (their patients remain); that cleanup is manual.
