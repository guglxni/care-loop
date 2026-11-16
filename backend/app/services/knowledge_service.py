"""Live care-coordination facts for one chart.

Each request reads the database again. Refresh stores the source path and the
build time only. This module does not register that path with an external service.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AdherenceLog,
    CareEvent,
    Condition,
    HealthReading,
    Patient,
    PatientKnowledgeLink,
)
from app.phones import list_phone_links
from app.services.consultation_service import next_scheduled
from app.services.medication_service import list_active_medications
from app.services.patient_service import get_patient
from app.timeutil import json_number, to_iso, utcnow

DISCLAIMER = (
    "Care coordination facts. Not medical advice. Do not diagnose or change medicines."
)
RECENT_GLUCOSE_LIMIT = 5
RECENT_BLOOD_PRESSURE_LIMIT = 3


def knowledge_source_path(patient_id: uuid.UUID) -> str:
    return f"/api/v1/patients/{patient_id}/knowledge"


def build_document(session: Session, patient_id: str) -> str:
    """Markdown facts for this chart. Missing patients raise NotFoundError."""
    patient = get_patient(session, patient_id)
    _map_ingest_origin()
    sections = [
        _patient_section(patient),
        _conditions_section(session, patient),
        _medications_section(session, patient),
        _glucose_section(session, patient),
        _blood_pressure_section(session, patient),
        _consultation_section(session, patient),
        _events_section(session, patient),
        _phones_section(session, patient),
    ]
    return DISCLAIMER + "\n\n" + "\n\n".join(sections) + "\n"


def refresh_link(session: Session, patient_id: str) -> PatientKnowledgeLink:
    """Store the source path and build time. Leaves bolna_knowledgebase_id unchanged."""
    patient = get_patient(session, patient_id)
    path = knowledge_source_path(patient.id)
    row = session.get(PatientKnowledgeLink, patient.id)
    built_at = utcnow()
    if row is None:
        row = PatientKnowledgeLink(
            patient_id=patient.id,
            source_url=path,
            bolna_knowledgebase_id=None,
            last_built_at=built_at,
        )
        session.add(row)
    else:
        row.source_url = path
        row.last_built_at = built_at
    session.commit()
    session.refresh(row)
    return row


def _patient_section(patient: Patient) -> str:
    lines = [
        f"- Preferred name: {_plain(patient.preferred_name)}",
        f"- Patient id: {patient.id}",
        f"- Preferred language: {_plain(patient.preferred_language)}",
    ]
    return _section("Patient", lines)


def _conditions_section(session: Session, patient: Patient) -> str:
    rows = session.scalars(
        select(Condition)
        .where(Condition.patient_id == patient.id)
        .order_by(Condition.diagnosis_date.asc(), Condition.condition_type.asc())
    ).all()
    lines = [f"- {_plain(row.condition_type)}" for row in rows]
    return _section("Conditions", lines or ["None recorded."])


def _medications_section(session: Session, patient: Patient) -> str:
    medications = list_active_medications(session, str(patient.id))
    latest = _latest_adherence(session, patient)
    lines = []
    for medication in medications:
        parts = [
            _plain(medication.medication_name),
            f"dose {_plain(medication.prescribed_dosage)}",
        ]
        times = _schedule_times(medication.schedule)
        if times:
            parts.append("times " + ", ".join(times))
        log = latest.get(medication.id)
        if log is not None:
            parts.append(f"latest adherence {_plain(log.reported_status)}")
        lines.append("- " + ", ".join(parts))
    return _section("Active medications", lines or ["None recorded."])


def _glucose_section(session: Session, patient: Patient) -> str:
    rows = session.scalars(
        select(HealthReading)
        .where(
            HealthReading.patient_id == patient.id,
            HealthReading.measurement_type == "blood_glucose",
            HealthReading.data_quality == "valid",
        )
        .order_by(HealthReading.measured_at.desc(), HealthReading.created_at.desc())
        .limit(RECENT_GLUCOSE_LIMIT)
    ).all()
    lines = [_reading_line(json_number(row.value), row.unit, row) for row in rows]
    return _section("Recent glucose", lines or ["None recorded."])


def _blood_pressure_section(session: Session, patient: Patient) -> str:
    systolics = list(
        session.scalars(
            select(HealthReading)
            .where(
                HealthReading.patient_id == patient.id,
                HealthReading.measurement_type == "systolic_blood_pressure",
                HealthReading.data_quality == "valid",
            )
            .order_by(HealthReading.measured_at.desc(), HealthReading.created_at.desc())
            .limit(RECENT_BLOOD_PRESSURE_LIMIT)
        ).all()
    )
    if not systolics:
        return _section("Recent blood pressure", ["None recorded."])
    times = [row.measured_at for row in systolics]
    diastolics = session.scalars(
        select(HealthReading).where(
            HealthReading.patient_id == patient.id,
            HealthReading.measurement_type == "diastolic_blood_pressure",
            HealthReading.measured_at.in_(times),
            HealthReading.data_quality == "valid",
        )
    ).all()
    lines = []
    for systolic in systolics:
        diastolic = _match_diastolic(systolic, diastolics)
        diastolic_value = diastolic.value if diastolic is not None else systolic.secondary_value
        if diastolic_value is None:
            continue
        value = f"{json_number(systolic.value)}/{json_number(diastolic_value)}"
        origin = _origin(systolic) or (_origin(diastolic) if diastolic is not None else None)
        lines.append(_reading_line(value, systolic.unit, systolic, origin=origin))
    return _section("Recent blood pressure", lines or ["None recorded."])


def _consultation_section(session: Session, patient: Patient) -> str:
    row = next_scheduled(session, str(patient.id))
    if row is None:
        return _section("Next consultation", ["None scheduled."])
    lines = [
        f"- clinician: {_plain(row.clinician)}",
        f"- appointment_date: {to_iso(row.appointment_date)}",
        f"- consultation_type: {_plain(row.consultation_type)}",
        f"- status: {_plain(row.status)}",
    ]
    return _section("Next consultation", lines)


def _events_section(session: Session, patient: Patient) -> str:
    rows = session.scalars(
        select(CareEvent)
        .where(CareEvent.patient_id == patient.id, CareEvent.status == "open")
        .order_by(CareEvent.created_at.asc())
    ).all()
    lines = [
        f"- {_plain(row.event_type)}, priority {_plain(row.priority)}: {_plain(row.event_description)}"
        for row in rows
    ]
    return _section("Open care events", lines or ["None recorded."])


def _phones_section(session: Session, patient: Patient) -> str:
    rows = list_phone_links(session, str(patient.id))
    lines = [f"- {_plain(row.phone_e164)}, label {_plain(row.label)}" for row in rows]
    return _section("Linked phone numbers", lines or ["None linked."])


def _latest_adherence(session: Session, patient: Patient) -> dict[uuid.UUID, AdherenceLog]:
    rows = session.scalars(
        select(AdherenceLog)
        .where(AdherenceLog.patient_id == patient.id)
        .order_by(
            AdherenceLog.recorded_at.desc(),
            AdherenceLog.schedule_time.desc(),
            AdherenceLog.id.desc(),
        )
    ).all()
    latest: dict[uuid.UUID, AdherenceLog] = {}
    for row in rows:
        if row.medication_id not in latest:
            latest[row.medication_id] = row
    return latest


def _schedule_times(schedule: object) -> list[str]:
    if isinstance(schedule, list):
        raw = schedule
    elif isinstance(schedule, dict):
        raw = schedule.get("times", [])
    else:
        return []
    if not isinstance(raw, list):
        return []
    return [_plain(item) for item in raw if isinstance(item, str) and item.strip()]


def _reading_line(value, unit: str, row: HealthReading, origin: str | None = None) -> str:
    text = (
        f"- {value} {_plain(unit)}, measured_at {to_iso(row.measured_at)}, "
        f"source {_plain(row.source)}"
    )
    chosen = origin if origin is not None else _origin(row)
    if chosen:
        text += f", ingest origin {_plain(chosen)}"
    return text


def _match_diastolic(systolic: HealthReading, rows) -> HealthReading | None:
    matches = [row for row in rows if row.measured_at == systolic.measured_at]
    if not matches:
        return None
    same_source = [row for row in matches if row.source == systolic.source]
    pool = same_source or matches
    return max(pool, key=lambda row: (row.created_at, str(row.id)))


def _origin(row: HealthReading | None) -> str | None:
    if row is None or "ingest_origin" not in HealthReading.__mapper__.attrs:
        return None
    value = getattr(row, "ingest_origin", None)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _map_ingest_origin() -> None:
    column = HealthReading.__table__.columns.get("ingest_origin")
    if column is None or "ingest_origin" in HealthReading.__mapper__.attrs:
        return
    HealthReading.__mapper__.add_property("ingest_origin", column)


def _section(title: str, lines: list[str]) -> str:
    return f"## {title}\n" + "\n".join(lines)


def _plain(value: object) -> str:
    return " ".join(str(value).split())
