import enum
from sqlalchemy import Column, String, Integer, Text, ForeignKey, DateTime, Numeric, Enum, text
from sqlalchemy.dialects.postgresql import JSONB
from .database import Base

# Added `str` mixin so Pydantic and SQLAlchemy treat this transparently as a string
class DiagnosisStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    complete = "complete"
    failed = "failed"

class User(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    contact_number = Column(String(20), nullable=True)
    created_at = Column(DateTime, server_default=text("now()"), nullable=False)
    updated_at = Column(DateTime, server_default=text("now()"), nullable=False)

class Patient(Base):
    __tablename__ = "patients"
    id = Column(String(36), primary_key=True)
    doctor_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=True)
    gender = Column(String(20), nullable=True)
    contact_number = Column(String(20), nullable=True)
    created_at = Column(DateTime, server_default=text("now()"), nullable=False)
    updated_at = Column(DateTime, server_default=text("now()"), nullable=False)

class Diagnosis(Base):
    __tablename__ = "diagnoses"
    id = Column(String(36), primary_key=True)
    patient_id = Column(String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    doctor_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    mucosal_type = Column(String(100), nullable=True)
    ulcer = Column(String(255), nullable=True)
    patch = Column(String(255), nullable=True)
    growth = Column(String(255), nullable=True)
    sharp_objects = Column(String(255), nullable=True)
    pigmentation = Column(String(255), nullable=True)
    oral_mapping = Column(String(255), nullable=True)
    symptoms = Column(JSONB, nullable=True)
    habits = Column(JSONB, nullable=True)
    dl_image_s3_key = Column(String(255), nullable=True)
    optical_image_1_s3_key = Column(String(255), nullable=True)
    optical_image_2_s3_key = Column(String(255), nullable=True)
    advise = Column(Text, nullable=True)
    provisional_diagnosis = Column(String(255), nullable=True)
    
    # YOUR FIX: Explicitly name the type and remove creation ownership from SQLAlchemy
    status = Column(
        Enum(DiagnosisStatus, name="diagnosis_status", create_type=False), 
        server_default="pending", 
        nullable=False
    )
    
    rules_match_result = Column(String(255), nullable=True)
    optical_deviation_index = Column(Numeric, nullable=True)
    dl_label = Column(String(50), nullable=True)
    dl_confidence = Column(Numeric, nullable=True)
    final_score = Column(Numeric, nullable=True)
    created_at = Column(DateTime, server_default=text("now()"), nullable=False)
    updated_at = Column(DateTime, server_default=text("now()"), nullable=False)


class AuditEvent(Base):
    """Append-only record of who did what. No foreign keys on purpose: the trail must outlive
    the patient or doctor it describes."""
    __tablename__ = "audit_events"
    id = Column(String(36), primary_key=True)
    doctor_id = Column(String(36), nullable=False, index=True)
    action = Column(String(40), nullable=False)
    resource_type = Column(String(20), nullable=True)
    resource_id = Column(String(36), nullable=True)
    patient_id = Column(String(36), nullable=True, index=True)
    detail = Column(String(255), nullable=True)
    source_ip = Column(String(45), nullable=True)
    created_at = Column(DateTime, server_default=text("now()"), nullable=False)


class ProblemReport(Base):
    """A doctor's "Report a problem" message. The text is free-form and may contain patient details
    by mistake, so it lives only here (never in logs or audit rows)."""
    __tablename__ = "problem_reports"
    id = Column(String(36), primary_key=True)
    doctor_id = Column(String(36), nullable=False, index=True)
    message = Column(Text, nullable=False)
    context = Column(String(1000), nullable=True)
    created_at = Column(DateTime, server_default=text("now()"), nullable=False)
