# ADR 0011: Clinical Rules Storage Migration — Bundled File to Aurora Table

## Context
ADR 0005 decided to store the clinical rules engine's data as bundled JSON
files inside the Lambda deployment package, reasoning explicitly from a
small, hand-curated placeholder table (a handful of rows).

Once the real source file (`Final  DD for new software.xlsx`) was obtained
and inspected, two things were discovered that invalidate that reasoning:

1. **The real match key is ten fields, not four.** The original four-field
   match (`Ulcer`/`Patch`/`Growth`/`Mucosal Condition`) was empirically
   proven insufficient — 115 of 240 four-field combinations returned more
   than one diagnosis. Expanding to all nine clinical input fields still
   left 616 unresolved conflicts. Those conflicts were fully resolved only
   once `Provisional Diagnosis` was correctly understood to be an *input*
   to this lookup (the DL model's classification, arriving from a separate
   step) rather than an output of it — at which point all ten fields
   together produced a fully deterministic table: zero combinations with
   more than one `Differential Diagnosis` or `Advise`, across all rows.

2. **The real row count is ~592,000, not a few hundred.** Deduplicated on
   the correct ten-field key, the data converts to 591,976 unique rules.
   Serialized as JSON, that file alone is 183.2MB.

## Decision
Move the clinical rules table from a bundled JSON file into Aurora, as a
new `clinical_rules` table, queried through the same Data API path every
other piece of application data already uses — not reloaded into Lambda
memory at cold start.

## Rationale
- **Package size risk.** 183.2MB of data alone leaves little to no safe
  margin under Lambda's 250MB unzipped package limit once FastAPI,
  SQLAlchemy, `sqlalchemy-aurora-data-api`, boto3, and Pydantic are also
  included. This is the same class of risk ADR 0005 explicitly reasoned
  about and judged safe — correctly, for the data assumed at the time.
- **Correctness is unaffected by this change.** The ten-field match key and
  its proven one-row-per-combination guarantee hold identically whether the
  lookup runs against an in-memory dict or a SQL `WHERE` clause. Only the
  storage location changes.
- **Likely a net improvement, not just a workaround.** An indexed Postgres
  query against 592K rows is plausibly faster at cold start than
  deserializing an 183MB JSON blob into memory on every new execution
  environment — this resolves the packaging risk and may improve latency.
- **Bulk loading** requires `rds-data:BatchExecuteStatement` rather than
  592,000 individual Data API calls — already present, unused, in the
  Lambda's IAM policy (`lambda.tf`) from Stage 3.

## Consequences
- One new table (`clinical_rules`), loaded via a one-time bulk-import
  script — not a schema migration in the traditional sense, since this is
  data, not structure.
- `rules_engine.py`'s `get_differential_and_advise` changes from an
  in-memory dict lookup to a real SQL query executed through the existing
  `database.py` session, identical in spirit to every other endpoint's
  data access.
- `clinical_rules.json` and the conversion script that produced it are
  retired — useful as a one-time verification tool, not a permanent
  artifact.
- ADR 0005 is superseded by this ADR for the clinical rules specifically;
  its core reasoning (bundled files for small, static data) remains valid
  in general and is unaffected for anything else that stays genuinely small.