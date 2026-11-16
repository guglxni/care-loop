"""Scripted demo outbound call. Tests patch start_outbound_call so pytest never dials.

The selected patient is the demo chart, or the patient_id / patient_name in
the body. The destination number only rings. A patient_phone_links row does
not replace that patient. Inbound webhook resolution still uses the link table.
"""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.demo.ravi import PATIENT_ID as RAVI_ID
from app.demo.ravi import STORED_CONTACT, ensure_seeded
from app.errors import ConflictError, NotFoundError
from app.models import Patient, VoiceCall
from app.services.bolna_outbound import FROM_NUMBER
from app.services.outbound_call import deliver_outbound_call, log_outbound
from app.services.outbound_context import canonical_call_type
from app.services.reminder_service import SYNTHETIC_NUMBER
from app.validation import raise_if, reject_unknown_fields

DEMO_CALL_FIELDS = frozenset({"patient_id", "patient_name", "scenario", "to"})
BLOCKED_NUMBERS = frozenset({SYNTHETIC_NUMBER, FROM_NUMBER, STORED_CONTACT})
_E164 = re.compile(r"^\+[1-9]\d{1,14}$")


def start_demo_call(session: Session, payload: dict) -> dict:
    details: list[str] = []
    reject_unknown_fields(payload, DEMO_CALL_FIELDS, details)
    _optional_name(payload, details)
    recipient = _recipient(payload, details)
    raise_if(details)
    assert recipient is not None

    try:
        call_type = canonical_call_type(payload.get("scenario"))
    except ConflictError:
        log_outbound("unknown", payload.get("scenario"), "failure")
        raise

    ensure_seeded(session)
    try:
        patient_id = _selected_patient_id(session, payload)
    except ConflictError:
        log_outbound("unknown", call_type, "failure")
        raise
    return deliver_outbound_call(session, patient_id, call_type, recipient)


def demo_call_status(session: Session, execution_id: str) -> dict:
    row = session.scalar(select(VoiceCall).where(VoiceCall.bolna_call_id == execution_id))
    if row is None:
        raise NotFoundError("Demo call was not found")
    return {
        "execution_id": row.bolna_call_id,
        "call_status": row.call_status,
        "patient_id": str(row.patient_id),
    }


def _selected_patient_id(session: Session, payload: dict) -> str:
    """The body chooses the chart. The phone number is not consulted."""
    if "patient_id" in payload and payload["patient_id"] is not None:
        raw = payload["patient_id"]
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        raise ConflictError(
            "Outbound call was not placed because the patient was not found.",
            ["patient_id does not match a chart"],
        )
    name = payload.get("patient_name")
    if isinstance(name, str) and name.strip():
        matches = list(
            session.scalars(select(Patient).where(Patient.preferred_name == name.strip())).all()
        )
        if len(matches) != 1:
            raise ConflictError(
                "Outbound call was not placed because the patient was not found.",
                ["patient_name did not match one chart"],
            )
        return str(matches[0].id)
    return str(RAVI_ID)


def _optional_name(payload: dict, details: list[str]) -> None:
    if "patient_name" not in payload or payload["patient_name"] is None:
        return
    if not isinstance(payload["patient_name"], str) or not payload["patient_name"].strip():
        details.append("patient_name must be a string")


def _recipient(payload: dict, details: list[str]) -> str | None:
    raw = payload.get("to")
    if not isinstance(raw, str):
        details.append("to must be an E.164 phone number")
        return None
    number = "".join(raw.split())
    if not _E164.fullmatch(number):
        details.append("to must be an E.164 phone number")
        return None
    if number == SYNTHETIC_NUMBER:
        details.append("to +919840011223 is the synthetic chart number and cannot be dialed")
        return None
    if number == STORED_CONTACT:
        details.append("to +15555501052 is the synthetic stored contact and cannot be dialed")
        return None
    if number in BLOCKED_NUMBERS:
        details.append("to is the CareLoop line and cannot be dialed")
        return None
    return number
