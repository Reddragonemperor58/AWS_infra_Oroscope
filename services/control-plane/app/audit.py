"""Audit trail: who (doctor id) did what to which record, when, and from which IP.

Patient data is sensitive, so every endpoint that reads or changes it writes one row here.
The row is added to the SAME database session as the action and committed with it, so a
change and its audit row succeed or fail together. For reads the caller commits right away.
The log stores ids and field NAMES only, never patient values (no names, phones, findings).
"""
import uuid
from typing import Optional

from fastapi import Request
from sqlalchemy.orm import Session

from .models import AuditEvent, User


def _source_ip(request: Request) -> Optional[str]:
    event = request.scope.get("aws.event") or {}
    try:
        return event["requestContext"]["http"]["sourceIp"][:45]
    except (KeyError, TypeError):
        return None


def record(
    db: Session,
    request: Request,
    user: User,
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    patient_id: Optional[str] = None,
    detail: Optional[str] = None,
    commit: bool = False,
) -> None:
    db.add(AuditEvent(
        id=str(uuid.uuid4()),
        doctor_id=user.id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        patient_id=patient_id,
        detail=detail[:255] if detail else None,
        source_ip=_source_ip(request),
    ))
    if commit:
        db.commit()
