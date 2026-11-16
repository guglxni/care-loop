"""Phone numbers that resolve to one chart. Stored as E.164 only."""

import re
import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Text, Uuid, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db import Base, UTCDateTime
from app.errors import ConflictError, NotFoundError, ValidationError
from app.services.patient_service import get_patient
from app.timeutil import to_iso, utcnow
from app.validation import raise_if, reject_unknown_fields

CARELOOP_LINE = "+14235838428"
PHONE_LINK_FIELDS = frozenset({"phone_e164", "label"})
_E164 = re.compile(r"^\+[1-9]\d{1,14}$")
_LABEL_MAX = 80


class PatientPhoneLink(Base):
    __tablename__ = "patient_phone_links"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True
    )
    phone_e164: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "patient_id": str(self.patient_id),
            "phone_e164": self.phone_e164,
            "label": self.label,
            "created_at": to_iso(self.created_at),
        }


def normalize_e164(value: object) -> str | None:
    """Drop spaces and accept only + followed by an E.164 digit string."""
    if not isinstance(value, str):
        return None
    compact = "".join(value.split())
    if _E164.fullmatch(compact) is None:
        return None
    return compact


def resolve_patient_id_by_phone(session: Session, number: object) -> uuid.UUID | None:
    """Return the chart id for an E.164 number, or None when nothing matches.

    Spaces are removed. The match is the stored E.164 value. The CareLoop line
    never resolves, even if a row were present.
    """
    phone = normalize_e164(number)
    if phone is None or phone == CARELOOP_LINE:
        return None
    bind = session.get_bind()
    if bind is None or not inspect(bind).has_table(PatientPhoneLink.__tablename__):
        return None
    row = _by_phone(session, phone)
    if row is None:
        return None
    return row.patient_id


def list_phone_links(session: Session, patient_id: str) -> list[PatientPhoneLink]:
    patient = get_patient(session, patient_id)
    rows = session.scalars(
        select(PatientPhoneLink)
        .where(PatientPhoneLink.patient_id == patient.id)
        .order_by(PatientPhoneLink.created_at.asc(), PatientPhoneLink.phone_e164.asc())
    ).all()
    return list(rows)


def link_phone(session: Session, patient_id: str, payload: dict) -> tuple[PatientPhoneLink, bool]:
    """Link one E.164 number to a chart. The same number cannot belong to two charts."""
    patient = get_patient(session, patient_id)
    details: list[str] = []
    reject_unknown_fields(payload, PHONE_LINK_FIELDS, details)
    phone = _require_phone(payload, details)
    label = _require_label(payload, details)
    raise_if(details)
    assert phone is not None and label is not None

    existing = _by_phone(session, phone)
    if existing is not None:
        if existing.patient_id != patient.id:
            _raise_conflict()
        return existing, False

    row = PatientPhoneLink(patient_id=patient.id, phone_e164=phone, label=label)
    try:
        with session.begin_nested():
            session.add(row)
            session.flush()
    except IntegrityError:
        raced = _by_phone(session, phone)
        if raced is None:
            raise
        if raced.patient_id != patient.id:
            _raise_conflict()
        return raced, False
    session.commit()
    session.refresh(row)
    return row, True


def unlink_phone(session: Session, patient_id: str, phone_e164: str) -> None:
    """Remove one number from this chart. A number owned by someone else stays put."""
    patient = get_patient(session, patient_id)
    phone = normalize_e164(phone_e164)
    if phone is None:
        raise ValidationError(
            "Request validation failed",
            ["phone_e164 must be a + followed by digits"],
        )
    if phone == CARELOOP_LINE:
        raise ValidationError(
            "Request validation failed",
            ["phone_e164 is the CareLoop line and cannot be linked"],
        )
    row = _by_phone(session, phone)
    if row is None or row.patient_id != patient.id:
        raise NotFoundError(
            "Phone link was not found",
            ["phone_e164 is not linked to this patient"],
        )
    session.delete(row)
    session.commit()


def ensure_phone_link(
    session: Session,
    patient_id: uuid.UUID,
    phone_e164: str,
    label: str,
    *,
    link_id: uuid.UUID | None = None,
) -> bool:
    """Insert a known-good link when it is missing. Does not commit.

    Returns True when a row was added. A number already linked to this chart
    is left unchanged. A number linked to someone else raises ConflictError.
    """
    phone = normalize_e164(phone_e164)
    text = label.strip() if isinstance(label, str) else ""
    if phone is None or phone == CARELOOP_LINE or not text:
        raise ValueError("phone link seed is not a linkable E.164 number")
    existing = _by_phone(session, phone)
    if existing is not None:
        if existing.patient_id != patient_id:
            _raise_conflict()
        return False
    session.add(
        PatientPhoneLink(
            id=link_id or uuid.uuid4(),
            patient_id=patient_id,
            phone_e164=phone,
            label=text,
        )
    )
    session.flush()
    return True


def claim_phone_link(
    session: Session,
    patient_id: uuid.UUID,
    phone_e164: str,
    label: str,
    *,
    link_id: uuid.UUID | None = None,
) -> bool:
    """Point this number at one chart, moving it off another chart when needed.

    Does not commit. Returns True when a row was inserted or reassigned.
    The CareLoop line is rejected.
    """
    phone = normalize_e164(phone_e164)
    text = label.strip() if isinstance(label, str) else ""
    if phone is None or phone == CARELOOP_LINE or not text:
        raise ValueError("phone link seed is not a linkable E.164 number")
    existing = _by_phone(session, phone)
    if existing is None:
        session.add(
            PatientPhoneLink(
                id=link_id or uuid.uuid4(),
                patient_id=patient_id,
                phone_e164=phone,
                label=text,
            )
        )
        session.flush()
        return True
    changed = False
    if existing.patient_id != patient_id:
        existing.patient_id = patient_id
        changed = True
    if existing.label != text:
        existing.label = text
        changed = True
    if changed:
        session.flush()
    return changed


def _by_phone(session: Session, phone: str) -> PatientPhoneLink | None:
    return session.scalar(select(PatientPhoneLink).where(PatientPhoneLink.phone_e164 == phone))


def _require_phone(payload: dict, details: list[str]) -> str | None:
    if "phone_e164" not in payload or payload["phone_e164"] is None:
        details.append("phone_e164 must be a + followed by digits")
        return None
    phone = normalize_e164(payload["phone_e164"])
    if phone is None:
        details.append("phone_e164 must be a + followed by digits")
        return None
    if phone == CARELOOP_LINE:
        details.append("phone_e164 is the CareLoop line and cannot be linked")
        return None
    return phone


def _require_label(payload: dict, details: list[str]) -> str | None:
    if "label" not in payload or payload["label"] is None:
        details.append("label is required")
        return None
    value = payload["label"]
    if not isinstance(value, str):
        details.append("label must be a string")
        return None
    text = value.strip()
    if not text:
        details.append("label is required")
        return None
    if len(text) > _LABEL_MAX:
        details.append("label is too long")
        return None
    return text


def _raise_conflict() -> None:
    raise ConflictError(
        "Phone number is already linked to another patient",
        ["phone_e164 is already linked to another patient"],
    )
