"""Common blood-pressure ingest for manual entry and CSV import.

There is no Bluetooth connector. Channel ``bluetooth`` is refused with HTTP 501
``not_connected``. This module does not scan, pair, or open a device socket.

Manual channel
    ``ingest_origin`` is ``manual``. ``source`` must be ``manual``,
    ``home_monitor``, or ``clinic``. A ``synthetic`` or ``device_reported``
    flag on a manual row does not change the origin.

CSV channel
    Do not stamp every imported row with ``ingest_origin`` ``manual``.
    Source and origin are chosen per row:

    * ``synthetic`` true sets ``ingest_origin`` to ``synthetic``.
    * Otherwise, when the row says device — ``device_reported`` true, a true
      ``device`` flag, or ``source`` ``device`` — store ``source``
      ``home_monitor`` and ``ingest_origin`` ``device``.
    * Otherwise store ``source`` ``manual`` and ``ingest_origin`` ``manual``.

    A normal imported CSV of home readings uses ``source`` ``home_monitor``
    and ``ingest_origin`` ``device`` only when that row has
    ``device_reported`` true (or the row says ``device``). Rows without that
    signal default to ``source`` ``manual`` and ``ingest_origin`` ``manual``,
    including a source cell of ``home_monitor`` or ``clinic``.

Duplicates follow the glucose rule in ``app.ingest.quality.reading_key``:
same patient, measurement type, ``measured_at``, source, device id (blank
when empty), and value are skipped.

``reading_service.record_blood_pressure`` writes ``source`` and the systolic,
diastolic, and pulse rows, but it cannot set ``ingest_origin`` and it does
not skip duplicates. Rows are written here in that same shape. ``ingest_origin``
is persisted only when ``health_readings.ingest_origin`` exists.
"""

import csv
from io import StringIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ValidationError
from app.ingest.quality import is_duplicate, normalize_bp_unit, reading_key, require_aware_timestamp
from app.models import HealthReading
from app.services.patient_service import get_patient
from app.timeutil import to_iso
from app.validation import (
    optional_number,
    optional_text,
    raise_if,
    reject_unknown_fields,
    require_choice,
    require_number,
)

NOT_CONNECTED = {
    "error": {
        "code": "not_connected",
        "message": "Bluetooth blood pressure devices are not connected.",
    }
}
TOP_FIELDS = frozenset({"channel", "rows", "csv_text", "unit"})
ROW_FIELDS = frozenset(
    {
        "systolic",
        "diastolic",
        "pulse",
        "measured_at",
        "source",
        "unit",
        "device_id",
        "synthetic",
        "device_reported",
        "device",
    }
)
MANUAL_SOURCES = ("manual", "home_monitor", "clinic")
CSV_COLUMNS = ROW_FIELDS | {"notes"}
MAX_ROWS = 500


class BluetoothUnavailable(Exception):
    """Channel bluetooth has no connector."""


def ingest_blood_pressure(session: Session, patient_id: str, payload: dict) -> tuple[dict, int]:
    channel = _raw_channel(payload)
    if channel == "bluetooth":
        raise BluetoothUnavailable()
    details: list[str] = []
    reject_unknown_fields(payload, TOP_FIELDS, details)
    if channel is None:
        details.append("channel must be one of: manual, csv")
        raise_if(details)
    assert channel is not None
    default_unit = payload.get("unit") if "unit" in payload else None
    rows = _input_rows(payload, channel, details)
    raise_if(details)
    prepared = [
        _prepare_row(channel, row, index, default_unit, details) for index, row in enumerate(rows)
    ]
    raise_if(details)
    patient = get_patient(session, patient_id)
    stored, skipped = _persist(session, patient.id, [row for row in prepared if row is not None])
    status = 201 if stored else 200
    return {
        "channel": channel,
        "readings": stored,
        "skipped_duplicates": skipped,
    }, status


def _raw_channel(payload: dict) -> str | None:
    channel = payload.get("channel")
    if not isinstance(channel, str):
        return None
    cleaned = channel.strip().lower()
    if cleaned in {"manual", "csv", "bluetooth"}:
        return cleaned
    return None


