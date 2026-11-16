"""Voice call outcomes and the idempotent Bolna webhook inbox.

Webhook bodies are stored on a voice call. A completed extraction may also
record adherence and care events. It does not create a prescription or a reading.
"""

import hashlib
import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calls.results import stage_call_result
from app.models import Patient, VoiceCall, WebhookDelivery
from app.phones import resolve_patient_id_by_phone
from app.services.patient_service import get_patient
from app.timeutil import utcnow
from app.validation import parse_uuid, raise_if, reject_unknown_fields, require_choice

OUTCOME_FIELDS = frozenset(
    {
        "bolna_call_id",
        "call_type",
        "language",
        "call_status",
        "summary",
        "extracted_data",
    }
)
CALL_TYPES = ("outbound", "inbound")


@dataclass(frozen=True)
class WebhookResult:
    status: int
    body: dict


def record_call_outcome(session: Session, patient_id: str, payload: dict) -> tuple[VoiceCall, bool]:
    patient = get_patient(session, patient_id)
    details: list[str] = []
    reject_unknown_fields(payload, OUTCOME_FIELDS, details)
    bolna_call_id = _required_token(payload, "bolna_call_id", details, max_length=200)
    call_type = require_choice(payload, "call_type", CALL_TYPES, details)
    language = _required_token(payload, "language", details, max_length=35)
    call_status = _required_token(payload, "call_status", details, max_length=80)
    summary = _required_text(payload, "summary", details, max_length=8000)
    extracted = payload.get("extracted_data", None)
    if "extracted_data" not in payload or not isinstance(extracted, dict):
        details.append("extracted_data must be an object")
        extracted = None
    raise_if(details)
    assert bolna_call_id and call_type and language and call_status and summary is not None

    existing = session.scalar(select(VoiceCall).where(VoiceCall.bolna_call_id == bolna_call_id))
    if existing is not None and existing.patient_id != patient.id:
        raise_if(["bolna_call_id is already linked to another patient"])
    created = existing is None
    row = existing or VoiceCall(patient_id=patient.id, bolna_call_id=bolna_call_id, call_type=call_type)
    row.patient_id = patient.id
    row.call_type = call_type
    row.language = language
    row.call_status = call_status
    row.summary = summary
    row.extracted_data = extracted
    session.add(row)
    session.commit()
    session.refresh(row)
    return row, created


def accept_webhook(session: Session, payload: dict) -> WebhookResult:
    delivery_key = compute_delivery_key(payload)
    existing = session.scalar(
        select(WebhookDelivery).where(WebhookDelivery.delivery_key == delivery_key)
    )
    if existing is not None:
        return WebhookResult(status=200, body={"duplicate": True})

    bolna_call_id = _call_identifier(payload) or delivery_key
    patient = _resolve_patient(session, payload)
    session.add(
        WebhookDelivery(
            bolna_call_id=bolna_call_id,
            delivery_key=delivery_key,
            payload=payload,
            received_at=utcnow(),
        )
    )
    if patient is None:
        session.commit()
        return WebhookResult(status=202, body={"ignored": True})

    summary = payload.get("summary")
    summary = summary.strip() if isinstance(summary, str) and summary.strip() else None
    extracted = payload.get("extracted_data")
    if not isinstance(extracted, dict):
        extracted = {}
    status = payload.get("status")
    call_status = status.strip() if isinstance(status, str) and status.strip() else "unknown"
    language = payload.get("language")
    if isinstance(language, str) and language.strip():
        language = language.strip()
    else:
        language = patient.preferred_language

    row = session.scalar(select(VoiceCall).where(VoiceCall.bolna_call_id == bolna_call_id))
    if row is not None and row.patient_id != patient.id:
        session.rollback()
        raise_if(["bolna_call_id is already linked to another patient"])
    if row is None:
        row = VoiceCall(
            patient_id=patient.id,
            bolna_call_id=bolna_call_id,
            call_type=_call_type(payload),
            language=language,
            call_status=call_status,
            summary=summary,
            extracted_data=extracted,
        )
        session.add(row)
    else:
        explicit_call_type = _explicit_call_type(payload)
        if explicit_call_type is not None:
            row.call_type = explicit_call_type
        if isinstance(payload.get("language"), str) and payload["language"].strip():
            row.language = language
        if isinstance(status, str) and status.strip():
            row.call_status = status.strip()
        if summary is not None:
            row.summary = summary
        if isinstance(payload.get("extracted_data"), dict):
            row.extracted_data = extracted
    stage_call_result(session, payload, patient=patient, voice_call=row)
    session.commit()
    return WebhookResult(
        status=200,
        body={"duplicate": False, "bolna_call_id": bolna_call_id, "patient_id": str(patient.id)},
    )


