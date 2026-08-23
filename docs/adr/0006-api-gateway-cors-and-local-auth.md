# ADR 0006: CORS Handling and Local Auth Bypass

## Context
As we build the Control Plane (FastAPI/Mangum), two architectural boundaries must be defined:
1. **CORS (Cross-Origin Resource Sharing):** Who handles browser preflight `OPTIONS` requests?
2. **Local Development Auth:** How do we test endpoints locally using `uvicorn` when API Gateway's `aws.event` context (and the Cognito JWT) is missing?

## Decisions
1. **API Gateway owns CORS:** We will configure CORS natively on the HTTP API (v2). This prevents the Lambda function from experiencing cold starts and billing charges just to answer browser preflight checks. FastAPI will not use `CORSMiddleware`.
2. **Local Auth via Dependency Overrides:** We reject embedding a `LOCAL_DEV` environment variable check inside the production auth path. Instead, local development will use a separate entrypoint (`local.py`) that utilizes FastAPI's `app.dependency_overrides` to inject a mock user. 

## Consequences
* The production code in `dependencies.py` has no escape hatch; it will securely crash if the AWS event context is missing.
* Local development requires running `python local.py` instead of the standard `uvicorn app.main:app`.