def _input_rows(payload: dict, channel: str, details: list[str]) -> list[dict]:
    has_csv = "csv_text" in payload and payload.get("csv_text") not in (None, "")
    has_rows = "rows" in payload and payload.get("rows") not in (None, "")
    if channel == "manual" and has_csv:
        details.append("csv_text is only accepted when channel is csv")
    if has_csv and has_rows:
        details.append("send rows or csv_text, not both")
        return []
    if channel == "csv" and has_csv:
        return _parse_csv(payload.get("csv_text"), details)
    if "rows" not in payload or payload.get("rows") is None:
        details.append("rows is required")
        return []
    rows = payload["rows"]
    if not isinstance(rows, list):
        details.append("rows must be a list")
        return []
    if not rows:
        details.append("rows is required")
        return []
    if len(rows) > MAX_ROWS:
        details.append("rows is too long")
        return []
    cleaned = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            details.append(f"rows[{index}] must be an object")
            continue
        unknown = [key for key in row if key not in ROW_FIELDS]
        for key in unknown:
            details.append(f"rows[{index}].{key} is not accepted")
        cleaned.append(row)
    return cleaned


def _parse_csv(value, details: list[str]) -> list[dict]:
    if not isinstance(value, str):
        details.append("csv_text must be a string")
        return []
    if len(value) > 500_000:
        details.append("csv_text is too long")
        return []
    reader = csv.DictReader(StringIO(value))
    fieldnames = reader.fieldnames or []
    headers = {(name or "").strip().lower() for name in fieldnames}
    required = {"systolic", "diastolic", "measured_at"}
    if not required <= headers:
        details.append("csv_text must include systolic, diastolic, and measured_at columns")
        return []
    rows = []
    for raw in reader:
        if raw is None:
            continue
        normalized = {
            (key or "").strip().lower(): (item.strip() if isinstance(item, str) else item)
            for key, item in raw.items()
            if key is not None
        }
        if not any(normalized.get(name) for name in ("systolic", "diastolic", "measured_at")):
            continue
        row = {key: normalized.get(key) for key in CSV_COLUMNS if key in normalized}
        for number_field in ("systolic", "diastolic", "pulse"):
            cell = row.get(number_field)
            if cell in (None, ""):
                row[number_field] = None
                continue
            try:
                number = float(cell)
            except (TypeError, ValueError):
                continue
            row[number_field] = int(number) if number.is_integer() else number
        if row.get("pulse") is None and "pulse" not in normalized:
            row.pop("pulse", None)
        rows.append(row)
        if len(rows) > MAX_ROWS:
            details.append("rows is too long")
            return []
    if not rows:
        details.append("rows is required")
    return rows


def _prepare_row(channel: str, row: dict, index: int, default_unit, details: list[str]) -> dict | None:
    prefix = f"rows[{index}]."
    before = len(details)
    systolic = _number(row, "systolic", details, prefix, required=True)
    diastolic = _number(row, "diastolic", details, prefix, required=True)
    pulse = _number(row, "pulse", details, prefix, required=False)
    measured_at = _timestamp(row, prefix, details)
    unit = _unit(row, default_unit, prefix, details)
    device_box: list[str] = []
    device_id = optional_text(row, "device_id", device_box, max_length=200)
    for item in device_box:
        details.append(f"{prefix}{item}")
    source, origin = _source_and_origin(channel, row, prefix, details)
    if systolic is not None and not 70 <= systolic <= 250:
        details.append(f"{prefix}systolic must be between 70 and 250")
    if diastolic is not None and not 40 <= diastolic <= 150:
        details.append(f"{prefix}diastolic must be between 40 and 150")
    if systolic is not None and diastolic is not None and not systolic > diastolic:
        details.append(f"{prefix}systolic must be greater than diastolic")
    if pulse is not None and not 30 <= pulse <= 220:
        details.append(f"{prefix}pulse must be between 30 and 220")
    if len(details) != before or measured_at is None or source is None or unit is None:
        return None
    assert systolic is not None and diastolic is not None
    return {
        "systolic": systolic,
        "diastolic": diastolic,
        "pulse": pulse,
        "measured_at": measured_at,
        "unit": unit,
        "source": source,
        "ingest_origin": origin,
        "device_id": device_id,
    }


def _number(row: dict, field: str, details: list[str], prefix: str, *, required: bool):
    box: list[str] = []
    if required:
        value = require_number(row, field, box)
    else:
        value = optional_number(row, field, box)
    for item in box:
        details.append(f"{prefix}{item}")
    return value