def compute_delivery_key(payload: dict) -> str:
    identifier = payload.get("id")
    if isinstance(identifier, str) and identifier.strip():
        return identifier.strip()
    if isinstance(identifier, int) and not isinstance(identifier, bool):
        return str(identifier)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _call_identifier(payload: dict) -> str | None:
    identifier = payload.get("id")
    if isinstance(identifier, str) and identifier.strip():
        return identifier.strip()
    if isinstance(identifier, int) and not isinstance(identifier, bool):
        return str(identifier)
    return None


def _resolve_patient(session: Session, payload: dict):
    """A linked phone selects the chart. An id in the body is the fallback."""
    linked_id = _patient_id_from_numbers(session, payload)
    if linked_id is not None:
        patient = session.get(Patient, linked_id)
        if patient is not None:
            return patient
    for candidate in (_direct_patient_id(payload), _context_patient_id(payload)):
        if candidate is None:
            continue
        details: list[str] = []
        parsed = parse_uuid(candidate, "patient_id", details)
        if parsed is None:
            continue
        patient = session.get(Patient, parsed)
        if patient is not None:
            return patient
    return None


def _direct_patient_id(payload: dict) -> str | None:
    value = payload.get("patient_id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _context_patient_id(payload: dict) -> str | None:
    context = payload.get("context_details")
    if not isinstance(context, dict):
        return None
    recipient = context.get("recipient_data")
    if not isinstance(recipient, dict):
        return None
    value = recipient.get("patient_id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _patient_id_from_numbers(session: Session, payload: dict):
    """Resolve user_number, then to_number, then from_number. Skip the CareLoop line."""
    for number in _webhook_numbers(payload):
        patient_id = resolve_patient_id_by_phone(session, number)
        if patient_id is not None:
            return patient_id
    return None


def _webhook_numbers(payload: dict) -> list[object]:
    numbers: list[object] = [payload.get("user_number")]
    telephony = payload.get("telephony_data")
    if isinstance(telephony, dict):
        numbers.append(telephony.get("to_number"))
        numbers.append(telephony.get("from_number"))
    return numbers


def _call_type(payload: dict) -> str:
    return _explicit_call_type(payload) or "outbound"


def _explicit_call_type(payload: dict) -> str | None:
    candidates = [payload.get("call_type")]
    telephony = payload.get("telephony_data")
    if isinstance(telephony, dict):
        candidates.append(telephony.get("call_type"))
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip().lower() in CALL_TYPES:
            return candidate.strip().lower()
    return None


def _required_token(payload: dict, field: str, details: list[str], *, max_length: int) -> str | None:
    if field not in payload or payload[field] is None:
        details.append(f"{field} is required")
        return None
    value = payload[field]
    if not isinstance(value, str) or not value.strip():
        details.append(f"{field} is required")
        return None
    if len(value.strip()) > max_length:
        details.append(f"{field} is too long")
        return None
    return value.strip()


def _required_text(payload: dict, field: str, details: list[str], *, max_length: int) -> str | None:
    if field not in payload or not isinstance(payload[field], str):
        details.append(f"{field} is required")
        return None
    value = payload[field]
    if len(value) > max_length:
        details.append(f"{field} is too long")
        return None
    return value
