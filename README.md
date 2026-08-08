# Oroscope

AI-assisted oral cancer screening tool for dentists — combines a rule-engine
diagnosis (structured symptom/observation matching), an optical filter
comparison, and a deep-learning image classifier into a single diagnostic
workflow. Originally built as a Streamlit + FastAPI prototype; being rebuilt
as a serverless, event-driven AWS architecture.

## Status

**Stage 1 of 9 — complete.** Network and database infrastructure provisioned,
empirically tested, and documented. See `docs/architecture.md` for current
system state.

| Stage | Status |
|---|---|
| 0 — AWS account, IAM, Terraform bootstrap | Done |
| 1 — Network + Aurora Serverless v2 + schema migrations | Done |
| 2 — Cognito (identity) | In progress |
| 3 — Control-plane Lambda + API Gateway | Not started |
| 4 — S3 + SQS + inference Lambda (container image) + SNS | Not started |
| 5 — Frontend (React, static, S3 + CloudFront) | Not started |
| 6 — CI/CD | Not started |
| 7 — Observability, cost guardrails, security hardening | Not started |

## Stack at a glance

- **IaC:** Terraform, S3 + native locking remote backend (see ADR 0001)
- **Database:** Aurora Serverless v2 (PostgreSQL 17.9), accessed exclusively
  via the Data API — no VPC-attached compute (see ADR 0002)
- **Migrations:** Alembic, via `sqlalchemy-aurora-data-api` (see ADR 0003)
- **Identity:** Cognito User Pool (in progress)
- **Compute (planned):** Lambda — control plane synchronous, inference async
  via SQS, packaged as a container image (no Kubernetes/EKS)

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — current infrastructure state
- [`docs/schema.md`](docs/schema.md) — authoritative database schema
- [`docs/runbook.md`](docs/runbook.md) — operational how-tos (migrations,
  querying via CLI, finding valid engine versions, multi-machine workflow)
- [`docs/cost-notes.md`](docs/cost-notes.md) — real observed costs and why
- [`docs/concepts.md`](docs/concepts.md) — glossary, written for interview review
- [`docs/adr/`](docs/adr/) — architecture decision records:
  - [0001 — IaC tool choice](docs/adr/0001-iac-tool-choice.md)
  - [0002 — Database engine choice](docs/adr/0002-database-choice.md)
  - [0003 — Migration execution strategy](docs/adr/0003-migration-execution-strategy.md)

## Local setup

See `docs/runbook.md` for running migrations and querying the database
directly. AWS credentials must be configured independently on each machine
(`aws configure`) — never committed, never synced via git.