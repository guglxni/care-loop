"""Active medication schedules and adherence reports.

Adherence can only reference a medication that already exists for the patient.
It cannot create a medication or change a dosage.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AdherenceLog, Medication
from app.services.patient_service import get_patient
from app.timeutil import utcnow
from app.validation import (
    optional_text,
    parse_uuid,
    raise_if,
    reject_unknown_fields,
    require_choice,
    require_datetime,
)

ADHERENCE_FIELDS = frozenset(
    {
        "medication_id",
        "schedule_time",
        "reported_status",
        "reported_reason",
        "source",
    }
)
ADHERENCE_STATUSES = ("taken", "missed", "unknown")
ADHERENCE_SOURCES = ("app", "call_self_report", "inferred")


def list_active_medications(session: Session, patient_id: str) -> list[Medication]:
    patient = get_patient(session, patient_id)
    today = datetime.now(timezone.utc).date()
    rows = session.scalars(
        select(Medication)
        .where(Medication.patient_id == patient.id, Medication.active.is_(True))
        .order_by(Medication.medication_name.asc())
    ).all()
    return [row for row in rows if row.end_date is None or row.end_date >= today]


def record_adherence(session: Session, patient_id: str, payload: dict) -> AdherenceLog:
    patient = get_patient(session, patient_id)
    details: list[str] = []
    reject_unknown_fields(payload, ADHERENCE_FIELDS, details)
    medication_id = parse_uuid(payload.get("medication_id"), "medication_id", details)
    schedule_time = require_datetime(payload, "schedule_time", details, reject_far_future=False)
    reported_status = require_choice(payload, "reported_status", ADHERENCE_STATUSES, details)
    source = require_choice(payload, "source", ADHERENCE_SOURCES, details)
    reported_reason = optional_text(payload, "reported_reason", details, max_length=500)
    medication = None
    if medication_id is not None:
        medication = session.scalar(
            select(Medication).where(
                Medication.id == medication_id,
                Medication.patient_id == patient.id,
            )
        )
        if medication is None:
            details.append("medication_id does not match a medication for this patient")
    raise_if(details)
    assert medication is not None and schedule_time is not None
    row = AdherenceLog(
        patient_id=patient.id,
        medication_id=medication.id,
        schedule_time=schedule_time,
        reported_status=reported_status,
        reported_reason=reported_reason,
        recorded_at=utcnow(),
        source=source,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row