def _timestamp(row: dict, prefix: str, details: list[str]):
    try:
        return require_aware_timestamp(row.get("measured_at"))
    except ValidationError as exc:
        for item in exc.details or [exc.message]:
            details.append(f"{prefix}{item}")
        return None


def _unit(row: dict, default_unit, prefix: str, details: list[str]) -> str | None:
    raw = row.get("unit") if "unit" in row and row.get("unit") not in (None, "") else default_unit
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raw = "mmHg"
    try:
        return normalize_bp_unit(raw)
    except ValidationError as exc:
        for item in exc.details or [exc.message]:
            details.append(f"{prefix}{item}")
        return None


def _source_and_origin(
    channel: str,
    row: dict,
    prefix: str,
    details: list[str],
) -> tuple[str | None, str | None]:
    if channel == "manual":
        box: list[str] = []
        source = require_choice(row, "source", MANUAL_SOURCES, box)
        for item in box:
            details.append(f"{prefix}{item}")
        return source, "manual"
    source, origin = classify_csv_row(row)
    return source, origin


def classify_csv_row(row: dict) -> tuple[str, str]:
    """Return ``(source, ingest_origin)`` for one CSV row."""

    says_device = _says_device(row)
    source = "home_monitor" if says_device else "manual"
    if _flag(row.get("synthetic")):
        return source, "synthetic"
    if says_device:
        return source, "device"
    return source, "manual"


def _says_device(row: dict) -> bool:
    if _flag(row.get("device_reported")) or _flag(row.get("device")):
        return True
    source = row.get("source")
    return isinstance(source, str) and source.strip().lower() == "device"


def _flag(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return False


def _bind_ingest_origin() -> bool:
    column = HealthReading.__table__.columns.get("ingest_origin")
    if column is None:
        return False
    if "ingest_origin" not in HealthReading.__mapper__.attrs:
        HealthReading.__mapper__.add_property("ingest_origin", column)
    return True


def _persist(session: Session, patient_id, prepared: list[dict]) -> tuple[list[dict], list[dict]]:
    origin_mapped = _bind_ingest_origin()
    existing = session.scalars(
        select(HealthReading).where(HealthReading.patient_id == patient_id)
    ).all()
    known = {
        _identity(row.patient_id, row.measurement_type, row.measured_at, row.source, row.device_id, row.value)
        for row in existing
    }
    stored_rows = []
    skipped = []
    for item in prepared:
        components = [
            ("systolic_blood_pressure", item["systolic"], item["diastolic"], item["unit"]),
            ("diastolic_blood_pressure", item["diastolic"], None, item["unit"]),
        ]
        if item["pulse"] is not None:
            components.append(("pulse", item["pulse"], None, "bpm"))
        for measurement_type, value, secondary, unit in components:
            key = _identity(
                patient_id,
                measurement_type,
                item["measured_at"],
                item["source"],
                item["device_id"],
                value,
            )
            if is_duplicate(known, key):
                skipped.append(
                    {
                        "measurement_type": measurement_type,
                        "value": _public_number(value),
                        "measured_at": to_iso(item["measured_at"]),
                        "source": item["source"],
                        "ingest_origin": item["ingest_origin"],
                    }
                )
                continue
            reading = HealthReading(
                patient_id=patient_id,
                measurement_type=measurement_type,
                value=value,
                secondary_value=secondary,
                unit=unit,
                measurement_context=None,
                measured_at=item["measured_at"],
                source=item["source"],
                device_id=item["device_id"],
                data_quality="valid",
                support=None,
                **({"ingest_origin": item["ingest_origin"]} if origin_mapped else {}),
            )
            session.add(reading)
            stored_rows.append((reading, item["ingest_origin"]))
            known.add(key)
    if stored_rows:
        try:
            session.commit()
        except Exception:
            session.rollback()
            raise
        for reading, _origin in stored_rows:
            session.refresh(reading)
    payloads = []
    for reading, origin in stored_rows:
        body = reading.to_dict()
        body["ingest_origin"] = origin
        payloads.append(body)
    return payloads, skipped


def _identity(patient_id, measurement_type, measured_at, source, device_id, value):
    return reading_key(patient_id, measurement_type, measured_at, source, device_id, value)


def _public_number(value) -> int | float:
    number = float(value)
    if number.is_integer():
        return int(number)
    return number

