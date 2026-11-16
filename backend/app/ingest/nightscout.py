"""Nightscout v1 entry ingest.

Live sync reads GET {NIGHTSCOUT_URL}/api/v1/entries.json and sends
NIGHTSCOUT_API_TOKEN in the api-secret header unchanged. The token is the
hash Nightscout documents for that header; this module does not hash it again.

The mock path replays the fixture. Those rows use source glucometer and
ingest_origin synthetic. They are not a CGM feed. Live rows use source cgm
and ingest_origin device. This process does not pair a physical transmitter.
"""

import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import urllib.error
import urllib.request

from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import NotFoundError, ValidationError
from app.ingest.models import IngestSyncRun, ensure_ingest_schema
from app.ingest.quality import (
    is_duplicate,
    normalize_glucose,
    number_token,
    reading_key,
    require_aware_timestamp,
)
from app.models import HealthReading
from app.services.patient_service import get_patient
from app.timeutil import utcnow

logger = logging.getLogger(__name__)

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "nightscout_entries.json"
FIXTURE_SUPPORT = "synthetic_nightscout_fixture"
ENTRY_COUNT = 288
TIMEOUT_SECONDS = 10
MAX_BODY_BYTES = 2_000_000

ORIGIN_SYNTHETIC = "synthetic"
ORIGIN_DEVICE = "device"
SOURCE_GLUCOMETER = "glucometer"
SOURCE_CGM = "cgm"
CONNECTOR_MOCK = "nightscout_mock"
CONNECTOR_LIVE = "nightscout"

MISSING_MESSAGE = (
    "Nightscout is unavailable because NIGHTSCOUT_URL or NIGHTSCOUT_API_TOKEN is not set."
)
UNAVAILABLE_HTTP = (
    "Nightscout is unavailable because the entries request failed. No readings were stored."
)
BAD_URL_MESSAGE = (
    "NIGHTSCOUT_URL must be an http or https URL and must not include a username or password."
)
UNITS_UNREAD = (
    "Site units were not read. Entries that do not name units are stored as mg/dL."
)
MOCK_MESSAGE = (
    "Synthetic Nightscout fixture stored with source glucometer and ingest_origin synthetic. "
    "support is synthetic_nightscout_fixture. These rows are not from a live sensor or a physical CGM."
)
LIVE_MESSAGE = (
    "Nightscout entries stored with source cgm and ingest_origin device. "
    "Direction, when the entry has one, is stored in support. "
    "A physical CGM transmitter is not connected."
)


