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

### Database & Application Concepts
* **Transactions:** A binary database operation (all-or-nothing). No partial execution is allowed.
* **Transactional DDL (Data Definition Language):** A PostgreSQL feature where schema updates (like creating or dropping tables) occur within a transaction. If any part of the migration fails, the entire schema change rolls back cleanly.
* **Migration:** A version-controlled way to safely apply and track database schema changes (using tools like Alembic) without breaking the database in production.
* **Idempotent DDL:** Database schema modification scripts written so they can be run multiple times safely without throwing errors (e.g., using `CREATE TABLE IF NOT EXISTS`).
* **Data API-Style Request:** A stateless HTTPS request that executes SQL against Aurora via IAM authentication. It is used for both DDL (schema changes) and ordinary DML operations (like `SELECT`, `INSERT`, `UPDATE`).
* **ACU (Aurora Capacity Unit) / Scale to Zero:** The metric of compute/RAM allocation for Aurora Serverless. It scales dynamically based on traffic and can be configured to drop to 0 (pausing compute entirely) when idle to save costs.

### Infrastructure as Code & Billing
* **Terraform State (`.tfstate`):** The internal tracking file where Terraform records the current real-world state of your cloud resources to compare against future code changes.
* **Reference vs. Value Distinction:** 
  * **Security / Architectural (Primary):** A *reference* is a pointer to a sensitive resource (like an ARN pointing to a database password), whereas the *value* is the sensitive data itself. It is perfectly safe to expose an ARN in Terraform outputs or log files because an ARN is completely inert. To resolve that reference into the actual value, the caller must pass a strict, secondary IAM permission check (e.g., `secretsmanager:GetSecretValue`) at runtime.
  * **IaC / Terraform (Secondary):** Referencing dynamic resource attributes (`aws_vpc.main.id`) keeps code resilient, whereas hardcoding literal string values (`"vpc-12345"`) breaks the code if the underlying infrastructure is destroyed and recreated.
* **Credit-Based vs. Always Free AWS Billing:** Credit-based offers expire after a set timeline or dollar limit. Always Free tiers (like 1M Lambda requests/month) persist indefinitely as long as usage stays under the strict monthly cap.