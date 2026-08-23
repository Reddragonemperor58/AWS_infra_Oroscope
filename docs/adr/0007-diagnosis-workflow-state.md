# ADR 0007: Diagnosis Workflow State Management

## Context
The Oroscope diagnosis process is multi-step: clinical rules matching, optical analysis (SSIM), and deep learning screening. We must determine how and when the `Diagnoses` database record is created to accumulate these results. 

## Decision
The `POST /diagnoses/clinical-match` endpoint will act as the **state initiator**. It will take the clinical inputs (ulcer, patch, growth, mucosal condition), run the rules engine, and explicitly create the `Diagnoses` database row. It will set the initial `status` to `pending`, persist the rules result, and return the newly generated `diagnosis_id`.

## Rationale
* **Simplified Frontend Logic:** The frontend does not need to pre-create an empty diagnosis record. It starts the flow with real clinical data and receives a tracking ID for subsequent steps.
* **Database Integrity:** Subsequent expensive operations (like uploading heavy DL and optical images) will use `PATCH /diagnoses/{id}`. This ensures we never have orphaned images sitting in S3 without a matching database record.