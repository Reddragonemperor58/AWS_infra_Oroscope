# ADR 0005: Rules Engine Data Storage

## Context
Stage 3 requires implementing the clinical diagnosis and optical scoring rules engine. The original application relied on external Excel/CSV files. We need to decide where this ruleset lives in the cloud architecture. We do not yet possess the final, production clinical data, meaning the system will be built using placeholder data to verify the schema and matching logic.

## Decision
We will store the clinical and scoring rules as **bundled JSON files** deployed directly alongside the Lambda function code (`clinical_rules.json` and `scoring_rules.json`), rather than creating a database table (e.g., in Aurora via Alembic).

## Rationale
* **Simplicity & Speed:** Bundled files have zero AWS dependencies. They can be read into memory during the Lambda cold start and cached, requiring no network calls or database queries.
* **Auditability:** Clinical diagnostic rules are highly sensitive. Keeping them in version control (Git) ensures every modification goes through standard code review and leaves a permanent audit trail.
* **Premature Optimization:** Standing up a full database migration and CRUD API for tables that currently only hold placeholder data is unnecessary overhead at this stage.

## Consequences
* **Deployment overhead:** Updating a single clinical rule requires a full code deployment, whereas a database table would allow runtime updates.
* **Future Migration:** If the clinic later requires a UI for administrators to update rules on the fly, we will need to migrate this data into Aurora and rewrite the loader logic to use the Data API.