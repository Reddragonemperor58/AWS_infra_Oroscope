# Architectural Glossary

### Networking & Infrastructure
* **VPC (Virtual Private Cloud):** A private cloud network assigned to the customer which is isolated from the rest of the internet unless explicit gateways (IGW/NAT) and routing rules are added. It provides an isolated, secure boundary to deploy resources.
* **CIDR (Classless Inter-Domain Routing):** A flexible method for allocating IP addresses and routing traffic (e.g., `10.0.0.0/16`).
* **Subnet:** A logical subdivision of a VPC's IP block (e.g., `10.0.1.0/24`). A subnet is strictly bound to **exactly one Availability Zone**. 
* **Subnet Mask:** The number of bits that are constant in the IP address allocated to a subnet (e.g., the `/24` meaning 256 IP addresses).
* **Availability Zone (AZ):** Physically distinct data centers within a single AWS Region. You select multiple AZs primarily to ensure **high availability and redundancy**, rather than just proximity.
* **DB Subnet Group:** An AWS construct that groups private subnets across multiple AZs, required so that services like Aurora can place database network interfaces and handle multi-AZ failover.
* **Security Group:** A **stateful** virtual firewall applied directly at the *resource level* (e.g., an Aurora instance). Being stateful means if it allows an incoming request, it automatically remembers and allows the return response.
* **Network ACL (NACL):** A **stateless** virtual firewall applied at the *subnet boundary*. Being stateless means it evaluates inbound and outbound traffic completely independently; allowing an inbound request does not automatically allow the outbound response.
* **Internet Gateway (IGW):** A gateway that makes two-way internet traffic possible for a VPC. However, a resource is only reachable if it also has a public IP, route table rules pointing to the IGW, and permissive Security Groups.
* **NAT Gateway (Network Address Translation):** A one-way gateway that allows resources in private subnets to initiate outbound traffic to the internet (e.g., to download packages) but prevents the internet from initiating a connection back into the VPC.
* **VPC Gateway Endpoint vs. Interface Endpoint:** 
  * **Gateway Endpoint:** 100% free. Works by updating VPC Route Tables to access specific AWS services (only S3 and DynamoDB).
  * **Interface Endpoint (PrivateLink):** Costs ~$0.01/hour per AZ plus data fees. Provisions an actual network interface (ENI) with a private IP inside your subnet to access most other AWS services (like SSM or Secrets Manager) without leaving the AWS network.

