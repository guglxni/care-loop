"""Shared request checks. Clinical range rules live in the services that own them."""

import math
import uuid
from datetime import datetime, timedelta, timezone

from flask import request

from app.errors import ValidationError

CLINICAL_MUTATION_FIELDS = frozenset(
    {
        "diagnosis",
        "diagnosis_date",
        "condition",
        "condition_type",
        "conditions",
        "prescription",
        "medication",
        "medication_name",
        "medications",
        "prescribed_dosage",
        "dosage",
        "dose",
        "new_dose",
        "new_dosage",
        "frequency",
        "schedule",
        "treating_clinician",
        "prescribing_clinician",
        "start_date",
        "end_date",
        "active",
        "interpretation",
        "classification",
        "label",
        "advice",
        "recommendation",
        "high",
        "low",
        "hyperglycemia",
        "hypoglycemia",
    }
)

_NO_PRESCRIBE = (
    "This endpoint does not record a diagnosis, prescription, or dose change."
)
_FUTURE_SKEW = timedelta(minutes=5)


def raise_if(details: list[str]) -> None:
    if not details:
        return
    message = "Request validation failed"
    if any("does not record a diagnosis" in item for item in details):
        message = _NO_PRESCRIBE
    raise ValidationError(message, details)


def read_json_object() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError("Request validation failed", ["body must be a JSON object"])
    return data


def reject_unknown_fields(
    payload: dict,
    allowed: frozenset[str] | set[str],
    details: list[str],
    *,
    profile: bool = False,
) -> None:
    for key in payload:
        if key in allowed:
            continue
        if key in CLINICAL_MUTATION_FIELDS:
            details.append(
                f"{key} cannot be changed. This endpoint does not record a diagnosis, prescription, or dose change."
            )
        elif profile:
            details.append(f"{key} is not an updatable profile field")
        else:
            details.append(f"{key} is not accepted")


def parse_uuid(value: object, field: str, details: list[str]) -> uuid.UUID | None:
    if not isinstance(value, str) or not value.strip():
        details.append(f"{field} must be a UUID")
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        details.append(f"{field} must be a UUID")
        return None


def require_choice(
    payload: dict,
    field: str,
    allowed: tuple[str, ...],
    details: list[str],
) -> str | None:
    if field not in payload or payload[field] is None or payload[field] == "":
        details.append(f"{field} is required")
        return None
    value = payload[field]
    if value not in allowed:
        details.append(f"{field} must be one of: {', '.join(allowed)}")
        return None
    return value


def optional_choice(
    payload: dict,
    field: str,
    allowed: tuple[str, ...],
    details: list[str],
) -> str | None:
    if field not in payload or payload[field] is None or payload[field] == "":
        return None
    value = payload[field]
    if value not in allowed:
        details.append(f"{field} must be one of: {', '.join(allowed)}")
        return None
    return value


def require_number(payload: dict, field: str, details: list[str]) -> float | None:
    if field not in payload or payload[field] is None:
        details.append(f"{field} is required")
        return None
    return _number(payload[field], field, details)


def optional_number(payload: dict, field: str, details: list[str]) -> float | None:
    if field not in payload or payload[field] is None:
        return None
    return _number(payload[field], field, details)


def _number(value: object, field: str, details: list[str]) -> float | None:
    if isinstance(value, str):
        text = value.strip()
        try:
            parsed = float(text)
        except ValueError:
            details.append(f"{field} must be a number")
            return None
        if not math.isfinite(parsed):
            details.append(f"{field} must be a finite number")
            return None
        if parsed.is_integer() and "." not in text and "e" not in text.lower():
            return float(int(parsed))
        return parsed
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        details.append(f"{field} must be a number")
        return None
    if isinstance(value, float) and not math.isfinite(value):
        details.append(f"{field} must be a finite number")
        return None
    return float(value)


def require_datetime(
    payload: dict,
    field: str,
    details: list[str],
    *,
    reject_far_future: bool = False,
) -> datetime | None:
    if field not in payload or payload[field] is None or payload[field] == "":
        details.append(f"{field} is required")
        return None
    value = payload[field]
    if not isinstance(value, str):
        details.append(f"{field} must be an ISO 8601 string with a timezone offset")
        return None
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        details.append(f"{field} must be an ISO 8601 string with a timezone offset")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        details.append(f"{field} must include a timezone offset")
        return None
    utc_value = parsed.astimezone(timezone.utc)
    if reject_far_future and utc_value - datetime.now(timezone.utc) > _FUTURE_SKEW:
        details.append(f"{field} must not be more than 5 minutes in the future")
        return None
    return utc_value


def optional_text(
    payload: dict,
    field: str,
    details: list[str],
    *,
    max_length: int,
) -> str | None:
    if field not in payload or payload[field] is None:
        return None
    value = payload[field]
    if not isinstance(value, str):
        details.append(f"{field} must be a string")
        return None
    if len(value) > max_length:
        details.append(f"{field} is too long")
        return None
    stripped = value.strip()
    return stripped or None


def normalize_contact_number(value: object, details: list[str]) -> str | None:
    if not isinstance(value, str):
        details.append("contact_number must be a string starting with +")
        return None
    normalized = "".join(value.split())
    if len(normalized) < 2 or not normalized.startswith("+"):
        details.append("contact_number must start with +")
        return None
    if len(normalized) > 32:
        details.append("contact_number is too long")
        return None
    return normalized
