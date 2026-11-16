"""Known-patient, known-reason context for one outbound call.

The packet is built from the chart. It does not include the medical-history
narrative. A missing patient, an unknown call type, or a chart that cannot
support the reason raises ConflictError (HTTP 409). Callers must not dial
when this function fails.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.demo.ravi import SCHEDULED_UNCONFIRMED, classify_adherence
from app.errors import ConflictError, NotFoundError
from app.models import (
    AdherenceLog,
    CarePlan,
    Condition,
    Consultation,
    HealthReading,
    Medication,
    VoiceCall,
)
from app.services.patient_service import get_patient

CALL_TYPES = ("onboarding", "medication_adherence", "weekly_checkin")
LANGUAGE_POLICY = (
    "Follow the language the person is speaking. Start in the chart language. "
    "Switch if they switch. English, Hindi, and Kannada are supported."
)
SUPPORTED_LANGUAGES = "English, Hindi, Kannada"
CLINIC_TZ = timezone(timedelta(hours=5, minutes=30))
_NOT_PLACED = "Outbound call was not placed"
_WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
_CONDITION_LABELS = {
    "type_2_diabetes": "type 2 diabetes",
    "hypertension": "hypertension",
}
_CONDITION_ORDER = {"type_2_diabetes": 0, "hypertension": 1}
_ALIASES = {
    "onboarding": "onboarding",
    "medication": "medication_adherence",
    "medication_followup": "medication_adherence",
    "medication_adherence": "medication_adherence",
    "medication_check": "medication_adherence",
    "weekly": "weekly_checkin",
    "weekly_checkin": "weekly_checkin",
    "glucose_check": "weekly_checkin",
    "bp_check": "weekly_checkin",
}


def build_outbound_context(session: Session, patient_id: str, call_type: str) -> dict:
    """Read the chart and return the outbound context fields.

    call_type is onboarding, medication_adherence, or weekly_checkin.
    Demo scenario names medication and weekly are accepted and returned
    as those canonical types.
    """
    canonical = canonical_call_type(call_type)
    patient = _patient(session, patient_id)
    name = _required_text(patient.preferred_name, "patient_name")
    language = _required_text(patient.preferred_language, "preferred_language")
    clinic, doctor = _clinic_and_doctor(session, patient.id)
    _require_clinic_and_doctor(clinic, doctor)
    assert clinic is not None and doctor is not None

    if canonical == "onboarding":
        reason, objective, relevant = _onboarding(session, patient.id, name, clinic, doctor)
    elif canonical == "medication_adherence":
        reason, objective, relevant = _medication(session, patient.id, name)
    else:
        reason, objective, relevant = _weekly(session, patient.id, name)

    return {
        "patient_id": str(patient.id),
        "patient_name": name,
        "call_type": canonical,
        "call_reason": reason,
        "call_objective": objective,
        "preferred_language": language,
        "language_policy": LANGUAGE_POLICY,
        "supported_languages": SUPPORTED_LANGUAGES,
        "clinic_name": clinic,
        "doctor_name": doctor,
        "relevant_context": relevant,
    }


def canonical_call_type(call_type: object) -> str:
    """Map a scenario or purpose onto one outbound call type, or reject it."""
    if isinstance(call_type, str):
        mapped = _ALIASES.get(call_type.strip().lower())
    else:
        mapped = None
    if mapped is None:
        raise ConflictError(
            f"{_NOT_PLACED} because it has no known reason.",
            [f"call_type must be one of: {', '.join(CALL_TYPES)}"],
        )
    return mapped


def _patient(session: Session, patient_id: str):
    try:
        return get_patient(session, str(patient_id).strip())
    except NotFoundError as exc:
        raise ConflictError(
            f"{_NOT_PLACED} because the patient was not found.",
            ["patient_id does not match a chart"],
        ) from exc


def _required_text(value: object, field: str) -> str:
    text = _text(value)
    if text is None:
        raise ConflictError(
            f"{_NOT_PLACED} because the call context was incomplete.",
            [f"{field} is not recorded"],
        )
    return text


def _require_clinic_and_doctor(clinic: str | None, doctor: str | None) -> None:
    details: list[str] = []
    if not clinic:
        details.append("clinic_name is not recorded")
    if not doctor:
        details.append("doctor_name is not recorded")
    if details:
        raise ConflictError(
            f"{_NOT_PLACED} because the clinic or doctor is not on the chart.",
            details,
        )


def _clinic_and_doctor(session: Session, patient_id: uuid.UUID) -> tuple[str | None, str | None]:
    plans = list(session.scalars(select(CarePlan).where(CarePlan.patient_id == patient_id)).all())
    clinic = None
    doctor = None
    for plan in plans:
        protocol = plan.escalation_protocol if isinstance(plan.escalation_protocol, dict) else {}
        clinic = clinic or _text(protocol.get("clinic"))
        doctor = doctor or _text(protocol.get("doctor")) or _text(plan.clinician)
    if doctor is None:
        names: list[str] = []
        conditions = session.scalars(select(Condition).where(Condition.patient_id == patient_id)).all()
        for row in conditions:
            name = _text(row.treating_clinician)
            if name and name not in names:
                names.append(name)
        if len(names) == 1:
            doctor = names[0]
    if doctor is None:
        upcoming = session.scalars(
            select(Consultation)
            .where(Consultation.patient_id == patient_id, Consultation.status == "scheduled")
            .order_by(Consultation.appointment_date.asc())
        ).first()
        if upcoming is not None:
            doctor = _text(upcoming.clinician)
    return clinic, doctor


def _onboarding(
    session: Session,
    patient_id: uuid.UUID,
    name: str,
    clinic: str,
    doctor: str,
) -> tuple[str, str, str]:
    if _consent_recorded(session, patient_id):
        raise ConflictError(
            f"{_NOT_PLACED} because consent is already recorded.",
            ["onboarding requires consent that is not yet recorded"],
        )
    conditions = _condition_phrase(session, patient_id)
    reason = (
        f"Onboarding for {name} at {clinic} with {doctor}. Consent is not yet recorded."
    )
    objective = (
        f"Introduce {name} to voice check-ins at {clinic} with {doctor} "
        "and ask for consent. Ask their preferred language and record it. "
        "Consent is not yet recorded."
    )
    relevant = (
        f"Clinic: {clinic}. Doctor: {doctor}. Conditions: {conditions}. "
        "Consent is not yet recorded."
    )
    return reason, objective, relevant


def _medication(session: Session, patient_id: uuid.UUID, name: str) -> tuple[str, str, str]:
    doses = _unconfirmed_evening_doses(session, patient_id)
    if not doses:
        raise ConflictError(
            f"{_NOT_PLACED} because no unconfirmed evening medication is scheduled.",
            ["medication_adherence needs an unconfirmed evening dose"],
        )
    phrase = _join([_dose_phrase(dose) for dose in doses])
    reason = f"Medication adherence for the unconfirmed evening {phrase}."
    objective = (
        f"Ask {name} whether the evening {phrase} was taken. "
        "Record only what they report. event_status unconfirmed."
    )
    relevant = f"Evening medication {phrase}. event_status unconfirmed."
    return reason, objective, relevant


def _weekly(session: Session, patient_id: uuid.UUID, name: str) -> tuple[str, str, str]:
    readings = list(
        session.scalars(
            select(HealthReading).where(
                HealthReading.patient_id == patient_id,
                HealthReading.data_quality == "valid",
            )
        ).all()
    )
    glucose_rows = [row for row in readings if row.measurement_type == "blood_glucose"]
    pressure_rows = [row for row in readings if row.measurement_type == "systolic_blood_pressure"]
    plans = list(session.scalars(select(CarePlan).where(CarePlan.patient_id == patient_id)).all())
    missing_glucose = _missing_days(plans, "blood_glucose", _reading_days(glucose_rows))
    missing_pressure = _missing_days(plans, "blood_pressure", _reading_days(pressure_rows))
    relevant_parts = [
        f"Recent glucose readings: {len(glucose_rows)}.",
        f"Recent blood pressure readings: {len(pressure_rows)}.",
    ]
    if missing_glucose:
        relevant_parts.append(
            "Missing scheduled glucose readings: " + ", ".join(missing_glucose) + "."
        )
    if missing_pressure:
        relevant_parts.append(
            "Missing scheduled blood pressure readings: " + ", ".join(missing_pressure) + "."
        )
    relevant = " ".join(relevant_parts)
    reason = f"Weekly check-in for {name} about glucose and blood pressure."
    if missing_glucose:
        reason += " Missing scheduled glucose readings: " + ", ".join(missing_glucose) + "."
    if missing_pressure:
        reason += (
            " Missing scheduled blood pressure readings: " + ", ".join(missing_pressure) + "."
        )
    objective = (
        f"Ask {name} about recent glucose and blood pressure. {relevant} "
        "Record only numbers they report."
    )
    return reason, objective, relevant


def _unconfirmed_evening_doses(session: Session, patient_id: uuid.UUID) -> list[dict]:
    today = datetime.now(CLINIC_TZ).date()
    medications = session.scalars(
        select(Medication).where(Medication.patient_id == patient_id, Medication.active.is_(True))
    ).all()
    logs = list(
        session.scalars(select(AdherenceLog).where(AdherenceLog.patient_id == patient_id)).all()
    )
    doses: list[dict] = []
    for medication in medications:
        if medication.end_date is not None and medication.end_date < today:
            continue
        for clock in _evening_clocks(medication.schedule):
            status = classify_adherence(_logs_at_clock(logs, medication.id, clock))
            if status != SCHEDULED_UNCONFIRMED:
                continue
            doses.append(
                {
                    "name": medication.medication_name.strip(),
                    "dosage": medication.prescribed_dosage.strip(),
                    "time": clock,
                }
            )
    doses.sort(key=lambda item: (item["time"], item["name"]))
    return doses


def _evening_clocks(schedule: object) -> list[str]:
    times, weekdays = _schedule_parts(schedule)
    if weekdays and _WEEKDAYS[datetime.now(CLINIC_TZ).weekday()] not in weekdays:
        return []
    clocks: list[str] = []
    for item in times:
        parsed = _parse_clock(item)
        if parsed is None:
            continue
        hour, minute = parsed
        if hour < 17:
            continue
        clock = f"{hour:02d}:{minute:02d}"
        if clock not in clocks:
            clocks.append(clock)
    return clocks


def _schedule_parts(schedule: object) -> tuple[list[str], set[str] | None]:
    times: list = []
    weekdays: set[str] | None = None
    if isinstance(schedule, list):
        times = schedule
    elif isinstance(schedule, dict):
        raw_times = schedule.get("times", [])
        times = raw_times if isinstance(raw_times, list) else []
        raw_days = schedule.get("weekdays")
        if isinstance(raw_days, list):
            weekdays = {str(day).strip().lower() for day in raw_days if str(day).strip()}
    else:
        return [], None
    clean = [item.strip() for item in times if isinstance(item, str) and item.strip()]
    return clean, weekdays


def _parse_clock(value: str) -> tuple[int, int] | None:
    parts = value.split(":")
    if len(parts) not in (2, 3) or not all(part.isdigit() for part in parts[:2]):
        return None
    hour = int(parts[0])
    minute = int(parts[1])
    if hour > 23 or minute > 59:
        return None
    return hour, minute


def _logs_at_clock(logs: list, medication_id: uuid.UUID, clock: str) -> list[dict]:
    hour, minute = _parse_clock(clock) or (0, 0)
    matched = []
    for row in logs:
        if row.medication_id != medication_id:
            continue
        local = row.schedule_time.astimezone(CLINIC_TZ)
        if local.hour != hour or local.minute != minute:
            continue
        matched.append(
            {
                "id": str(row.id),
                "source": row.source,
                "reported_status": row.reported_status,
                "recorded_at": row.recorded_at,
            }
        )
    return matched


def _consent_recorded(session: Session, patient_id: uuid.UUID) -> bool:
    calls = session.scalars(select(VoiceCall).where(VoiceCall.patient_id == patient_id)).all()
    for call in calls:
        data = call.extracted_data or {}
        if isinstance(data, dict) and data.get("consent_recorded") is True:
            return True
    return False


def _condition_phrase(session: Session, patient_id: uuid.UUID) -> str:
    rows = list(session.scalars(select(Condition).where(Condition.patient_id == patient_id)).all())
    rows.sort(key=lambda row: (_CONDITION_ORDER.get(row.condition_type, 9), row.condition_type))
    labels: list[str] = []
    for row in rows:
        label = _CONDITION_LABELS.get(row.condition_type, row.condition_type.replace("_", " "))
        if label not in labels:
            labels.append(label)
    if not labels:
        return "none recorded"
    return _join(labels)


def _missing_days(plans: list, schedule_key: str, present: set[date]) -> list[str]:
    missing: list[str] = []
    for plan in plans:
        schedule = plan.monitoring_schedule if isinstance(plan.monitoring_schedule, dict) else {}
        block = schedule.get(schedule_key)
        for day in _window_gaps(block, present):
            if day not in missing:
                missing.append(day)
    return missing


def _window_gaps(block: object, present: set[date]) -> list[str]:
    if not isinstance(block, dict):
        return []
    expected = block.get("expected", "daily")
    if expected != "daily":
        return []
    start = _as_date(block.get("window_start"))
    end = _as_date(block.get("window_end"))
    if start is None or end is None or end < start or (end - start).days > 366:
        return []
    missing: list[str] = []
    cursor = start
    while cursor <= end:
        if cursor not in present:
            missing.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return missing


def _reading_days(rows: list) -> set[date]:
    return {row.measured_at.astimezone(CLINIC_TZ).date() for row in rows}


def _dose_phrase(dose: dict) -> str:
    return f"{dose['name']} {dose['dosage']} scheduled at {dose['time']}"


def _join(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + ", and " + items[-1]


def _as_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and len(value) >= 10:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None
