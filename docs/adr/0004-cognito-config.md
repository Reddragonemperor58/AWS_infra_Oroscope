# ADR 0004: Cognito User Pool Configuration and Auth Flows

## Context
The initial prototype used a hardcoded JWT implementation in `auth.py` with a fixed 30-minute expiry and no refresh path. For the cloud deployment, we provisioned an Amazon Cognito User Pool to act as the identity provider (IdP). We needed to determine the account provisioning model, the specific authentication flows, and the appropriate pricing tier to support necessary security features without incurring unnecessary per-MAU costs.

## Decisions

1. **Identity Structure (Admin-Only, Email, No Groups)**
   * **Admin-Only Creation:** Public sign-ups are explicitly disabled (`allow_admin_create_user_only = true`). Because this is a B2B healthcare application, doctor accounts are centrally provisioned by clinic administrators.
   * **Email as Username:** Enforced as the sole username attribute (`username_attributes = ["email"]`) for simplicity.
   * **No Cognito Groups (YAGNI):** We are deferring the use of IAM/Cognito groups. The current requirement only dictates a single baseline role (Doctor), making group-based RBAC unnecessary at this stage.

2. **Auth Flow (SRP over Admin API)**
   * We explicitly use `ALLOW_USER_SRP_AUTH` (Secure Remote Password) and rejected the `ADMIN_NO_SRP_AUTH` flow. 
   * *Rationale:* SRP is a zero-knowledge proof protocol. It ensures the frontend performs cryptographic hashing locally so the plaintext password is never transmitted over the wire to AWS. 

3. **Refresh Token Rotation & Flow Conflict**
   * We enabled modern refresh token rotation (`refresh_token_rotation.feature = "ENABLED"`).
   * *The Catch:* Doing so required us to **remove** `ALLOW_REFRESH_TOKEN_AUTH` from the `explicit_auth_flows` list. Enabling the legacy refresh flow natively conflicts with the modern `GetTokensFromRefreshToken` rotation operation, which AWS explicitly enforces at the API level (throwing an `InvalidParameterException` if both are configured).

4. **Pricing Tier and Password History (Empirically Validated)**
   * We configured `password_history_size = 5` to prevent password reuse. 
   * *Validation:* There was initial concern (stemming from outdated Terraform documentation) that this feature was gated behind Cognito's expensive Advanced Security (Plus) tier ($0.05/MAU). We explicitly locked the pool to `user_pool_tier = "ESSENTIALS"` and ran a live `terraform apply`. The pool provisioned successfully, confirming empirically that password history is included in the base Essentials tier flat rate.

## Consequences
* **Frontend Burden:** The React frontend (Stage 5) cannot simply POST a password to an endpoint. It must use a library capable of the SRP cryptographic handshake (e.g., AWS Amplify Auth or `amazon-cognito-identity-js`).
* **Session Management:** The frontend must strictly use `GetTokensFromRefreshToken` for session renewal.
* **Testing:** Backend engineers cannot use the standard AWS CLI `initiate-auth` command to test logins. Testing requires the `pycognito` Python library to calculate the SRP primes locally.