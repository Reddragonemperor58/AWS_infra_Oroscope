# ADR 0002: Database Engine Selection for Dr. Oroscope

## Context
Dr. Oroscope requires a relational database for Users (doctors), Patients, and Diagnoses. AWS Lambda functions must fetch patient images from S3, compute the optical deviation index, and write classification results back to the database. We need a database that balances secure access for a serverless compute layer with cost-efficiency during non-clinical hours.

## Options Considered
- **Standard RDS PostgreSQL** — traditional, provisioned, requires a direct TCP/psycopg2-style connection.
- **Aurora Serverless v2 (PostgreSQL)** — auto-scaling, AWS-managed, features the Data API.

## Decision
**Aurora Serverless v2 (PostgreSQL).**

## Reasoning
The primary driver is the network architecture for our inference pipeline. Enabling Aurora's Data API lets our Lambda execute SQL over standard HTTPS, authenticated via IAM (SigV4), keeping it entirely outside the VPC — no subnet configuration, no NAT Gateway to reach S3 or other AWS services. Standard RDS would have forced the Lambda into the VPC over a raw TCP connection, then required either a NAT Gateway or individual VPC endpoints for every other AWS service it calls.

Because clinics generally operate on fixed daytime schedules, Aurora Serverless v2's ability to scale ACUs to zero during idle periods — genuinely pausing, not just reducing — matches our bursty, low-volume traffic, keeping compute near zero outside active use.

Validated empirically, not just on paper: a real SQL query executed successfully via the Data API against the live cluster while the security group had zero ingress rules, confirming the connection never routes through the VPC's customer-facing network layer.

## Trade-offs Accepted
Real vendor lock-in — coupling data access to the proprietary Data API instead of standard `psycopg2` means a cloud migration would require rewriting the data access layer. A wake-up latency penalty applies on the first query after the cluster scales to zero. The Data API itself also isn't free — $0.20-0.70 per million requests, one million/month free for the account's first year — a small but real cost on top of Aurora's own compute and storage charges.