"""Allow-listed context packet for a voice check-in.

The packet names the patient, today's medicine times, the latest readings,
and the next visit. It does not include the chart narrative, documents,
other patients, or adherence history.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import HealthReading
from app.phones import resolve_patient_id_by_phone
from app.services.consultation_service import next_scheduled
from app.services.medication_service import list_active_medications
from app.services.patient_service import get_patient
from app.timeutil import json_number, to_iso
from app.validation import raise_if

_UTC_WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)

PURPOSES = (
    "glucose_check",
    "bp_check",
    "medication_check",
    "appointment_reminder",
    "general",
    "onboarding",
)

VOICE_INSTRUCTIONS = (
    "Record what the patient reports. Do not diagnose, prescribe, or change medicines. "
    "Ask a clinician to review urgent concerns."
)


def get_bolna_context(
    session: Session,
    patient_id: str,
    purpose: str | None,
    destination: str | None = None,
) -> dict:
    """Return the allow-listed chart for this check-in.

    A destination that is linked in patient_phone_links selects that chart.
    The path patient is used only when the destination is absent or unlinked.
    """
    linked_id = resolve_patient_id_by_phone(session, destination)
    patient = get_patient(session, str(linked_id) if linked_id is not None else patient_id)
    details: list[str] = []
    if purpose not in PURPOSES:
        details.append(
            "purpose must be one of: glucose_check, bp_check, medication_check, "
            "appointment_reminder, general, onboarding"
        )
    raise_if(details)

    chart_id = str(patient.id)
    packet: dict = {
        "patient_id": chart_id,
        "preferred_name": patient.preferred_name,
        "preferred_language": patient.preferred_language,
        "purpose": purpose,
        "due_medications": _due_medications(session, chart_id),
        "instructions": VOICE_INSTRUCTIONS,
    }
    glucose = _latest_glucose(session, patient.id)
    if glucose is not None:
        packet["latest_glucose"] = glucose
    pressure = _latest_blood_pressure(session, patient.id)
    if pressure is not None:
        packet["latest_blood_pressure"] = pressure
    consultation = next_scheduled(session, chart_id)
    if consultation is not None:
        packet["next_consultation"] = {
            "clinician": consultation.clinician,
            "appointment_date": to_iso(consultation.appointment_date),
            "consultation_type": consultation.consultation_type,
        }
    return packet


def _due_medications(session: Session, patient_id: str) -> list[dict]:
    due: list[dict] = []
    for medication in list_active_medications(session, patient_id):
        times = _times_for_today(medication.schedule)
        if not times:
            continue
        due.append({"name": medication.medication_name, "times": times})
    due.sort(key=lambda item: item["name"])
    return due


def _times_for_today(schedule: object) -> list[str]:
    times: list = []
    weekdays: list | None = None
    if isinstance(schedule, list):
        times = schedule
    elif isinstance(schedule, dict):
        raw_times = schedule.get("times", [])
        times = raw_times if isinstance(raw_times, list) else []
        raw_days = schedule.get("weekdays")
        if isinstance(raw_days, list):
            weekdays = raw_days
    else:
        return []
    if weekdays:
        today = _UTC_WEEKDAYS[datetime.now(timezone.utc).weekday()]
        allowed = {str(day).strip().lower() for day in weekdays}
        if today not in allowed:
            return []
    return [item for item in times if isinstance(item, str) and item.strip()]


def _latest_glucose(session: Session, patient_id) -> dict | None:
    row = session.scalars(
        select(HealthReading)
        .where(
            HealthReading.patient_id == patient_id,
            HealthReading.measurement_type == "blood_glucose",
            HealthReading.data_quality == "valid",
        )
        .order_by(HealthReading.measured_at.desc(), HealthReading.created_at.desc())
    ).first()
    if row is None:
        return None
    return {
        "value": json_number(row.value),
        "unit": row.unit,
        "context": row.measurement_context,
        "source": row.source,
        "measured_at": to_iso(row.measured_at),
    }


def _latest_blood_pressure(session: Session, patient_id) -> dict | None:
    systolic = session.scalars(
        select(HealthReading)
        .where(
            HealthReading.patient_id == patient_id,
            HealthReading.measurement_type == "systolic_blood_pressure",
            HealthReading.data_quality == "valid",
        )
        .order_by(HealthReading.measured_at.desc(), HealthReading.created_at.desc())
    ).first()
    if systolic is None:
        return None
    diastolic = session.scalar(
        select(HealthReading).where(
            HealthReading.patient_id == patient_id,
            HealthReading.measurement_type == "diastolic_blood_pressure",
            HealthReading.measured_at == systolic.measured_at,
            HealthReading.data_quality == "valid",
        )
    )
    diastolic_value = diastolic.value if diastolic is not None else systolic.secondary_value
    if diastolic_value is None:
        return None
    return {
        "systolic": json_number(systolic.value),
        "diastolic": json_number(diastolic_value),
        "unit": systolic.unit,
        "source": systolic.source,
        "measured_at": to_iso(systolic.measured_at),
    }
