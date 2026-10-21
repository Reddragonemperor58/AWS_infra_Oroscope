import os
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from mangum import Mangum

from .database import get_db
from .dependencies import get_current_user
from .models import User, Patient, Diagnosis, DiagnosisStatus
from .rules_engine import get_differential_and_advise  # get_clinical_diagnosis no longer exists
from .scoring_engine import get_band, get_final_score
from . import optical

app = FastAPI(title="Oroscope Control Plane")

IMAGES_BUCKET = os.environ.get("IMAGES_BUCKET", "")
AWS_REGION = os.environ.get("AWS_REGION", "ap-south-2")
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB per image
UPLOAD_URL_TTL_SECONDS = 300

_s3 = None


def get_s3():
    """Lazy S3 client. Newer regions (ap-south-2) need SigV4 AND the regional endpoint -
    the default global endpoint would put s3.amazonaws.com in the presigned URL, which fails."""
    global _s3
    if _s3 is None:
        _s3 = boto3.client(
            "s3",
            region_name=AWS_REGION,
            endpoint_url=f"https://s3.{AWS_REGION}.amazonaws.com",
            config=Config(signature_version="s3v4"),
        )
    return _s3


# --- SCHEMAS ---
class PatientCreate(BaseModel):
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    contact_number: Optional[str] = None

class PatientResponse(PatientCreate):
    id: str
    doctor_id: str
    created_at: datetime
    updated_at: datetime
    # Tells Pydantic v2 to map from SQLAlchemy ORM objects safely
    model_config = ConfigDict(from_attributes=True)

class ClinicalMatchRequest(BaseModel):
    patient_id: str
    ulcer: str
    patch: str
    growth: str
    mucosal_condition: str
    sharp_objects: str
    pigmentation: str
    symptoms: str   # plain string — real data is "Swelling", "No Symptoms", etc., never a list
    habits: str      # same — "Tobacco Chewing", "No Habits", etc.
    oral_mapping: str

class ClinicalLookupRequest(BaseModel):
    provisional_diagnosis: str  # normally comes from the DL model — manual input until that step exists

class OpticalRequest(BaseModel):
    provisional_diagnosis: str  # same: manual input while the DL step is skipped

class DiagnosisResponse(BaseModel):
    id: str
    patient_id: str
    rules_match_result: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)
    sharp_objects: Optional[str] = None
    pigmentation: Optional[str] = None
    oral_mapping: Optional[str] = None
    advise: Optional[str] = None
    optical_deviation_index: Optional[float] = None
    final_score: Optional[float] = None

class UploadTarget(BaseModel):
    url: str
    fields: dict

class OpticalUploadResponse(BaseModel):
    image_1: UploadTarget
    image_2: UploadTarget
    max_bytes: int
    expires_in_seconds: int

class OpticalResponse(DiagnosisResponse):
    provisional_diagnosis: str
    image_analysis_band: str
    ssim_score: float
    resized: bool
    warning: Optional[str] = None


@app.get("/health")
def health_check():
    return {"status": "ok"}


def _get_owned_diagnosis(db: Session, diagnosis_id: str, user: User) -> Diagnosis:
    """BOLA guard: a diagnosis is only visible to the doctor who created it."""
    diagnosis = db.query(Diagnosis).filter(
        Diagnosis.id == diagnosis_id,
        Diagnosis.doctor_id == user.id
    ).first()
    if not diagnosis:
        raise HTTPException(status_code=404, detail="Diagnosis not found")
    return diagnosis


# --- ENDPOINTS ---
@app.post("/patients", response_model=PatientResponse)
def create_patient(
    patient: PatientCreate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    db_patient = Patient(
        id=str(uuid.uuid4()),
        doctor_id=current_user.id, # BOLA FIX
        name=patient.name,
        age=patient.age,
        gender=patient.gender,
        contact_number=patient.contact_number
    )
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)
    return db_patient

