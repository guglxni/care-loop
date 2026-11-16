"""Map a completed Bolna execution onto adherence logs, care events, and the voice call.

Nothing here places a call or creates a medication. Uncertain self-report is stored
as unknown. A dose is marked missed only when the extraction says missed.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AdherenceLog, CareEvent, Medication, Patient, VoiceCall
from app.timeutil import utcnow
from app.validation import require_datetime

SOURCE = "call_self_report"
CONCERN_EVENT = "patient_concern"
FOLLOW_UP_EVENT = "follow_up_task"
FOLLOW_UP_DESCRIPTION = "Follow-up requested from the call."
_STATUS_BY_TOKEN = {
    "missed": "missed",
    "taken": "taken",
    "uncertain": "unknown",
    "unknown": "unknown",
}
_SENTINELS = frozenset({"not_discussed", "none", "n_a", "na", "null", "skipped"})
_FIELD_NAMES = frozenset(
    {
        "medication_status",
        "medication_adherence",
        "medication_id",
        "medication_name",
        "medication",
        "concern",
        "patient_concern",
        "follow_up_required",
        "follow_up_note",
        "follow_up_reason",
        "missed_reason",
        "reported_reason",
        "reason",
        "schedule_time",
    }
)
_SUBJECTIVE_FIELDS = frozenset(
    {
        "concern",
        "patient_concern",
        "missed_reason",
        "reported_reason",
        "reason",
        "follow_up_note",
        "follow_up_reason",
    }
)
_EXTRACTION_MARKERS = frozenset(
    {
        "subjective",
        "objective",
        "reasoning_subjective",
        "reasoning_objective",
        "confidence",
        "confidence_label",
        "status_reason",
        "validation",
    }
)
_CALL_TYPES = frozenset({"outbound", "inbound"})
_ADHERENCE_STATUSES = frozenset({"taken", "missed", "unknown"})


def save_call_result(session: Session, payload: dict) -> dict:
    """Validate and commit chart rows for one execution. The caller does not need a webhook."""
    staged = stage_call_result(session, payload)
    session.commit()
    for row in (*staged["adherence_logs"], *staged["care_events"]):
        session.refresh(row)
    voice_call = staged["voice_call"]
    if voice_call is not None:
        session.refresh(voice_call)
    return {
        "ignored": staged["ignored"],
        "adherence_logs": [row.to_dict() for row in staged["adherence_logs"]],
        "care_events": [row.to_dict() for row in staged["care_events"]],
        "voice_call": voice_call.to_dict() if voice_call is not None else None,
    }


def stage_call_result(
    session: Session,
    payload: dict,
    *,
    patient: Patient | None = None,
    voice_call: VoiceCall | None = None,
) -> dict:
    """Add validated rows to the current transaction. The caller commits."""
    empty = {"ignored": True, "adherence_logs": [], "care_events": [], "voice_call": None}
    if not isinstance(payload, dict) or not _is_completed(payload):
        return empty
    raw_extracted = payload.get("extracted_data")
    if not isinstance(raw_extracted, dict) or _is_blank(raw_extracted):
        return empty

    flat = _collect_fields(raw_extracted)
    resolved = patient if patient is not None else _patient_from_payload(session, payload)
    voice_call = _upsert_voice_call(session, payload, raw_extracted, resolved, voice_call)
    chart_patient = _chart_patient(session, resolved, voice_call)
    logs: list[AdherenceLog] = []
    events: list[CareEvent] = []
    if chart_patient is not None:
        log = _stage_adherence(session, chart_patient, payload, flat)
        if log is not None:
            logs.append(log)
        events.extend(_stage_events(session, chart_patient, flat))
    return {
        "ignored": False,
        "adherence_logs": logs,
        "care_events": events,
        "voice_call": voice_call,
    }


def _chart_patient(
    session: Session,
    patient: Patient | None,
    voice_call: VoiceCall | None,
) -> Patient | None:
    if voice_call is not None and patient is not None and voice_call.patient_id != patient.id:
        return None
    if patient is not None:
        return patient
    if voice_call is None:
        return None
    return session.get(Patient, voice_call.patient_id)


def _stage_adherence(
    session: Session,
    patient: Patient,
    payload: dict,
    flat: dict,
) -> AdherenceLog | None:
    reported_status = _reported_status(flat)
    if reported_status not in _ADHERENCE_STATUSES:
        return None
    medication = _resolve_medication(session, patient, payload, flat)
    if medication is None or medication.patient_id != patient.id:
        return None
    schedule_time = _schedule_time(payload, flat)
    if schedule_time is None:
        return None
    reason = _reason(flat)
    if reason is not None and len(reason) > 500:
        return None
    row = AdherenceLog(
        patient_id=patient.id,
        medication_id=medication.id,
        schedule_time=schedule_time,
        reported_status=reported_status,
        reported_reason=reason,
        recorded_at=utcnow(),
        source=SOURCE,
    )
    if row.reported_status not in _ADHERENCE_STATUSES or row.source != SOURCE:
        return None
    session.add(row)
    return row


def _stage_events(session: Session, patient: Patient, flat: dict) -> list[CareEvent]:
    rows: list[CareEvent] = []
    concern = _concern_text(flat)
    if concern is not None:
        staged = _add_event(session, patient, CONCERN_EVENT, concern)
        if staged is not None:
            rows.append(staged)
    if _follow_up_required(flat):
        staged = _add_event(session, patient, FOLLOW_UP_EVENT, _follow_up_description(flat))
        if staged is not None:
            rows.append(staged)
    return rows


def _add_event(
    session: Session,
    patient: Patient,
    event_type: str,
    description: str,
) -> CareEvent | None:
    if event_type not in {CONCERN_EVENT, FOLLOW_UP_EVENT}:
        return None
    if not isinstance(description, str):
        return None
    text = description.strip()
    if not text or len(text) > 4000 or _is_sentinel(text):
        return None
    row = CareEvent(
        patient_id=patient.id,
        event_type=event_type,
        event_description=text,
        priority="medium",
        status="open",
        resolved_at=None,
    )
    if row.priority != "medium" or row.status != "open":
        return None
    session.add(row)
    return row


def _upsert_voice_call(
    session: Session,
    payload: dict,
    raw_extracted: dict,
    patient: Patient | None,
    voice_call: VoiceCall | None,
) -> VoiceCall | None:
    summary = _summary(payload)
    bolna_call_id = _bolna_call_id(payload)
    if voice_call is None and bolna_call_id is not None:
        voice_call = session.scalar(select(VoiceCall).where(VoiceCall.bolna_call_id == bolna_call_id))
    if voice_call is not None:
        if summary is not None:
            voice_call.summary = summary
        voice_call.extracted_data = raw_extracted
        voice_call.call_status = "completed"
        return voice_call
    if patient is None or bolna_call_id is None:
        return None
    call_type = _call_type(payload)
    language = _language(payload, patient)
    if call_type is None or language is None:
        return None
    row = VoiceCall(
        patient_id=patient.id,
        bolna_call_id=bolna_call_id,
        call_type=call_type,
        language=language,
        call_status="completed",
        summary=summary,
        extracted_data=raw_extracted,
    )
    session.add(row)
    return row


def _resolve_medication(
    session: Session,
    patient: Patient,
    payload: dict,
    flat: dict,
) -> Medication | None:
    explicit = _explicit_medication_id(payload, flat)
    if explicit is not None:
        parsed = _uuid(explicit)
        if parsed is None:
            return None
        return session.scalar(
            select(Medication).where(Medication.id == parsed, Medication.patient_id == patient.id)
        )
    name = _medication_name(flat)
    if name is not None:
        return _match_name(session, patient.id, name)
    active = _active_medications(session, patient.id)
    if len(active) == 1:
        return active[0]
    return None


def _explicit_medication_id(payload: dict, flat: dict) -> object | None:
    candidates: list[object] = []
    if "medication_id" in flat:
        candidates.append(flat.get("medication_id"))
    if "medication_id" in payload:
        candidates.append(payload.get("medication_id"))
    context = payload.get("context_details")
    if isinstance(context, dict):
        recipient = context.get("recipient_data")
        if isinstance(recipient, dict) and "medication_id" in recipient:
            candidates.append(recipient.get("medication_id"))
    for candidate in candidates:
        if _is_blank(candidate):
            continue
        return candidate
    return None


def _match_name(session: Session, patient_id: uuid.UUID, name: str) -> Medication | None:
    target = name.strip().lower()
    rows = session.scalars(select(Medication).where(Medication.patient_id == patient_id)).all()
    matches = [row for row in rows if row.medication_name.strip().lower() == target]
    if len(matches) == 1:
        return matches[0]
    active = [row for row in matches if row.active]
    if len(active) == 1:
        return active[0]
    return None


def _active_medications(session: Session, patient_id: uuid.UUID) -> list[Medication]:
    today = datetime.now(timezone.utc).date()
    rows = session.scalars(
        select(Medication).where(Medication.patient_id == patient_id, Medication.active.is_(True))
    ).all()
    return [row for row in rows if row.end_date is None or row.end_date >= today]


def _reported_status(flat: dict) -> str | None:
    if "medication_status" in flat:
        raw = flat.get("medication_status")
    elif "medication_adherence" in flat:
        raw = flat.get("medication_adherence")
    else:
        return None
    if not isinstance(raw, str):
        return None
    return _STATUS_BY_TOKEN.get(_token(raw))


def _concern_text(flat: dict) -> str | None:
    if "concern" in flat:
        raw = flat.get("concern")
    elif "patient_concern" in flat:
        raw = flat.get("patient_concern")
    else:
        return None
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text or len(text) > 4000 or _is_sentinel(text):
        return None
    return text


def _follow_up_required(flat: dict) -> bool:
    value = flat.get("follow_up_required")
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return _token(value) in {"true", "yes"}
    return False


def _follow_up_description(flat: dict) -> str:
    for key in ("follow_up_note", "follow_up_reason"):
        value = flat.get(key)
        if not isinstance(value, str):
            continue
        text = value.strip()
        if text and not _is_sentinel(text) and len(text) <= 4000:
            return text
    return FOLLOW_UP_DESCRIPTION


def _reason(flat: dict) -> str | None:
    for key in ("missed_reason", "reported_reason", "reason"):
        value = flat.get(key)
        if not isinstance(value, str):
            continue
        text = value.strip()
        if not text or _is_sentinel(text) or len(text) > 500:
            continue
        return text
    return None


def _medication_name(flat: dict) -> str | None:
    for key in ("medication_name", "medication"):
        value = flat.get(key)
        if not isinstance(value, str):
            continue
        text = value.strip()
        if not text or _is_sentinel(text) or _token(text) in _STATUS_BY_TOKEN:
            continue
        return text
    return None


def _schedule_time(payload: dict, flat: dict) -> datetime | None:
    if flat.get("schedule_time") is not None:
        return _parse_datetime(flat.get("schedule_time"))
    if payload.get("schedule_time") is not None:
        return _parse_datetime(payload.get("schedule_time"))
    for key in ("updated_at", "created_at", "initiated_at"):
        if payload.get(key) is None:
            continue
        parsed = _parse_datetime(payload.get(key))
        if parsed is not None:
            return parsed
    return utcnow()


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return None
        return value.astimezone(timezone.utc)
    if not isinstance(value, str):
        return None
    details: list[str] = []
    return require_datetime({"value": value}, "value", details, reject_far_future=False)


def _summary(payload: dict) -> str | None:
    value = payload.get("summary")
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or len(text) > 8000:
        return None
    return text


def _bolna_call_id(payload: dict) -> str | None:
    for key in ("id", "bolna_call_id", "execution_id"):
        if key not in payload or payload[key] is None:
            continue
        value = payload[key]
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            text = str(value)
        elif isinstance(value, str):
            text = value.strip()
        else:
            return None
        if not text or len(text) > 200:
            return None
        return text
    return None


def _call_type(payload: dict) -> str | None:
    candidates = [payload.get("call_type")]
    telephony = payload.get("telephony_data")
    if isinstance(telephony, dict):
        candidates.append(telephony.get("call_type"))
    saw_explicit = False
    for candidate in candidates:
        if candidate is None:
            continue
        saw_explicit = True
        if isinstance(candidate, str) and candidate.strip().lower() in _CALL_TYPES:
            return candidate.strip().lower()
    if saw_explicit:
        return None
    return "outbound"


def _language(payload: dict, patient: Patient | None) -> str | None:
    value = payload.get("language")
    if isinstance(value, str) and value.strip():
        text = value.strip()
        if len(text) > 35 or any(character.isspace() for character in text):
            return None
        return text
    if patient is not None and patient.preferred_language.strip():
        return patient.preferred_language.strip()
    return None


def _patient_from_payload(session: Session, payload: dict) -> Patient | None:
    candidates: list[str] = []
    direct = payload.get("patient_id")
    if isinstance(direct, str) and direct.strip():
        candidates.append(direct.strip())
    context = payload.get("context_details")
    if isinstance(context, dict):
        recipient = context.get("recipient_data")
        if isinstance(recipient, dict):
            nested = recipient.get("patient_id")
            if isinstance(nested, str) and nested.strip():
                candidates.append(nested.strip())
    for candidate in candidates:
        parsed = _uuid(candidate)
        if parsed is None:
            continue
        patient = session.get(Patient, parsed)
        if patient is not None:
            return patient
    return None


def _collect_fields(extracted: dict) -> dict:
    found: dict = {}
    _walk(extracted, found, 0)
    return found


def _walk(node: dict, found: dict, depth: int) -> None:
    if depth > 6:
        return
    for key, value in node.items():
        if not isinstance(key, str):
            continue
        name = key.strip().lower()
        if name in _FIELD_NAMES:
            if name not in found:
                prefer = "subjective" if name in _SUBJECTIVE_FIELDS else "objective"
                found[name] = _unwrap(value, prefer=prefer)
            continue
        if isinstance(value, dict) and not _is_extraction_result(value):
            _walk(value, found, depth + 1)


def _unwrap(value: object, *, prefer: str) -> object:
    if not isinstance(value, dict) or not _is_extraction_result(value):
        return value
    status = value.get("status")
    if isinstance(status, str) and _token(status) in {"skipped", "failed"}:
        return None
    order = ("subjective", "objective") if prefer == "subjective" else ("objective", "subjective")
    for key in order:
        item = value.get(key)
        if _is_blank(item):
            continue
        return item
    return None


def _is_extraction_result(value: dict) -> bool:
    return bool(_EXTRACTION_MARKERS & value.keys())


def _is_completed(payload: dict) -> bool:
    status = payload.get("status")
    return isinstance(status, str) and status.strip().lower() == "completed"


def _is_blank(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, dict):
        return not value or all(_is_blank(item) for item in value.values())
    if isinstance(value, list):
        return not value or all(_is_blank(item) for item in value)
    return False


def _is_sentinel(value: str) -> bool:
    return _token(value) in _SENTINELS


def _token(value: str) -> str:
    cleaned = value.strip().lower().replace("-", " ").replace("/", " ").replace("_", " ")
    return "_".join(part for part in cleaned.split() if part)


def _uuid(value: object) -> uuid.UUID | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return uuid.UUID(value.strip())
    except ValueError:
        return None