class NightscoutUnavailable(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass
class IngestResult:
    http_status: int
    message: str
    body: dict | None = None


@dataclass(frozen=True)
class PreparedEntry:
    measured_at: datetime
    value: Decimal
    unit: str
    device_id: str | None
    support: str | None


def map_nightscout_unit(raw: object) -> str | None:
    """Map a Nightscout units token onto mg/dL or mmol/L. Unknown tokens return None."""
    if not isinstance(raw, str):
        return None
    token = "".join(raw.split()).lower()
    if token in {"mg/dl", "mgdl"}:
        return "mg/dL"
    if token in {"mmol/l", "mmol", "mmoll"}:
        return "mmol/L"
    return None


def load_fixture() -> list:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise RuntimeError("Nightscout fixture must be a JSON array")
    return payload


def ingest_fixture(session: Session, patient_id: str) -> dict:
    patient = get_patient(session, patient_id)
    return _ingest(
        session,
        patient.id,
        load_fixture(),
        connector=CONNECTOR_MOCK,
        ingest_origin=ORIGIN_SYNTHETIC,
        source=SOURCE_GLUCOMETER,
        site_unit=None,
        units_note=None,
        base_message=MOCK_MESSAGE,
        started=utcnow(),
        synthetic=True,
    )


def sync_live(session: Session, patient_id: str) -> IngestResult:
    patient = get_patient(session, patient_id)
    started = utcnow()
    raw_url = os.environ.get("NIGHTSCOUT_URL", "").strip()
    token = os.environ.get("NIGHTSCOUT_API_TOKEN", "").strip()
    if not raw_url or not token:
        _save_run(
            session,
            patient_id=patient.id,
            connector=CONNECTOR_LIVE,
            status="unavailable",
            started=started,
            inserted=0,
            duplicate=0,
            skipped=0,
            message=MISSING_MESSAGE,
        )
        return IngestResult(503, MISSING_MESSAGE)
    try:
        base = site_base(raw_url)
        entries = fetch_entries(base, token)
    except NightscoutUnavailable as exc:
        _save_run(
            session,
            patient_id=patient.id,
            connector=CONNECTOR_LIVE,
            status="unavailable",
            started=started,
            inserted=0,
            duplicate=0,
            skipped=0,
            message=exc.message,
        )
        return IngestResult(503, exc.message)
    site_unit, units_note = fetch_site_unit(base, token)
    body = _ingest(
        session,
        patient.id,
        entries,
        connector=CONNECTOR_LIVE,
        ingest_origin=ORIGIN_DEVICE,
        source=SOURCE_CGM,
        site_unit=site_unit,
        units_note=units_note,
        base_message=LIVE_MESSAGE,
        started=started,
        synthetic=False,
    )
    return IngestResult(201, body["message"], body)


def latest_run(session: Session, patient_id: str) -> IngestSyncRun:
    patient = get_patient(session, patient_id)
    run = session.scalars(
        select(IngestSyncRun)
        .where(IngestSyncRun.patient_id == patient.id)
        .order_by(IngestSyncRun.started_at.desc(), IngestSyncRun.id.desc())
    ).first()
    if run is None:
        raise NotFoundError("No ingest sync has been recorded for this patient")
    return run


def site_base(url: str) -> str:
    parsed = urlsplit(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise NightscoutUnavailable(BAD_URL_MESSAGE)
    if parsed.username or parsed.password:
        raise NightscoutUnavailable(BAD_URL_MESSAGE)
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def fetch_entries(base: str, token: str) -> list:
    payload = _get_json(f"{base}/api/v1/entries.json?count={ENTRY_COUNT}", token)
    if not isinstance(payload, list):
        raise NightscoutUnavailable(UNAVAILABLE_HTTP)
    return payload


def fetch_site_unit(base: str, token: str) -> tuple[str | None, str | None]:
    """Read settings.units. A status failure does not discard entries already fetched."""
    try:
        payload = _get_json(f"{base}/api/v1/status.json", token)
    except NightscoutUnavailable:
        logger.warning("Nightscout status request failed; unlabeled entries default to mg/dL")
        return None, UNITS_UNREAD
    unit = None
    if isinstance(payload, dict):
        settings = payload.get("settings")
        if isinstance(settings, dict):
            unit = map_nightscout_unit(settings.get("units"))
    if unit is None:
        return None, UNITS_UNREAD
    return unit, None


def _urlopen(request, timeout: float):
    return urllib.request.urlopen(request, timeout=timeout)


def _get_json(url: str, token: str) -> object:
    request = urllib.request.Request(
        url,
        headers={
            "api-secret": token,
            "Accept": "application/json",
            "User-Agent": "CareLoop-Ingest",
        },
        method="GET",
    )
    try:
        with _urlopen(request, TIMEOUT_SECONDS) as response:
            raw = response.read(MAX_BODY_BYTES + 1)
    except urllib.error.HTTPError as exc:
        logger.warning("Nightscout HTTP %s", exc.code)
        raise NightscoutUnavailable(UNAVAILABLE_HTTP) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.warning("Nightscout request failed: %s", type(exc).__name__)
        raise NightscoutUnavailable(UNAVAILABLE_HTTP) from exc
    if len(raw) > MAX_BODY_BYTES:
        raise NightscoutUnavailable(UNAVAILABLE_HTTP)
    try:
        return json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NightscoutUnavailable(UNAVAILABLE_HTTP) from exc


def _ingest(
    session: Session,
    patient_id: uuid.UUID,
    entries: list,
    *,
    connector: str,
    ingest_origin: str,
    source: str,
    site_unit: str | None,
    units_note: str | None,
    base_message: str,
    started: datetime,
    synthetic: bool,
) -> dict:
    ensure_ingest_schema()
    keys = _existing_keys(session, patient_id)
    inserted = 0
    duplicate = 0
    skipped = 0
    table = HealthReading.__table__
    for entry in entries:
        prepared = prepare_entry(entry, site_unit=site_unit, synthetic=synthetic)
        if prepared is None:
            skipped += 1
            continue
        key = reading_key(
            patient_id,
            "blood_glucose",
            prepared.measured_at,
            source,
            prepared.device_id,
            prepared.value,
        )
        if is_duplicate(keys, key):
            duplicate += 1
            continue
        try:
            with session.begin_nested():
                session.execute(
                    insert(table).values(
                        id=uuid.uuid4(),
                        patient_id=patient_id,
                        measurement_type="blood_glucose",
                        value=prepared.value,
                        secondary_value=None,
                        unit=prepared.unit,
                        measurement_context=None,
                        measured_at=prepared.measured_at,
                        source=source,
                        device_id=prepared.device_id,
                        data_quality="valid",
                        support=prepared.support,
                        created_at=utcnow(),
                        ingest_origin=ingest_origin,
                    )
                )
        except IntegrityError as exc:
            if not _unique_violation(exc):
                raise
            duplicate += 1
            continue
        keys.add(key)
        inserted += 1
    status = "partial" if skipped else "ok"
    message = _result_message(base_message, skipped, units_note)
    run = _save_run(
        session,
        patient_id=patient_id,
        connector=connector,
        status=status,
        started=started,
        inserted=inserted,
        duplicate=duplicate,
        skipped=skipped,
        message=message,
    )
    body = run.to_dict()
    body["ingest_origin"] = ingest_origin
    body["source"] = source
    if synthetic:
        body["support"] = FIXTURE_SUPPORT
    return body


def prepare_entry(entry: object, *, site_unit: str | None, synthetic: bool) -> PreparedEntry | None:
    if not isinstance(entry, dict) or entry.get("type") != "sgv":
        return None
    sgv = entry.get("sgv")
    if sgv is None or sgv == "":
        return None
    measured = _entry_time(entry)
    if measured is None:
        return None
    unit = _entry_unit(entry, site_unit)
    if unit is None:
        return None
    try:
        _submitted, canonical = normalize_glucose(sgv, unit)
        stored = Decimal(number_token(sgv))
    except ValidationError:
        return None
    if synthetic:
        support = FIXTURE_SUPPORT
    else:
        support = _direction(entry.get("direction"))
    return PreparedEntry(
        measured_at=measured,
        value=stored,
        unit=canonical,
        device_id=_device(entry.get("device")),
        support=support,
    )


def _entry_time(entry: dict) -> datetime | None:
    raw_string = entry.get("dateString")
    if isinstance(raw_string, str) and raw_string.strip():
        try:
            return require_aware_timestamp(raw_string)
        except ValidationError:
            pass
    raw_date = entry.get("date")
    if isinstance(raw_date, bool) or not isinstance(raw_date, (int, float)):
        return None
    try:
        moment = datetime.fromtimestamp(float(raw_date) / 1000.0, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None
    try:
        return require_aware_timestamp(moment)
    except ValidationError:
        return None


def _entry_unit(entry: dict, site_unit: str | None) -> str | None:
    if "units" in entry and entry.get("units") not in (None, ""):
        return map_nightscout_unit(entry.get("units"))
    if site_unit in {"mg/dL", "mmol/L"}:
        return site_unit
    return "mg/dL"


def _device(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    return text[:200]


def _direction(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    return text[:80]


def _existing_keys(session: Session, patient_id: uuid.UUID) -> set:
    rows = session.execute(
        select(
            HealthReading.patient_id,
            HealthReading.measurement_type,
            HealthReading.measured_at,
            HealthReading.source,
            HealthReading.device_id,
            HealthReading.value,
        ).where(HealthReading.patient_id == patient_id)
    )
    keys = set()
    for patient, kind, measured_at, source, device_id, value in rows:
        keys.add(reading_key(patient, kind, measured_at, source, device_id, value))
    return keys


def _unique_violation(exc: IntegrityError) -> bool:
    original = getattr(exc, "orig", None)
    text = str(original if original is not None else exc).lower()
    return "unique" in text or "health_readings_dedupe_uidx" in text


def _result_message(base: str, skipped: int, note: str | None) -> str:
    parts = [base]
    if note:
        parts.append(note)
    if skipped:
        parts.append(
            f"{skipped} entries were skipped because they were incomplete, not type sgv, "
            "or failed the timestamp or unit checks."
        )
    return " ".join(parts)


def _save_run(
    session: Session,
    *,
    patient_id: uuid.UUID,
    connector: str,
    status: str,
    started: datetime,
    inserted: int,
    duplicate: int,
    skipped: int,
    message: str,
) -> IngestSyncRun:
    run = IngestSyncRun(
        patient_id=patient_id,
        connector=connector,
        status=status,
        started_at=started,
        finished_at=utcnow(),
        inserted_count=inserted,
        duplicate_count=duplicate,
        skipped_count=skipped,
        message=message,
    )
    session.add(run)
    session.commit()
    return run