@app.get("/patients", response_model=List[PatientResponse])
def list_patients(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    return db.query(Patient).filter(Patient.doctor_id == current_user.id).all()

@app.post("/diagnoses/clinical-match", response_model=DiagnosisResponse)
def clinical_match(
    request: ClinicalMatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    patient = db.query(Patient).filter(
        Patient.id == request.patient_id,
        Patient.doctor_id == current_user.id
    ).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # State initiator only — no lookup here. Differential/advise require
    # provisional_diagnosis from the DL model, which doesn't exist yet at
    # this point in the flow. See run_clinical_lookup below.
    db_diagnosis = Diagnosis(
        id=str(uuid.uuid4()),
        patient_id=patient.id,
        doctor_id=current_user.id,
        mucosal_type=request.mucosal_condition,
        ulcer=request.ulcer,
        patch=request.patch,
        growth=request.growth,
        sharp_objects=request.sharp_objects,
        pigmentation=request.pigmentation,
        oral_mapping=request.oral_mapping,
        symptoms=request.symptoms,
        habits=request.habits,
        status=DiagnosisStatus.pending,
    )
    db.add(db_diagnosis)
    db.commit()
    db.refresh(db_diagnosis)
    return db_diagnosis


@app.patch("/diagnoses/{diagnosis_id}/clinical-lookup", response_model=DiagnosisResponse)
def run_clinical_lookup(
    diagnosis_id: str,
    request: ClinicalLookupRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    diagnosis = _get_owned_diagnosis(db, diagnosis_id, current_user)

    result = get_differential_and_advise(
        db=db,
        ulcer=diagnosis.ulcer, patch=diagnosis.patch, growth=diagnosis.growth,
        mucosal_condition=diagnosis.mucosal_type, sharp_objects=diagnosis.sharp_objects,
        pigmentation=diagnosis.pigmentation, symptoms=diagnosis.symptoms,
        habits=diagnosis.habits, oral_mapping=diagnosis.oral_mapping,
        provisional_diagnosis=request.provisional_diagnosis,
    )
    if not result:
        raise HTTPException(status_code=404, detail="No matching clinical rule found.")

    diagnosis.rules_match_result = result["differential_diagnosis"]
    diagnosis.advise = result["advise"]
    db.commit()
    db.refresh(diagnosis)
    return diagnosis


@app.post("/diagnoses/{diagnosis_id}/optical-upload-urls", response_model=OpticalUploadResponse)
def create_optical_upload_urls(
    diagnosis_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Step 1 of the optical flow: hand the client two short-lived presigned S3 POST forms.

    Images go straight to S3 (API Gateway caps requests at 10 MB, Lambda at 6 MB). The S3 keys
    are chosen HERE and stored on the diagnosis, so the analysis step never trusts a
    client-supplied key. The POST policy rejects non-image content types and files over 10 MB.
    """
    if not IMAGES_BUCKET:
        raise HTTPException(status_code=500, detail="Image bucket is not configured")
    diagnosis = _get_owned_diagnosis(db, diagnosis_id, current_user)

    keys = [f"diagnoses/{diagnosis.id}/optical_1", f"diagnoses/{diagnosis.id}/optical_2"]
    targets = []
    for key in keys:
        post = get_s3().generate_presigned_post(
            Bucket=IMAGES_BUCKET,
            Key=key,
            Conditions=[
                ["content-length-range", 1, MAX_IMAGE_BYTES],
                ["starts-with", "$Content-Type", "image/"],
            ],
            ExpiresIn=UPLOAD_URL_TTL_SECONDS,
        )
        targets.append(UploadTarget(url=post["url"], fields=post["fields"]))

    diagnosis.optical_image_1_s3_key, diagnosis.optical_image_2_s3_key = keys
    db.commit()
    return OpticalUploadResponse(
        image_1=targets[0], image_2=targets[1],
        max_bytes=MAX_IMAGE_BYTES, expires_in_seconds=UPLOAD_URL_TTL_SECONDS,
    )


def _read_s3_image(key: str) -> bytes:
    try:
        obj = get_s3().get_object(Bucket=IMAGES_BUCKET, Key=key)
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
            raise HTTPException(status_code=409, detail="Upload both images before analysis")
        raise
    if obj["ContentLength"] > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large")
    return obj["Body"].read()


@app.patch("/diagnoses/{diagnosis_id}/optical", response_model=OpticalResponse)
def run_optical_analysis(
    diagnosis_id: str,
    request: OpticalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Step 2: SSIM on the two uploaded images -> deviation -> band -> final score.

    deviation = 1 - ssim_score (SSIM is a similarity; the 0.16 / 0.20 band thresholds are
    deviations). Bands: <0.16 Variable Diagnosis, <=0.20 Borderline, else Suggestive of Dysplasia.
    """
    diagnosis = _get_owned_diagnosis(db, diagnosis_id, current_user)
    if not (diagnosis.optical_image_1_s3_key and diagnosis.optical_image_2_s3_key):
        raise HTTPException(status_code=409, detail="Request upload URLs and upload both images first")

    img1 = _read_s3_image(diagnosis.optical_image_1_s3_key)
    img2 = _read_s3_image(diagnosis.optical_image_2_s3_key)
    try:
        result = optical.calculate_ssim(img1, img2)
    except optical.OpticalImageError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    deviation = 1.0 - result["ssim_score"]
    band = get_band(deviation)
    final_score = get_final_score(request.provisional_diagnosis, deviation)

    diagnosis.optical_deviation_index = Decimal(str(round(deviation, 6)))
    warning = None
    diagnosis.final_score = final_score  # None on a lookup miss: clears any stale score
    if final_score is None:
        warning = f"'{request.provisional_diagnosis}' is not in the scoring sheet; no final score computed"
        diagnosis.status = DiagnosisStatus.pending
    else:
        diagnosis.status = DiagnosisStatus.complete  # prototype: DL step skipped, so this is the last step
    db.commit()
    db.refresh(diagnosis)

    base = DiagnosisResponse.model_validate(diagnosis).model_dump()
    return OpticalResponse(
        **base,
        provisional_diagnosis=request.provisional_diagnosis,
        image_analysis_band=band,
        ssim_score=result["ssim_score"],
        resized=result["resized"],
        warning=warning,
    )

# --- MANGUM WRAPPER ---
handler = Mangum(app)