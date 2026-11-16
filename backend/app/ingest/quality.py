"""Timestamp, unit, and duplicate checks shared by ingest connectors.

Stored glucose stays in the unit that was submitted. ``glucose_to_mg_dl`` is
only for comparisons.
"""

import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import NoReturn

from app.errors import ValidationError
from app.validation import require_datetime

_FUTURE_SKEW = timedelta(minutes=5)
# Same factor Nightscout and the forecast helper use for comparisons.
MGDL_PER_MMOL = 18.0182

_GLUCOSE_UNITS = {
    "mg/dl": "mg/dL",
    "mmol/l": "mmol/L",
}


def _reject(details: list[str]) -> NoReturn:
    raise ValidationError("Request validation failed", details)


def _as_utc(value: object) -> datetime:
    """Return UTC. Reject naive values. Do not apply the future limit."""
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            _reject(["timestamp must include a timezone offset"])
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        details: list[str] = []
        parsed = require_datetime(
            {"timestamp": value},
            "timestamp",
            details,
            reject_far_future=False,
        )
        if parsed is None:
            _reject(details)
        return parsed
    _reject(["timestamp must be an aware datetime or an ISO 8601 string with a timezone offset"])


def require_aware_timestamp(value: object) -> datetime:
    """Return a UTC datetime. Reject naive timestamps and times more than five minutes ahead."""
    parsed = _as_utc(value)
    if parsed - datetime.now(timezone.utc) > _FUTURE_SKEW:
        _reject(["timestamp must not be more than 5 minutes in the future"])
    return parsed


def _finite_number(value: object, field: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        _reject([f"{field} must be a number"])
    if isinstance(value, float) and not math.isfinite(value):
        _reject([f"{field} must be a finite number"])
    if isinstance(value, Decimal):
        number = value
    elif isinstance(value, (int, float)):
        number = Decimal(str(value))
    elif isinstance(value, str):
        text = value.strip()
        try:
            number = Decimal(text)
        except (InvalidOperation, ValueError):
            _reject([f"{field} must be a number"])
    else:
        _reject([f"{field} must be a number"])
    if not number.is_finite():
        _reject([f"{field} must be a finite number"])
    return number


def number_token(value: object) -> str:
    """Stable decimal text so 120, 120.0, and Decimal('120.00') share a duplicate key."""
    number = _finite_number(value, "value")
    text = format(number, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def normalize_glucose(value: object, unit: object) -> tuple[float, str]:
    """Accept mg/dL or mmol/L and return the submitted number with a canonical unit label.

    The number is not converted. ``mmol`` alone is not a stored unit; Nightscout's
    site token is mapped to mmol/L before this is called.
    """
    number = _finite_number(value, "value")
    if not isinstance(unit, str) or unit.strip().lower() not in _GLUCOSE_UNITS:
        _reject(["unit must be one of: mg/dL, mmol/L"])
    canonical = _GLUCOSE_UNITS[unit.strip().lower()]
    return float(number), canonical


def glucose_to_mg_dl(value: object, unit: object) -> float:
    """Convert for comparisons only. Ingest stores the submitted unit unchanged."""
    number, canonical = normalize_glucose(value, unit)
    if canonical == "mg/dL":
        return number
    return number * MGDL_PER_MMOL


def normalize_bp_unit(unit: object) -> str:
    """Accept mmHg only."""
    if isinstance(unit, str) and unit.strip().lower() == "mmhg":
        return "mmHg"
    _reject(["unit must be mmHg"])


def _patient_token(patient_id: object) -> str:
    import uuid

    if isinstance(patient_id, uuid.UUID):
        return str(patient_id)
    try:
        return str(uuid.UUID(str(patient_id)))
    except (ValueError, TypeError, AttributeError):
        return str(patient_id)


def reading_key(
    patient_id: object,
    measurement_type: object,
    measured_at: object,
    source: object,
    device_id: object,
    value: object,
) -> tuple[str, str, str, str, str, str]:
    """Duplicate identity: patient, type, UTC time, source, device (blank if empty), value.

    Naive timestamps are rejected. A timestamp already stored in the future still
    forms a key so duplicate detection can see it; new rows use
    ``require_aware_timestamp`` before they are inserted.
    """
    moment = _as_utc(measured_at)
    device = "" if device_id is None else str(device_id)
    return (
        _patient_token(patient_id),
        str(measurement_type),
        moment.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        str(source),
        device,
        number_token(value),
    )


def is_duplicate(existing_keys, key) -> bool:
    return key in existing_keys
