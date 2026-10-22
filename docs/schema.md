# Oroscope Database Schema

## Users

- `id` (String 36, PK) - Cognito Sub
- `email` (String 255, Unique, Not Null)
- `contact_number` (String 20, Nullable)
- `created_at` (DateTime, Not Null)
- `updated_at` (DateTime, Not Null)

## Patients

- `id` (String 36, PK)
- `doctor_id` (String 36, FK -> Users.id, Not Null) - Denormalized for dashboard query speed
- `name` (String 100, Not Null)
- `age` (Integer, Nullable)
- `gender` (String 20, Nullable)
- `contact_number` (String 20, Nullable)
- `created_at` (DateTime, Not Null)
- `updated_at` (DateTime, Not Null)

## Diagnoses

A diagnosis is built up in steps (state machine, ADR 0007): clinical-match creates the row, clinical-lookup attaches the rules result, optical-upload-urls + optical attach the image analysis and score.

- `id` (String 36, PK)
- `patient_id` (String 36, FK -> Patients.id, Not Null)
- `doctor_id` (String 36, FK -> Users.id, Not Null) - Denormalized for dashboard query speed
- `mucosal_type` (String 100, Nullable)
- `ulcer` (String 255, Nullable)
- `patch` (String 255, Nullable)
- `growth` (String 255, Nullable)
- `sharp_objects` (String 255, Nullable) - Clinical input; part of the clinical_rules match key
- `pigmentation` (String 255, Nullable) - Clinical input; part of the clinical_rules match key
- `oral_mapping` (String 255, Nullable) - Clinical input; part of the clinical_rules match key. Single canonical value; "Multiple areas" when the doctor ticks two or more
- `symptoms` (String 255, Nullable) - Single canonical value (e.g. "Swelling", "No Symptoms"), not a list. "Multiple symptoms" when the doctor ticks two or more (the UI collapses them)
- `habits` (String 255, Nullable) - Single canonical value (e.g. "Tobacco Chewing", "No Habits"), not a list. "Multiple habits" when the doctor ticks two or more
- `dl_image_s3_key` (String 255, Nullable) - Unused in the prototype (DL step skipped)
- `optical_image_1_s3_key` (String 255, Nullable) - Set by POST /diagnoses/{id}/optical-upload-urls (server-generated: `diagnoses/{id}/optical_1`); never client-supplied
- `optical_image_2_s3_key` (String 255, Nullable) - Same, `diagnoses/{id}/optical_2`
- `status` (ENUM: 'pending', 'processing', 'complete', 'failed', Not Null, Default: 'pending') - Set to 'complete' when the optical step computes a final score (prototype: last step, since DL is skipped)
- `rules_match_result` (String 255, Nullable) - Holds the looked-up Differential Diagnosis, via PATCH /diagnoses/{id}/clinical-lookup
- `advise` (Text, Nullable) - Holds the looked-up Advise text, same endpoint
- `optical_deviation_index` (Numeric, Nullable) - `1 - SSIM` of the two optical images (SSIM is a similarity; this is the deviation). Set by PATCH /diagnoses/{id}/optical
- `dl_label` (String 50, Nullable) - Unused in the prototype (DL step skipped)
- `dl_confidence` (Numeric, Nullable) - Unused in the prototype (DL step skipped)
- `final_score` (Numeric, Nullable) - 0-5 score from `scoring_engine.py`: lookup of (provisional diagnosis, image-analysis band). Null if the provisional diagnosis is not in the scoring sheet. Set by PATCH /diagnoses/{id}/optical
- `created_at` (DateTime, Not Null)
- `updated_at` (DateTime, Not Null)

`provisional_diagnosis` is **not stored** on Diagnoses. In the prototype it is request input to the clinical-lookup and optical steps. Once the DL step exists it will come from the model (see TODOs).

## Clinical Rules

Reference data - the full clinical decision table, loaded once from
`Final  DD for new software.xlsx`, not user-generated. 591,976 rows.

- `id` (Integer, PK)
- `ulcer`, `patch`, `growth`, `mucosal_condition`, `sharp_objects`, `pigmentation`, `symptoms`, `habits`, `oral_mapping` (String 255, Not Null) - nine clinical inputs
- `provisional_diagnosis` (String 255, Not Null) - tenth input; the DL model's classification, supplied manually until the DL step exists. Source data has inconsistent case and whitespace (e.g. "SPECKLED LEUKOPLAKIA", " Speckled Leukoplakia"), so the lookup compares `upper(btrim(provisional_diagnosis))` (zero conflicts proven across the table); includes the rule category "VARIABLE DIAGNOSIS" (2,464 rows: no lesion, symptom + habit)
- `differential_diagnosis` (String 255, Not Null)
- `advise` (Text, Not Null)

## Scoring (not a table)

The optical scoring table (`Scoring_excel_0_to_5_1.xlsx`: Provisional Diagnosis x image-analysis band -> Score 0-5) is 78 rows (26 diagnoses x 3 bands) plus one dentist-confirmed category (Variable Diagnosis x 3 bands = 0), 81 entries in total for 27 diagnoses, so it lives in code, not the database: `services/control-plane/app/scoring_engine.py`, generated from the Excel by script.

- Bands from the deviation: `< 0.16` Variable Diagnosis; `<= 0.20` Borderline; otherwise Suggestive of Dysplasia.
- Diagnosis names match case-, whitespace- and apostrophe-insensitively.
- Source-sheet conflict resolved by the owner: Fibroma + Suggestive of Dysplasia = 3 (the sheet held both 2 and 3).
- "Variable Diagnosis" (a clinical_rules category, not in the Excel) scores 0 in every band, dentist-confirmed.
- Aliases in the code, **UNCONFIRMED** clinically: IRRITATION FIBROMA -> Fibroma; APTHOUS STOMATITIS -> Apthous Ulcer.

**Indexes:**

- `ix_patients_doctor_id`: (Patients.doctor_id)
- `ix_diagnoses_doctor_id`: (Diagnoses.doctor_id)
- `ix_diagnoses_patient_id_created_at`: Composite on (Diagnoses.patient_id, Diagnoses.created_at)
- `ix_clinical_rules_lookup`: Unique composite on all ten ClinicalRules input columns (enforces the proven one-answer-per-combination guarantee at the database level)

**TODOs:**

- Decide `ON DELETE` behaviour for the `doctor_id` foreign keys (Patients and Diagnoses reference Users). Deleting a patient currently cascades to its diagnoses; deleting a user is not defined.
- Confirm that "two or more ticks -> Multiple symptoms / habits / areas" matches the original app.
- `updated_at` columns currently only set on INSERT. Need to configure SQLAlchemy `onupdate` hooks or Postgres triggers to refresh on UPDATE.
- Decide where `provisional_diagnosis` is persisted once the DL step exists (a new column vs. `dl_label`). Until then it is request input, so a Diagnosis row does not record which diagnosis its score was computed from.
- Confirm the two scoring aliases (IRRITATION FIBROMA, APTHOUS STOMATITIS) and the 7 scored diagnoses with no clinical_rules rows (Fissured Tongue, Geographic Tongue, Herpetic Stomatitis, Melanin Patches, Severe Dysplasia, Smoker's Palate, Verrucous Carcinoma) with the dentist.