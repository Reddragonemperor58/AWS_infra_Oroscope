# ADR 0010: Cognito-to-Database User Sync Gap

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