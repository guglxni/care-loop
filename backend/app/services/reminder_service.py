"""Queue one outbound reminder. The synthetic chart number is never dialed.

A destination in patient_phone_links selects that chart for user_data.
The patient id in the URL is used only when the destination is not linked.
"""

import os
import re

from sqlalchemy.orm import Session

from app.demo.ravi import STORED_CONTACT
from app.errors import ConflictError
from app.phones import resolve_patient_id_by_phone
from app.services.bolna_outbound import FROM_NUMBER
from app.services.outbound_call import deliver_outbound_call, log_outbound
from app.services.outbound_context import canonical_call_type
from app.validation import raise_if, reject_unknown_fields

REMIND_FIELDS = frozenset({"to", "purpose", "call_type"})
SYNTHETIC_NUMBER = "+919840011223"
BLOCKED_NUMBERS = frozenset({SYNTHETIC_NUMBER, FROM_NUMBER, STORED_CONTACT})
_E164 = re.compile(r"^\+[1-9]\d{1,14}$")


def queue_reminder(session: Session, patient_id: str, payload: dict) -> dict:
    details: list[str] = []
    reject_unknown_fields(payload, REMIND_FIELDS, details)
    recipient = _recipient(payload, details)
    raise_if(details)
    assert recipient is not None

    raw_type = _requested_call_type(payload)
    try:
        call_type = canonical_call_type(raw_type)
    except ConflictError:
        log_outbound(patient_id, raw_type, "failure")
        raise
    return deliver_outbound_call(session, _chart_id(session, patient_id, recipient), call_type, recipient)


def _chart_id(session: Session, patient_id: str, recipient: str) -> str:
    """Use the linked chart when this destination already belongs to one."""
    linked = resolve_patient_id_by_phone(session, recipient)
    if linked is None:
        return patient_id
    return str(linked)


def _requested_call_type(payload: dict) -> object:
    if "call_type" in payload and payload["call_type"] is not None:
        return payload["call_type"]
    if "purpose" in payload and payload["purpose"] is not None:
        return payload["purpose"]
    return "medication_check"


def _recipient(payload: dict, details: list[str]) -> str | None:
    if "to" in payload and payload["to"] is not None:
        raw = payload["to"]
    else:
        raw = os.environ.get("USER_PHONE_NUMBER", "").strip()
        if not raw:
            details.append("to is required when USER_PHONE_NUMBER is unset")
            return None
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
