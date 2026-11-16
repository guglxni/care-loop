"""Consultation, laboratory, and follow-up coordination.

Findings name an appointment fact for a person to review. They do not diagnose,
prescribe, recommend taking a medicine, or change a dose.
"""

from datetime import date, datetime, timezone

from intelligence.models import Consultation, Finding, PatientRecord
from intelligence.rules import coordination_priority

_MISSING = object()


def evaluate_consultations(
    record: PatientRecord,
    as_of: datetime,
    catalog: dict,
) -> list[Finding]:
    """Open coordination findings for visits and laboratories."""
    consultations = _collection(record, ("consultations", "appointments"))
    findings: list[Finding] = []
    for consult in consultations:
        if not _same_patient(consult, record):
            continue
        status = _text(consult, "status")
        raw_type = _raw(consult, "consultation_type", "type")
        ctype = raw_type.lower()
        if status == "scheduled":
            when = _moment(consult, "appointment_date", "scheduled_at", "appointment_at")
            if _instant(when) >= _instant(as_of):
                findings.append(_upcoming(record, consult, raw_type, when))
            else:
                findings.append(_overdue(record, consult, raw_type, when, catalog))
            if ctype == "laboratory":
                findings.append(_laboratory(record, consult, when, catalog))
        elif status == "completed" and ctype in {"consultation", "follow_up", "follow-up"}:
            if not _has_later_scheduled_follow_up(consult, consultations):
                findings.append(_follow_up(record, consult))
    return findings


def _upcoming(record: PatientRecord, consult: Consultation, raw_type: str, when: datetime) -> Finding:
    clinician = _clinician(consult)
    display_type = raw_type or "consultation"
    consultation_id = _id(consult)
    description = f"Scheduled {display_type} with {clinician} at {_iso(when)}."
    return _finding(
        record,
        kind="consultation_upcoming",
        priority="low",
        rule_id=None,
        dedupe_key=f"consult-upcoming:{consultation_id}",
        description=description,
        evidence=_evidence(consult, display_type, when, "scheduled"),
    )


def _overdue(
    record: PatientRecord,
    consult: Consultation,
    raw_type: str,
    when: datetime,
    catalog: dict,
) -> Finding:
    clinician = _clinician(consult)
    display_type = raw_type or "consultation"
    consultation_id = _id(consult)
    description = f"Overdue {display_type} with {clinician} at {_iso(when)}."
    return _finding(
        record,
        kind="consultation_overdue",
        priority=coordination_priority(catalog, "overdue_consultation_priority"),
        rule_id=None,
        dedupe_key=f"consult-overdue:{consultation_id}",
        description=description,
        evidence=_evidence(consult, display_type, when, "scheduled"),
    )


def _laboratory(record: PatientRecord, consult: Consultation, when: datetime, catalog: dict) -> Finding:
    clinician = _clinician(consult)
    consultation_id = _id(consult)
    description = f"Pending laboratory appointment with {clinician} at {_iso(when)}."
    return _finding(
        record,
        kind="laboratory_pending",
        priority=coordination_priority(catalog, "pending_laboratory_priority"),
        rule_id=None,
        dedupe_key=f"lab-pending:{consultation_id}",
        description=description,
        evidence=_evidence(consult, "laboratory", when, "scheduled"),
    )


def _follow_up(record: PatientRecord, consult: Consultation) -> Finding:
    consultation_id = _id(consult)
    return _finding(
        record,
        kind="follow_up_task",
        priority="low",
        rule_id=None,
        dedupe_key=f"follow-up:{consultation_id}",
        description=f"Follow-up task open after consultation {consultation_id}",
        evidence=_evidence(consult, _raw(consult, "consultation_type", "type"), _moment(
            consult, "appointment_date", "scheduled_at", "appointment_at"
        ), "completed"),
    )


def _has_later_scheduled_follow_up(consult: Consultation, consultations: list) -> bool:
    current_id = _id(consult)
    current = _instant(_moment(consult, "appointment_date", "scheduled_at", "appointment_at"))
    for other in consultations:
        if _id(other) == current_id:
            continue
        if _text(other, "consultation_type", "type") not in {"follow_up", "follow-up"}:
            continue
        if _text(other, "status") != "scheduled":
            continue
        other_when = _moment(other, "appointment_date", "scheduled_at", "appointment_at")
        if _instant(other_when) > current:
            return True
    return False


def _finding(
    record: PatientRecord,
    *,
    kind: str,
    priority: str,
    rule_id: str | None,
    dedupe_key: str,
    description: str,
    evidence: dict,
) -> Finding:
    from intelligence.escalation import guard_description, new_model

    return new_model(
        Finding,
        id=f"{kind}:{dedupe_key}",
        patient_id=_patient_id(record),
        kind=kind,
        priority=priority,
        rule_id=rule_id,
        dedupe_key=dedupe_key,
        description=guard_description(description, kind=kind),
        event_description=guard_description(description, kind=kind),
        evidence=evidence,
    )


def _evidence(consult: Consultation, display_type: str, when: datetime, status: str) -> dict:
    return {
        "consultation_id": _id(consult),
        "clinician": _clinician(consult),
        "consultation_type": display_type,
        "appointment_date": _iso(when),
        "status": status,
    }


def _collection(record: PatientRecord, names: tuple[str, ...]) -> list:
    for name in names:
        value = _attr(record, name)
        if value is _MISSING or value is None:
            continue
        return list(value)
    return []


def _same_patient(consult: Consultation, record: PatientRecord) -> bool:
    consult_patient = _attr(consult, "patient_id")
    if consult_patient is _MISSING or consult_patient is None:
        return True
    return str(consult_patient) == _patient_id(record)


def _patient_id(record: PatientRecord) -> str:
    return str(_attr(record, "patient_id"))


def _id(consult: Consultation) -> str:
    value = _attr(consult, "id", "consultation_id")
    if value is _MISSING or value is None:
        raise ValueError("consultation id is required for care coordination")
    return str(value)


def _clinician(consult: Consultation) -> str:
    value = _attr(consult, "clinician", "clinician_name")
    if value is _MISSING or value is None or str(value).strip() == "":
        return "unspecified clinician"
    return str(value)


def _raw(consult: Consultation, *names: str) -> str:
    value = _attr(consult, *names)
    if value is _MISSING or value is None:
        return ""
    return str(value).strip()


def _text(consult: Consultation, *names: str) -> str:
    return _raw(consult, *names).lower()


def _moment(consult: Consultation, *names: str) -> datetime:
    value = _attr(consult, *names)
    if value is _MISSING or value is None:
        raise ValueError("appointment time is required for care coordination")
    if not isinstance(value, (datetime, date)):
        raise TypeError("appointment time must be a date or datetime")
    return value


def _instant(value: datetime | date) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)


def _iso(value: datetime | date) -> str:
    return value.isoformat()


def _attr(obj: object, *names: str):
    for name in names:
        if isinstance(obj, dict):
            if name in obj:
                return obj[name]
            continue
        if hasattr(obj, name):
            return getattr(obj, name)
    return _MISSING
