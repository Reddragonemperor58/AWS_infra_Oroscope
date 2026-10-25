import os
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict, Field, field_validator
from mangum import Mangum

from .database import get_db
from .dependencies import get_current_user
from . import audit
from .models import User, Patient, Diagnosis, DiagnosisStatus
from .rules_engine import get_differential_and_advise  # get_clinical_diagnosis no longer exists
from .scoring_engine import get_band, get_final_score
from . import optical
from .records import router as records_router
from .support import router as support_router

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
class PatientBase(BaseModel):
    """Unconstrained shape used for RESPONSES (never reject data we already stored)."""
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    contact_number: Optional[str] = None


class PatientCreate(BaseModel):
    """Request shape. Limits mirror the DB column sizes so oversized input is a clean 422,
    not a database error, and cap how much junk one request can push into the DB."""
    name: str = Field(min_length=1, max_length=100)
    age: Optional[int] = Field(default=None, ge=0, le=120)
    gender: Optional[str] = Field(default=None, max_length=20)
    contact_number: Optional[str] = Field(default=None, max_length=20)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank")
        return v


class PatientResponse(PatientBase):
    id: str
    doctor_id: str
    created_at: datetime
    updated_at: datetime
    # Tells Pydantic v2 to map from SQLAlchemy ORM objects safely
    model_config = ConfigDict(from_attributes=True)

class ClinicalMatchRequest(BaseModel):
    patient_id: str = Field(max_length=36)
    ulcer: str = Field(max_length=255)
    patch: str = Field(max_length=255)
    growth: str = Field(max_length=255)
    mucosal_condition: str = Field(max_length=255)
    sharp_objects: str = Field(max_length=255)
    pigmentation: str = Field(max_length=255)
    symptoms: str = Field(max_length=255)   # plain string - real data is "Swelling", "No Symptoms", etc.
    habits: str = Field(max_length=255)      # same - "Tobacco Chewing", "No Habits", etc.
    oral_mapping: str = Field(max_length=255)

class ClinicalLookupRequest(BaseModel):
    provisional_diagnosis: str = Field(max_length=255)  # normally comes from the DL model — manual input until that step exists

class OpticalRequest(BaseModel):
    provisional_diagnosis: str = Field(max_length=255)  # same: manual input while the DL step is skipped

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

class DlUploadResponse(BaseModel):
    image: UploadTarget
    max_bytes: int
    expires_in_seconds: int

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
    request: Request,
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
    audit.record(db, request, current_user, "patient.create", "patient", db_patient.id, db_patient.id)
    db.commit()
    db.refresh(db_patient)
    return db_patient

@app.post("/diagnoses/clinical-match", response_model=DiagnosisResponse)
def clinical_match(
    http: Request,
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
    audit.record(db, http, current_user, "diagnosis.create", "diagnosis", db_diagnosis.id, patient.id)
    db.commit()
    db.refresh(db_diagnosis)
    return db_diagnosis


@app.patch("/diagnoses/{diagnosis_id}/clinical-lookup", response_model=DiagnosisResponse)
def run_clinical_lookup(
    http: Request,
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

    diagnosis.provisional_diagnosis = request.provisional_diagnosis
    diagnosis.rules_match_result = result["differential_diagnosis"]
    diagnosis.advise = result["advise"]
    audit.record(db, http, current_user, "diagnosis.lookup", "diagnosis", diagnosis.id, diagnosis.patient_id)
    db.commit()
    db.refresh(diagnosis)
    return diagnosis


def _presigned_image_post(key: str) -> UploadTarget:
    """Short-lived presigned S3 POST for one image: size and type are enforced by S3 itself."""
    post = get_s3().generate_presigned_post(
        Bucket=IMAGES_BUCKET,
        Key=key,
        Conditions=[
            ["content-length-range", 1, MAX_IMAGE_BYTES],
            ["starts-with", "$Content-Type", "image/"],
        ],
        ExpiresIn=UPLOAD_URL_TTL_SECONDS,
    )
    return UploadTarget(url=post["url"], fields=post["fields"])


@app.post("/diagnoses/{diagnosis_id}/dl-upload-url", response_model=DlUploadResponse)
def create_dl_upload_url(
    http: Request,
    diagnosis_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """The close-up photo meant for the deep-learning classifier. The model is not connected yet,
    so for now the photo is only stored (key chosen here, never by the client) and the provisional
    diagnosis is still picked by the doctor."""
    if not IMAGES_BUCKET:
        raise HTTPException(status_code=500, detail="Image bucket is not configured")
    diagnosis = _get_owned_diagnosis(db, diagnosis_id, current_user)
    key = f"diagnoses/{diagnosis.id}/dl_image"
    target = _presigned_image_post(key)
    diagnosis.dl_image_s3_key = key
    audit.record(db, http, current_user, "diagnosis.dl_upload_url", "diagnosis", diagnosis.id, diagnosis.patient_id)
    db.commit()
    return DlUploadResponse(image=target, max_bytes=MAX_IMAGE_BYTES, expires_in_seconds=UPLOAD_URL_TTL_SECONDS)


@app.post("/diagnoses/{diagnosis_id}/optical-upload-urls", response_model=OpticalUploadResponse)
def create_optical_upload_urls(
    http: Request,
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
    audit.record(db, http, current_user, "diagnosis.upload_urls", "diagnosis", diagnosis.id, diagnosis.patient_id)
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
    http: Request,
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

    diagnosis.provisional_diagnosis = request.provisional_diagnosis
    diagnosis.optical_deviation_index = Decimal(str(round(deviation, 6)))
    warning = None
    if final_score is None:
        warning = f"'{request.provisional_diagnosis}' is not in the scoring sheet; no final score computed"
    else:
        diagnosis.final_score = final_score
        diagnosis.status = DiagnosisStatus.complete  # prototype: DL step skipped, so this is the last step
    audit.record(db, http, current_user, "diagnosis.optical", "diagnosis", diagnosis.id, diagnosis.patient_id)
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

app.include_router(records_router)
app.include_router(support_router)

# --- MANGUM WRAPPER ---
handler = Mangum(app)
