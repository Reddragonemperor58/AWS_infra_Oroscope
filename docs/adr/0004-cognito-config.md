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
   * We enabled refresh token rotation (`refresh_token_rotation.feature = "ENABLED"`), a Cognito feature that shipped April 2025.
   * *The Catch:* This required removing `ALLOW_REFRESH_TOKEN_AUTH` from `explicit_auth_flows`. AWS's documentation states directly that the legacy `REFRESH_TOKEN_AUTH` flow is not compatible with rotation — attempting to configure both throws `InvalidParameterException` at apply time, which is what we hit and fixed by removing the legacy flow entirely.
   * *Mechanism:* under the legacy flow, one refresh token is reused unchanged for its full validity window (30 days by default). Under rotation, each use of `GetTokensFromRefreshToken` returns a new refresh token and invalidates the one just used, narrowing the window a stolen token remains useful. (Note: verify empirically whether reuse of an already-rotated token triggers broader session revocation, or simply fails — not independently confirmed from documentation alone.)
   * *Also corrected:* access token validity defaults to 60 minutes, not the 30-minute figure carried over from the original prototype's hardcoded `auth.py` constant — never explicitly set in this Terraform, worth configuring deliberately rather than leaving implicit.

4. **Pricing Tier and Password History (Empirically Validated)**
   * We configured `password_history_size = 5` to prevent password reuse. 
   * *Validation:* There was initial concern (stemming from outdated Terraform documentation) that this feature was gated behind Cognito's expensive Advanced Security (Plus) tier ($0.05/MAU). We explicitly locked the pool to `user_pool_tier = "ESSENTIALS"` and ran a live `terraform apply`. The pool provisioned successfully, confirming empirically that password history is included in the base Essentials tier flat rate.

5. **Public Client Configuration (No App Client Secret)**
   * We explicitly set `generate_secret = false` for the Cognito User Pool Client.
   * *Rationale:* The client consuming this API is a React Single Page Application (SPA), which executes entirely in the user's browser. SPAs are "public clients," meaning they cannot securely store a cryptographic client secret—any embedded secret can be easily extracted by inspecting the JavaScript bundle or monitoring network traffic. If a secret had been generated, AWS would mandate calculating a `SECRET_HASH` for every authentication request. This would force the frontend to either expose the secret locally to calculate the hash, or rely on a backend proxy, defeating the purpose of a direct Cognito integration. 

## Consequences
* **Frontend Burden:** The React frontend (Stage 5) cannot simply POST a password to an endpoint. It must use a library capable of the SRP cryptographic handshake (e.g., AWS Amplify Auth or `amazon-cognito-identity-js`).
* **Session Management:** The frontend must strictly use `GetTokensFromRefreshToken` for session renewal.
* **Security Posture:** By omitting a client secret, we accept that security relies entirely on the robust implementation of SRP, token rotation, and strict Redirect URI validation, rather than a static shared secret.
* **Testing:** Backend engineers cannot use the standard AWS CLI `initiate-auth` command to test logins. Testing requires the `pycognito` Python library to calculate the SRP primes locally.
no mechanism currently syncs a Cognito user to a Users row; verify whether Post-Confirmation fires for admin-created accounts before building on that assumption; until resolved, every new doctor needs a manual insert like the one above.