"""UTC timestamps stored by the API and returned as ISO 8601."""

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    text = value.astimezone(timezone.utc).isoformat()
    if text.endswith("+00:00"):
        return text[:-6] + "Z"
    return text


def json_number(value: float | int | None) -> float | int | None:
    if value is None:
        return None
    number = float(value)
    if number.is_integer():
        return int(number)
    return number
