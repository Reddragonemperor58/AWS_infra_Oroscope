"""Doctors can report a problem from the app. The report is stored in the database; a log line
with the report id (never the text) trips a CloudWatch alarm, which emails the owner."""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from . import audit
from .database import get_db
from .dependencies import get_current_user
from .models import ProblemReport, User

router = APIRouter()


class ProblemReportIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    context: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("message")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message must not be blank")
        return v


class ProblemReportOut(BaseModel):
    id: str


@router.post("/problem-reports", response_model=ProblemReportOut)
def create_problem_report(
    body: ProblemReportIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = ProblemReport(
        id=str(uuid.uuid4()),
        doctor_id=current_user.id,
        message=body.message,
        context=body.context,
    )
    db.add(report)
    audit.record(db, request, current_user, "report.create", "report", report.id)
    db.commit()
    # The marker below is what the CloudWatch metric filter matches (infra/monitoring_reports.tf).
    # Only ids are printed: the message itself may contain patient details.
    print(f"PROBLEM_REPORT id={report.id} doctor={current_user.id}")
    return ProblemReportOut(id=report.id)
