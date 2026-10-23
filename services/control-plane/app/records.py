"""Record-keeping endpoints: search and page patients, edit a patient, open a patient's case
history, and open one diagnosis with short-lived links to its two photos.

Every query filters on the calling doctor (BOLA guard): someone else's id returns 404, the same
as a missing one. API Gateway has already verified the JWT before any of this runs.
"""
import os
from datetime import datetime
from typing import List, Optional

import boto3
from botocore.client import Config
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from .database import get_db
from .dependencies import get_current_user
from .models import Diagnosis, Patient, User
from .scoring_engine import get_band

router = APIRouter()

IMAGES_BUCKET = os.environ.get("IMAGES_BUCKET", "")
AWS_REGION = os.environ.get("AWS_REGION", "ap-south-2")
PHOTO_LINK_TTL_SECONDS = 600

_s3 = None


def _s3_client():
    # Same settings as main.get_s3 (regional endpoint + SigV4, needed in ap-south-2). Kept here
    # so this module does not import main.py (which imports this module).
    global _s3
    if _s3 is None:
        _s3 = boto3.client(
            "s3",
            region_name=AWS_REGION,
            endpoint_url=f"https://s3.{AWS_REGION}.amazonaws.com",
            config=Config(signature_version="s3v4"),
        )
    return _s3


def _photo_link(key: Optional[str]) -> Optional[str]:
    if not key or not IMAGES_BUCKET:
        return None
    return _s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": IMAGES_BUCKET, "Key": key},
        ExpiresIn=PHOTO_LINK_TTL_SECONDS,
    )


# --- SCHEMAS ---
class PatientOut(BaseModel):
    id: str
    doctor_id: str
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    contact_number: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PatientUpdate(BaseModel):
    """Only the fields that are sent are changed. null clears age, gender or contact number."""
    name: Optional[str] = Field(default=None, max_length=100)
    age: Optional[int] = Field(default=None, ge=0, le=120)
    gender: Optional[str] = Field(default=None, max_length=20)
    contact_number: Optional[str] = Field(default=None, max_length=20)


class DiagnosisSummary(BaseModel):
    id: str
    status: str
    created_at: datetime
    provisional_diagnosis: Optional[str] = None
    image_analysis_band: Optional[str] = None
    final_score: Optional[float] = None


class DiagnosisDetail(DiagnosisSummary):
    patient_id: str
    updated_at: datetime
    ulcer: Optional[str] = None
    patch: Optional[str] = None
    growth: Optional[str] = None
    mucosal_condition: Optional[str] = None
    sharp_objects: Optional[str] = None
    pigmentation: Optional[str] = None
    symptoms: Optional[str] = None
    habits: Optional[str] = None
    oral_mapping: Optional[str] = None
    rules_match_result: Optional[str] = None
    advise: Optional[str] = None
    optical_deviation_index: Optional[float] = None
    image_1_url: Optional[str] = None
    image_2_url: Optional[str] = None
    photo_link_expires_in_seconds: int = PHOTO_LINK_TTL_SECONDS


# --- HELPERS ---
def _owned_patient(db: Session, patient_id: str, user: User) -> Patient:
    patient = db.query(Patient).filter(Patient.id == patient_id, Patient.doctor_id == user.id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


def _band(diagnosis: Diagnosis) -> Optional[str]:
    if diagnosis.optical_deviation_index is None:
        return None
    return get_band(float(diagnosis.optical_deviation_index))


def _status(diagnosis: Diagnosis) -> str:
    return getattr(diagnosis.status, "value", str(diagnosis.status))


def _summary(d: Diagnosis) -> DiagnosisSummary:
    return DiagnosisSummary(
        id=d.id,
        status=_status(d),
        created_at=d.created_at,
        provisional_diagnosis=getattr(d, "provisional_diagnosis", None),
        image_analysis_band=_band(d),
        final_score=float(d.final_score) if d.final_score is not None else None,
    )


# --- ENDPOINTS ---
@router.get("/patients", response_model=List[PatientOut])
def list_patients(
    q: Optional[str] = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The calling doctor's patients, A to Z, optionally filtered by name or phone."""
    query = db.query(Patient).filter(Patient.doctor_id == current_user.id)
    text = (q or "").strip()
    if text:
        # strpos (plain substring test) instead of ILIKE: nothing to escape, so "50%" or "a_b" are
        # searched literally, and no backslash reaches the RDS Data API (its SQL parser chokes on
        # ESCAPE '\', which broke the next parameter in the statement).
        query = query.filter(or_(
            func.strpos(func.lower(Patient.name), func.lower(text)) > 0,
            func.strpos(func.coalesce(Patient.contact_number, ""), text) > 0,
        ))
    return query.order_by(func.lower(Patient.name), Patient.id).offset(offset).limit(limit).all()


@router.get("/patients/{patient_id}", response_model=PatientOut)
def get_patient(patient_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _owned_patient(db, patient_id, current_user)


@router.patch("/patients/{patient_id}", response_model=PatientOut)
def update_patient(
    patient_id: str,
    update: PatientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    patient = _owned_patient(db, patient_id, current_user)
    changes = update.model_dump(exclude_unset=True)
    if "name" in changes:
        name = (changes["name"] or "").strip()
        if not name:
            raise HTTPException(status_code=422, detail="Name cannot be empty")
        changes["name"] = name
    for field, value in changes.items():
        setattr(patient, field, value)
    if changes:
        patient.updated_at = func.now()  # the column only has an insert-time default
    db.commit()
    db.refresh(patient)
    return patient


@router.get("/patients/{patient_id}/diagnoses", response_model=List[DiagnosisSummary])
def list_patient_diagnoses(
    patient_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """One patient's cases, newest first."""
    patient = _owned_patient(db, patient_id, current_user)
    rows = (
        db.query(Diagnosis)
        .filter(Diagnosis.patient_id == patient.id, Diagnosis.doctor_id == current_user.id)
        .order_by(Diagnosis.created_at.desc(), Diagnosis.id)
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_summary(d) for d in rows]


@router.get("/diagnoses/{diagnosis_id}", response_model=DiagnosisDetail)
def get_diagnosis(diagnosis_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """One case in full, with short-lived links to its photos (they may no longer exist in S3
    once the retention period has passed; the page shows that case gracefully)."""
    d = db.query(Diagnosis).filter(Diagnosis.id == diagnosis_id, Diagnosis.doctor_id == current_user.id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Diagnosis not found")
    base = _summary(d).model_dump()
    return DiagnosisDetail(
        **base,
        patient_id=d.patient_id,
        updated_at=d.updated_at,
        ulcer=d.ulcer,
        patch=d.patch,
        growth=d.growth,
        mucosal_condition=d.mucosal_type,
        sharp_objects=d.sharp_objects,
        pigmentation=d.pigmentation,
        symptoms=d.symptoms,
        habits=d.habits,
        oral_mapping=d.oral_mapping,
        rules_match_result=d.rules_match_result,
        advise=d.advise,
        optical_deviation_index=float(d.optical_deviation_index) if d.optical_deviation_index is not None else None,
        image_1_url=_photo_link(d.optical_image_1_s3_key),
        image_2_url=_photo_link(d.optical_image_2_s3_key),
    )
