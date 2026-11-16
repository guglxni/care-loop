"""Structured patient summary for care coordination.

Readings stay raw, adherence stays counted, and open tasks stay listed. The
summary has no diagnosis prose and does not recommend a medicine or a dose.
"""

from datetime import date, datetime, timezone

from intelligence.escalation import guard_description, new_model
from intelligence.models import CareCoordinationEvent, PatientRecord, PatientSummary, Reading, reading_origin

_MISSING = object()
_TAKEN = "taken"
_MISSED = "missed"
_UNCONFIRMED = frozenset({"unknown", "unconfirmed", ""})
_READING_LIMIT = 20


def build_summary(
    record: PatientRecord,
    events: list[CareCoordinationEvent],
    as_of: datetime,
) -> PatientSummary:
    """Build the coordination summary as of the given clock."""
    patient_id = str(_attr(record, "patient_id"))
    as_of_text = as_of.isoformat()
    adherence = _adherence(record, as_of)
    adherence["patient_id"] = patient_id
    adherence["as_of"] = as_of_text
    return new_model(
        PatientSummary,
        patient_id=patient_id,
        as_of=as_of_text,
        generated_at=as_of_text,
        recent_readings=_recent_readings(record, as_of),
        adherence=adherence,
        outstanding_tasks=_outstanding_tasks(events),
    )


def _recent_readings(record: PatientRecord, as_of: datetime) -> list[dict]:
    clock = _instant(as_of)
    eligible: list[tuple[datetime, str, Reading]] = []
    for reading in _collection(record, ("readings", "health_readings")):
        measured = _attr(reading, "measured_at")
        if measured is _MISSING or measured is None:
            continue
        instant = _instant(measured)
        if instant <= clock:
            identifier = _attr(reading, "id")
            eligible.append((instant, "" if identifier is _MISSING or identifier is None else str(identifier), reading))
    eligible.sort(key=lambda item: (item[0], item[1]), reverse=True)
    rows = []
    for _, _, reading in eligible[:_READING_LIMIT]:
        measured = _attr(reading, "measured_at")
        context = _optional(reading, "measurement_context", "context")
        rows.append(
            {
                "measurement_type": _value(reading, "measurement_type", "metric"),
                "value": _value(reading, "value"),
                "secondary_value": _optional(reading, "secondary_value"),
                "unit": _value(reading, "unit"),
                "measurement_context": context,
                "context": context,
                "measured_at": _iso(measured),
                "source": _value(reading, "source"),
                "origin": _origin(reading),
            }
        )
    return rows


def _origin(reading: Reading) -> str:
    return reading_origin(_value(reading, "source"))


def _adherence(record: PatientRecord, as_of: datetime) -> dict:
    clock = _instant(as_of)
    taken = 0
    missed = 0
    unconfirmed = 0
    missed_items = []
    for dose in _collection(record, ("doses", "adherence_logs", "adherence_events", "scheduled_doses")):
        scheduled = _attr(dose, "schedule_time", "scheduled_at", "due_at")
        if scheduled is _MISSING or scheduled is None:
            continue
        if _instant(scheduled) > clock:
            continue
        status = _status(dose)
        if status == _TAKEN:
            taken += 1
        elif status == _MISSED:
            missed += 1
            missed_items.append(
                {
                    "medication_name": _medication_name(dose, record),
                    "schedule_time": _iso(scheduled),
                    "reported_reason": _optional(dose, "reported_reason", "reason"),
                    "report_source": _report_source(dose),
                }
            )
        elif status is None or status in _UNCONFIRMED:
            unconfirmed += 1
    missed_items.sort(key=lambda item: item["schedule_time"])
    return {
        "taken": taken,
        "missed": missed,
        "unconfirmed": unconfirmed,
        "missed_items": missed_items,
    }


def _outstanding_tasks(events: list[CareCoordinationEvent]) -> list[dict]:
    tasks = []
    for event in events or []:
        status = _attr(event, "status")
        if status is _MISSING or status is None or str(status).strip().lower() != "open":
            continue
        kind = _value(event, "event_type", "kind", "type")
        description = guard_description(_text(event, "description", "event_description"), kind=str(kind or "task"))
        tasks.append(
            {
                "event_type": kind,
                "description": description,
                "priority": _optional(event, "priority"),
                "dedupe_key": _optional(event, "dedupe_key"),
            }
        )
    return tasks


def _medication_name(dose: object, record: PatientRecord) -> str:
    for name in ("medication_name", "medicine_name", "drug_name"):
        value = _attr(dose, name)
        if value not in (_MISSING, None, ""):
            return str(value)
    medication_id = _attr(dose, "medication_id")
    if medication_id not in (_MISSING, None):
        for medication in _collection(record, ("medications",)):
            current_id = _attr(medication, "id", "medication_id")
            if current_id not in (_MISSING, None) and str(current_id) == str(medication_id):
                for name in ("medication_name", "name", "medicine_name"):
                    value = _attr(medication, name)
                    if value not in (_MISSING, None, ""):
                        return str(value)
    value = _attr(dose, "name")
    if value not in (_MISSING, None):
        return str(value)
    return ""


def _report_source(dose: object) -> str:
    source = _attr(dose, "source", "report_source")
    if source is _MISSING or source is None:
        return "unconfirmed"
    if hasattr(source, "value"):
        source = source.value
    text = str(source).strip().lower()
    if text in {"app", "call_self_report", "patient-reported", "patient_reported"}:
        return "patient-reported"
    if text == "inferred":
        return "inferred"
    return text


def _status(dose: object) -> str | None:
    value = _attr(dose, "reported_status", "adherence_status", "status")
    if value is _MISSING or value is None:
        return None
    if hasattr(value, "value"):
        value = value.value
    text = str(value).strip().lower()
    if text in {"none", "null"}:
        return None
    return text


def _collection(record: PatientRecord, names: tuple[str, ...]) -> list:
    for name in names:
        value = _attr(record, name)
        if value is _MISSING or value is None:
            continue
        return list(value)
    return []


def _instant(value: datetime | date | str) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)


def _iso(value: datetime | date | str) -> str:
    if isinstance(value, str):
        return value
    return value.isoformat()


def _value(obj: object, *names: str):
    value = _attr(obj, *names)
    if value is _MISSING:
        return None
    return value


def _optional(obj: object, *names: str):
    value = _attr(obj, *names)
    if value is _MISSING:
        return None
    return value


def _text(obj: object, *names: str) -> str:
    value = _attr(obj, *names)
    if value is _MISSING or value is None:
        return ""
    return str(value)


def _attr(obj: object, *names: str):
    for name in names:
        if isinstance(obj, dict):
            if name in obj:
                return obj[name]
            continue
        if hasattr(obj, name):
            return getattr(obj, name)
    return _MISSING
