import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from mangum import Mangum

from .database import get_db
from .dependencies import get_current_user
from .models import User, Patient, Diagnosis, DiagnosisStatus
from .rules_engine import get_differential_and_advise  # get_clinical_diagnosis no longer exists

app = FastAPI(title="Oroscope Control Plane")

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
    provisional_diagnosis: str  # normally comes from the DL model — manual input until that Lambda exists

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

@app.get("/health")
def health_check():
    return {"status": "ok"}


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
    diagnosis = db.query(Diagnosis).filter(
        Diagnosis.id == diagnosis_id,
        Diagnosis.doctor_id == current_user.id
    ).first()
    if not diagnosis:
        raise HTTPException(status_code=404, detail="Diagnosis not found")

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

# --- MANGUM WRAPPER ---
handler = Mangum(app)