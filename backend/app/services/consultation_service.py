"""Scheduled consultations. Updating one does not create a clinical order."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import NotFoundError
from app.models import Consultation
from app.services.patient_service import get_patient
from app.timeutil import utcnow
from app.validation import raise_if, reject_unknown_fields, require_datetime

CONSULTATION_FIELDS = frozenset({"status", "appointment_date"})
CONSULTATION_STATUSES = ("scheduled", "completed", "cancelled", "rescheduled")


def get_consultation(session: Session, consultation_id: str) -> Consultation:
    try:
        parsed = uuid.UUID(str(consultation_id))
    except (ValueError, TypeError, AttributeError):
        raise NotFoundError("Consultation not found") from None
    row = session.get(Consultation, parsed)
    if row is None:
        raise NotFoundError("Consultation not found")
    return row


def next_scheduled(session: Session, patient_id: str) -> Consultation | None:
    patient = get_patient(session, patient_id)
    now = datetime.now(timezone.utc)
    return session.scalars(
        select(Consultation)
        .where(
            Consultation.patient_id == patient.id,
            Consultation.status == "scheduled",
            Consultation.appointment_date >= now,
        )
        .order_by(Consultation.appointment_date.asc())
    ).first()


def update_consultation(session: Session, consultation_id: str, payload: dict) -> Consultation:
    row = get_consultation(session, consultation_id)
    details: list[str] = []
    reject_unknown_fields(payload, CONSULTATION_FIELDS, details)
    if "status" not in payload and "appointment_date" not in payload:
        details.append("status or appointment_date is required")
    status = payload.get("status", row.status)
    if "status" in payload:
        if payload["status"] not in CONSULTATION_STATUSES:
            details.append(
                "status must be one of: scheduled, completed, cancelled, rescheduled"
            )
        else:
            status = payload["status"]
    appointment_date = row.appointment_date
    if "appointment_date" in payload:
        appointment_date = require_datetime(payload, "appointment_date", details)
    raise_if(details)
    row.status = status
    if appointment_date is not None:
        row.appointment_date = appointment_date
    row.updated_at = utcnow()
    session.commit()
    session.refresh(row)
    return row
