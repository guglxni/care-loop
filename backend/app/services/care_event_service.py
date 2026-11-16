"""Care events. The description is stored as submitted. No advice is generated."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CareEvent
from app.services.patient_service import get_patient
from app.timeutil import utcnow
from app.validation import optional_choice, raise_if, reject_unknown_fields, require_choice

EVENT_FIELDS = frozenset({"event_type", "event_description", "priority", "status"})
PRIORITIES = ("low", "medium", "high")
STATUSES = ("open", "acknowledged", "resolved")


def list_care_events(session: Session, patient_id: str) -> list[CareEvent]:
    patient = get_patient(session, patient_id)
    return list(
        session.scalars(
            select(CareEvent)
            .where(CareEvent.patient_id == patient.id)
            .order_by(CareEvent.created_at.desc())
        ).all()
    )


def create_care_event(session: Session, patient_id: str, payload: dict) -> CareEvent:
    patient = get_patient(session, patient_id)
    details: list[str] = []
    reject_unknown_fields(payload, EVENT_FIELDS, details)
    event_type = _required_text(payload, "event_type", details, max_length=120, strip=True)
    event_description = _required_text(
        payload, "event_description", details, max_length=4000, strip=False
    )
    priority = require_choice(payload, "priority", PRIORITIES, details)
    if "status" in payload and payload["status"] is not None:
        status = optional_choice(payload, "status", STATUSES, details) or "open"
    else:
        status = "open"
    raise_if(details)
    assert event_type is not None and event_description is not None and priority is not None
    row = CareEvent(
        patient_id=patient.id,
        event_type=event_type,
        event_description=event_description,
        priority=priority,
        status=status,
        resolved_at=utcnow() if status == "resolved" else None,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _required_text(
    payload: dict,
    field: str,
    details: list[str],
    *,
    max_length: int,
    strip: bool,
) -> str | None:
    if field not in payload or payload[field] is None:
        details.append(f"{field} is required")
        return None
    value = payload[field]
    if not isinstance(value, str) or not value.strip():
        details.append(f"{field} is required")
        return None
    if len(value) > max_length:
        details.append(f"{field} is too long")
        return None
    return value.strip() if strip else value
