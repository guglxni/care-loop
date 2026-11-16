"""Patient profile and chart history."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import NotFoundError
from app.models import CarePlan, Condition, Consultation, Document, HealthReading, Medication, Patient
from app.timeutil import utcnow
from app.validation import normalize_contact_number, raise_if, reject_unknown_fields

PROFILE_FIELDS = frozenset(
    {
        "preferred_name",
        "preferred_language",
        "contact_number",
        "medical_history",
        "allergies",
        "emergency_contact",
    }
)
RECENT_READING_LIMIT = 30


def get_patient(session: Session, patient_id: str) -> Patient:
    try:
        parsed = uuid.UUID(str(patient_id))
    except (ValueError, TypeError, AttributeError):
        raise NotFoundError("Patient not found") from None
    patient = session.get(Patient, parsed)
    if patient is None:
        raise NotFoundError("Patient not found")
    return patient


def update_profile(session: Session, patient_id: str, payload: dict) -> Patient:
    patient = get_patient(session, patient_id)
    details: list[str] = []
    reject_unknown_fields(payload, PROFILE_FIELDS, details, profile=True)
    changes: dict = {}

    if "preferred_name" in payload:
        value = payload["preferred_name"]
        if not isinstance(value, str) or not value.strip():
            details.append("preferred_name is required")
        elif len(value.strip()) > 120:
            details.append("preferred_name is too long")
        else:
            changes["preferred_name"] = value.strip()

    if "preferred_language" in payload:
        value = payload["preferred_language"]
        if not isinstance(value, str) or not value.strip() or any(ch.isspace() for ch in value):
            details.append("preferred_language must be a language tag without spaces")
        elif len(value.strip()) > 35:
            details.append("preferred_language is too long")
        else:
            changes["preferred_language"] = value.strip()

    if "contact_number" in payload:
        normalized = normalize_contact_number(payload["contact_number"], details)
        if normalized is not None:
            changes["contact_number"] = normalized

    if "medical_history" in payload:
        value = payload["medical_history"]
        if value is None:
            changes["medical_history"] = ""
        elif not isinstance(value, str):
            details.append("medical_history must be a string or null")
        elif len(value) > 8000:
            details.append("medical_history is too long")
        else:
            changes["medical_history"] = value

    if "allergies" in payload:
        value = payload["allergies"]
        if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
            details.append("allergies must be a list of strings")
        else:
            changes["allergies"] = [item.strip() for item in value]

    if "emergency_contact" in payload:
        value = payload["emergency_contact"]
        if not isinstance(value, dict):
            details.append("emergency_contact must be an object")
        else:
            changes["emergency_contact"] = value

    raise_if(details)
    if not changes:
        return patient
    for key, value in changes.items():
        setattr(patient, key, value)
    patient.updated_at = utcnow()
    session.commit()
    session.refresh(patient)
    return patient


def get_history(session: Session, patient_id: str) -> dict:
    patient = get_patient(session, patient_id)
    conditions = session.scalars(
        select(Condition)
        .where(Condition.patient_id == patient.id)
        .order_by(Condition.diagnosis_date.asc())
    ).all()
    medications = session.scalars(
        select(Medication)
        .where(Medication.patient_id == patient.id)
        .order_by(Medication.medication_name.asc())
    ).all()
    readings = session.scalars(
        select(HealthReading)
        .where(HealthReading.patient_id == patient.id)
        .order_by(HealthReading.measured_at.desc(), HealthReading.created_at.desc())
        .limit(RECENT_READING_LIMIT)
    ).all()
    consultations = session.scalars(
        select(Consultation)
        .where(Consultation.patient_id == patient.id)
        .order_by(Consultation.appointment_date.desc())
    ).all()
    care_plans = session.scalars(
        select(CarePlan)
        .where(CarePlan.patient_id == patient.id)
        .order_by(CarePlan.created_at.desc())
    ).all()
    documents = session.scalars(
        select(Document)
        .where(Document.patient_id == patient.id)
        .order_by(Document.created_at.desc())
    ).all()
    return {
        "patient_id": str(patient.id),
        "conditions": [row.to_dict() for row in conditions],
        "medications": [row.to_dict() for row in medications],
        "recent_readings": [row.to_dict() for row in readings],
        "consultations": [row.to_dict() for row in consultations],
        "care_plan": [row.to_summary() for row in care_plans],
        "documents": [row.to_dict() for row in documents],
    }
