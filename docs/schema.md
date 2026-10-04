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
- `id` (String 36, PK)
- `patient_id` (String 36, FK -> Patients.id, Not Null)
- `doctor_id` (String 36, FK -> Users.id, Not Null) - Denormalized for dashboard query speed
- `mucosal_type` (String 100, Nullable)
- `ulcer` (String 255, Nullable)
- `patch` (String 255, Nullable)
- `growth` (String 255, Nullable)
- `sharp_objects` (String 255, Nullable) - Clinical input; part of the clinical_rules match key
- `pigmentation` (String 255, Nullable) - Clinical input; part of the clinical_rules match key
- `oral_mapping` (String 255, Nullable) - Clinical input; part of the clinical_rules match key
- `symptoms` (JSONB, Nullable)
- `habits` (JSONB, Nullable)
- `dl_image_s3_key` (String 255, Nullable)
- `optical_image_1_s3_key` (String 255, Nullable)
- `optical_image_2_s3_key` (String 255, Nullable)
- `status` (ENUM: 'pending', 'processing', 'complete', 'failed', Not Null, Default: 'pending')
- `rules_match_result` (String 255, Nullable) - Stores the looked-up Differential Diagnosis
- `optical_deviation_index` (Numeric, Nullable)
- `dl_label` (String 50, Nullable)
- `dl_confidence` (Numeric, Nullable)
- `final_score` (Numeric, Nullable)
- `created_at` (DateTime, Not Null)
- `updated_at` (DateTime, Not Null)

## Clinical Rules
Reference data — the full clinical decision table, loaded once from the
source spreadsheet, not user-generated. 591,976 rows.
- `id` (Integer, PK)
- `ulcer`, `patch`, `growth`, `mucosal_condition`, `sharp_objects`, `pigmentation`, `symptoms`, `habits`, `oral_mapping` (String 255, Not Null) - the nine clinical inputs
- `provisional_diagnosis` (String 255, Not Null) - tenth input, the DL model's classification
- `differential_diagnosis` (String 255, Not Null)
- `advise` (Text, Not Null)

**Indexes:**
- `ix_patients_doctor_id`: (Patients.doctor_id)
- `ix_diagnoses_doctor_id`: (Diagnoses.doctor_id)
- `ix_diagnoses_patient_id_created_at`: Composite on (Diagnoses.patient_id, Diagnoses.created_at)
- `ix_clinical_rules_lookup`: Unique composite on all ten ClinicalRules input columns

**TODOs:**
- `updated_at` columns currently only set on INSERT. Need to configure SQLAlchemy `onupdate` hooks or Postgres triggers to refresh on UPDATE.