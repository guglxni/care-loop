"""Place one outbound Bolna call after a chart context exists.

Logs the patient id, call type, and success or failure. The log line does not
include the phone number, API key, or medical-history narrative.
"""

import logging
import uuid

from sqlalchemy.orm import Session

from app.errors import ApiError, ConflictError
from app.services.bolna_outbound import AGENT_ID, FROM_NUMBER, start_outbound_call
from app.services.outbound_context import build_outbound_context
from app.services.voice_service import record_call_outcome

logger = logging.getLogger(__name__)

CONTEXT_FIELDS = (
    "patient_id",
    "patient_name",
    "call_type",
    "call_reason",
    "call_objective",
    "preferred_language",
    "language_policy",
    "supported_languages",
    "clinic_name",
    "doctor_name",
    "relevant_context",
)


def deliver_outbound_call(
    session: Session,
    patient_id: str,
    call_type: object,
    recipient: str,
) -> dict:
    """Build context, then dial. A context failure returns before Bolna is called."""
    try:
        context = build_outbound_context(session, patient_id, str(call_type) if call_type is not None else "")
        user_data = _user_data(context)
    except ConflictError:
        log_outbound(patient_id, call_type, "failure")
        raise

    try:
        execution_id = start_outbound_call(
            agent_id=AGENT_ID,
            recipient_phone_number=recipient,
            from_phone_number=FROM_NUMBER,
            user_data=user_data,
        )
    except Exception as exc:
        log_outbound(context["patient_id"], context["call_type"], "failure")
        raise ApiError(
            "upstream_error",
            "The outbound call was not placed",
            502,
            [str(exc)],
        ) from exc

    log_outbound(context["patient_id"], context["call_type"], "success")
    record_call_outcome(
        session,
        context["patient_id"],
        {
            "bolna_call_id": execution_id,
            "call_type": "outbound",
            "language": context["preferred_language"],
            "call_status": "queued",
            "summary": context["call_reason"],
            "extracted_data": {
                "call_type": context["call_type"],
                "call_reason": context["call_reason"],
            },
        },
    )
    return {
        "execution_id": execution_id,
        "purpose": context["call_type"],
        "call_type": context["call_type"],
        "preferred_language": context["preferred_language"],
        "patient_id": context["patient_id"],
        "patient_name": context["patient_name"],
        "call_status": "queued",
    }


def log_outbound(patient_id: object, call_type: object, outcome: str) -> None:
    """Record the attempt without the destination number or chart narrative."""
    logger.info(
        "outbound_call patient_id=%s call_type=%s outcome=%s",
        _log_patient(patient_id),
        _log_token(call_type),
        "success" if outcome == "success" else "failure",
    )


def _user_data(context: dict) -> dict[str, str]:
    payload: dict[str, str] = {}
    for key in CONTEXT_FIELDS:
        value = context.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ConflictError(
                "Outbound call was not placed because the call context was incomplete.",
                [f"{key} is missing"],
            )
        payload[key] = value.strip()
    return payload


def _log_patient(value: object) -> str:
    if not isinstance(value, str):
        return "unknown"
    try:
        return str(uuid.UUID(value.strip()))
    except (ValueError, TypeError, AttributeError):
        return "unknown"


def _log_token(value: object) -> str:
    if not isinstance(value, str):
        return "invalid"
    token = value.strip()
    if not token or len(token) > 40 or any(character.isspace() for character in token):
        return "invalid"
    return token