### Identity, Security & IAM
* **IAM User:** A long-lived identity with permanent credentials, strictly meant for developers or administrators to access AWS APIs or the Console. **Not** for end-users logging into the application.
* **IAM Role:** A temporary identity assumed by AWS services (like Lambda) to securely request access to other resources without needing hardcoded credentials.
* **ARN (Amazon Resource Name):** The globally unique identifier used to reference specific AWS resources.
* **Secrets Manager:** An AWS-managed secure vault used to store and optionally rotate static secrets (like the database master password). It **does not** authenticate web requests or issue user tokens.
* **AWS SigV4 (Signature Version 4):** A software-level cryptographic signing protocol (HMAC-SHA256) used to authenticate AWS API requests. It is highly efficient at mitigating DDoS attacks because validating the math at the edge is computationally cheap compared to database lookups.
* **User Pool (Cognito):** The identity directory that handles end-user authentication (sign-up, sign-in, password resets) and issues JSON Web Tokens (JWTs) upon success.
* **Identity Pool (Cognito):** A service that takes authenticated users (from a User Pool) and assigns them temporary AWS IAM credentials so their client devices can access AWS services directly.
* **JWT (JSON Web Token):** A short-lived, cryptographically signed token used for authentication and authorization between the client and the backend.
* **What an Authorizer Checks:** It validates the JWT sent by the client, specifically verifying the cryptographic signature (using Cognito's public keys), the token's expiration time, and the issuer.
* **BOLA (Broken Object Level Authorization):** A critical API vulnerability where an application correctly validates *who* a user is (authentication), but fails to check if that user actually has permission to access the specific requested record (authorization).
* **Presigned URL:** A temporary, secure link that gives someone time-limited access to a specific AWS resource (like an S3 object) without requiring them to have AWS credentials.
* **Access Token:** A token assigned to the User by the Cognito for api requests. Expiry time is in hours. Travels all over the network, Vulnerability is high.
* **Refresh Token:** A token assigned to the User by the Cognito to mint new access tokens for every specified number of hours. Expiry time is usually in days or months. Only exchanges between the Cognito and User. Vulnerability is low. In this deployment,  rotated with new Refresh token by Cognito when a new access token is recieved.
* **ID Token:** An OpenID Connect (OIDC) token issued by Cognito containing the user's identity profile (like email, unique sub, and name). Unlike the Access Token (which is sent to the backend for authorization), the ID Token is consumed exclusively by the frontend client to verify who the user is and instantly display profile data without making an extra backend API request. It is minted alongside and shares the exact same short-lived expiry time as the Access Token.
* **Public Client vs. Confidential Client:** 
  * **Confidential Client:** An application (like a Node.js or Django backend) running on a private server where source code and environment variables are hidden from users. It can safely store a Client Secret to prove its application identity to Cognito.
  * **Public Client:** An application (like a React SPA or iOS app) executing directly on a user's device. Because its code can be inspected by the user, it cannot securely store a Client Secret (`generate_secret = false`).
  * **Example Analogy (The Bank Vault):**
    > **Confidential Client (Server):** Both keys are required simultaneously to open the box. Even if a thief steals the customer's key, they can't open the box without the Bank Manager standing next to them in the official bank building.
    > 
    > **Public Client (SPA):** The app is out in the open (the browser), so there is no Bank Manager present. You cannot leave the Manager's key hanging on the wall for everyone to see. So Cognito allows the vault to open with just the customer's key, but compensates by adding extra cameras and security protocols (SRP, Token Rotation, PKCE).
* **SRP (Secure Remote Password):** A zero-knowledge proof cryptographic protocol. It allows a client (React) to prove to a server (Cognito) that it knows a password by doing complex math locally, guaranteeing the plaintext password is never sent over the internet.
* **PKCE (Proof Key for Code Exchange):** An optional OAuth 2.0 security extension that dynamically generates a temporary cryptographic secret for every individual authorization request. It protects Public Clients against authorization code interception attacks without requiring a static Client Secret. Its been modified to mandatory in OAuth 2.1.
* **User Pool:** The overarching identity directory and database. It stores the actual human users, their attributes (emails, UUIDs), their hashed passwords, and global security policies (like password strength). By itself, it cannot process logins.
* **User Pool Client (App Client):** The specific configuration "doorway" that allows a software application to interact with a User Pool. A single User Pool can have multiple App Clients (e.g., one for a Web SPA, one for a Mobile App, one for a Backend Server), each with its own specific security rules, token expirations, and Client ID.
* **Client ID:** The unique public identifier for a specific User Pool Client. It tells Cognito which "door" an authentication request is trying to use.
* **URI vs. URL:** A URI (Uniform Resource Identifier) is a string of characters that identifies a resource either by its location, its name, or both. A URL (Uniform Resource Locator) is a specific type of URI that tells you exactly *where* a resource is on the internet and *how* to get there (e.g., starting with `https://`). **All URLs are URIs, but not all URIs are URLs.**
* **Redirect URI (Callback URI):** The exact, pre-registered destination where an Identity Provider (like Cognito) sends a user (and their tokens) after a successful login. OAuth uses the broader term "URI" rather than "URL" because this destination isn't always a web address; it must also support custom deep links for mobile apps (e.g., `oroscope-mobile://auth-callback`) which do not point to an internet location. In Cognito, this acts as a strict security whitelist to ensure tokens cannot be hijacked and sent to malicious phishing domains.

### Database & Application Concepts
* **Transactions:** A binary database operation (all-or-nothing). No partial execution is allowed.
* **Transactional DDL (Data Definition Language):** A PostgreSQL feature where schema updates (like creating or dropping tables) occur within a transaction. If any part of the migration fails, the entire schema change rolls back cleanly.
* **Migration:** A version-controlled way to safely apply and track database schema changes (using tools like Alembic) without breaking the database in production.
* **Idempotent DDL:** Database schema modification scripts written so they can be run multiple times safely without throwing errors (e.g., using `CREATE TABLE IF NOT EXISTS`).
* **Data API-Style Request:** A stateless HTTPS request that executes SQL against Aurora via IAM authentication. It is used for both DDL (schema changes) and ordinary DML operations (like `SELECT`, `INSERT`, `UPDATE`).
* **ACU (Aurora Capacity Unit) / Scale to Zero:** The metric of compute/RAM allocation for Aurora Serverless. It scales dynamically based on traffic and can be configured to drop to 0 (pausing compute entirely) when idle to save costs.
* **UUID:** Universally Unique Identifier.
* **sub:** stands for Subject (a standard term defined in the OpenID Connect and JWT specifications).
* **IDP:** Identity Provider.
* **SPA (Single Page Application):** A web application (like React) that downloads entirely to the user's browser on the first load, rather than relying on a server to render and send new HTML pages for every click.

### Infrastructure as Code & Billing
* **Terraform State (`.tfstate`):** The internal tracking file where Terraform records the current real-world state of your cloud resources to compare against future code changes.
* **Reference vs. Value Distinction:** 
  * **Security / Architectural (Primary):** A *reference* is a pointer to a sensitive resource (like an ARN pointing to a database password), whereas the *value* is the sensitive data itself. It is perfectly safe to expose an ARN in Terraform outputs or log files because an ARN is completely inert. To resolve that reference into the actual value, the caller must pass a strict, secondary IAM permission check (e.g., `secretsmanager:GetSecretValue`) at runtime.
  * **IaC / Terraform (Secondary):** Referencing dynamic resource attributes (`aws_vpc.main.id`) keeps code resilient, whereas hardcoding literal string values (`"vpc-12345"`) breaks the code if the underlying infrastructure is destroyed and recreated.
* **Credit-Based vs. Always Free AWS Billing:** Credit-based offers expire after a set timeline or dollar limit. Always Free tiers (like 1M Lambda requests/month) persist indefinitely as long as usage stays under the strict monthly cap.