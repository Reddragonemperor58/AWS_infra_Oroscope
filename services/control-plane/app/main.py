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
from .rules_engine import get_clinical_diagnosis, get_differential_and_advise

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
    symptoms: Optional[List[str]] = None
    habits: Optional[List[str]] = None

class DiagnosisResponse(BaseModel):
    id: str
    patient_id: str
    rules_match_result: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


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
    # 1. Verify patient exists AND belongs to the calling doctor
    patient = db.query(Patient).filter(
        Patient.id == request.patient_id, 
        Patient.doctor_id == current_user.id
    ).first()
    
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
        
    # 2. Run the isolated medical math
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
        
    # 3. Create the Diagnosis record (State initiator)
    db_diagnosis = Diagnosis(
        id=str(uuid.uuid4()),
        patient_id=patient.id,
        doctor_id=current_user.id,
        mucosal_type=request.mucosal_condition,
        ulcer=request.ulcer,
        patch=request.patch,
        growth=request.growth,
        symptoms=request.symptoms,
        habits=request.habits,
        rules_match_result=result["provisional_diagnosis"], 
        status=DiagnosisStatus.pending  # Explicitly use the Enum member
    )
    
    db.add(db_diagnosis)
    db.commit()
    db.refresh(db_diagnosis)
    
    return db_diagnosis

# --- MANGUM WRAPPER ---
handler = Mangum(app)