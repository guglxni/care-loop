"""Prescription and lab extract routes.

Stores a ``documents`` row when ``app.models.Document`` exists, and stores the
extraction on ``document_extractions``. The fallback model is registered on
``Base.metadata`` and is created only when that metadata creates tables. This
module does not run DDL and does not insert into ``medications``.

``confirmed`` stays false until ``POST .../confirm``. Confirming still does
not create a medication.
"""

import json
import uuid
from datetime import datetime

from flask import Blueprint, jsonify
from sqlalchemy import Boolean, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UTCDateTime, get_db
from app.errors import NotFoundError
from app.ingest.documents import (
    NOT_A_CONFIRMED_PRESCRIPTION,
    chart_document_type,
    extract_fields,
    resolve_document_text,
)
from app.models import JSONDocument
from app.services.patient_service import get_patient
from app.timeutil import to_iso, utcnow
from app.validation import raise_if, read_json_object, reject_unknown_fields, require_choice

bp = Blueprint("document_routes", __name__, url_prefix="/api/v1")

_EXTRACT_FIELDS = frozenset({"document_type", "filename", "text", "file_base64", "file"})
_CONFIRM_FIELDS = frozenset({"confirmed_by"})
_DOCUMENT_TYPES = ("prescription", "lab_report", "hba1c")
_CONFIRMED_BY = ("patient", "clinician")
_PAYLOAD_COLUMNS = ("extracted", "extracted_fields", "payload", "fields", "result")


def _imported_extraction():
    try:
        from app.ingest.models import DocumentExtraction as Imported
    except ImportError:
        return None
    table = getattr(Imported, "__table__", None)
    if table is None:
        return None
    return Imported


_ImportedExtraction = _imported_extraction()

if _ImportedExtraction is None:

    class DocumentExtraction(Base):
        """Fallback extraction row. Used when ``app.ingest.models`` has none."""

        __tablename__ = "document_extractions"

        id: Mapped[uuid.UUID] = mapped_column(
            Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
        )
        patient_id: Mapped[uuid.UUID] = mapped_column(
            Uuid(as_uuid=True), nullable=False, index=True
        )
        document_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
        document_type: Mapped[str] = mapped_column(Text, nullable=False)
        filename: Mapped[str] = mapped_column(Text, nullable=False)
        extraction_status: Mapped[str] = mapped_column(Text, nullable=False)
        extracted: Mapped[dict] = mapped_column(JSONDocument, nullable=False)
        confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
        confirmed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
        message: Mapped[str] = mapped_column(Text, nullable=False)
        extraction_error: Mapped[str | None] = mapped_column(Text, nullable=True)
        created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)

    ExtractionModel = DocumentExtraction
else:
    DocumentExtraction = _ImportedExtraction
    ExtractionModel = _ImportedExtraction


def _collapse_duplicate_reading_indexes() -> None:
    """Drop repeated dedupe indexes before metadata.create_all.

    ``ensure_ingest_schema`` compares a string with ``table.indexes``, which
    holds Index objects, so each call appends another index of the same name.
    SQLite then rejects the second CREATE INDEX.
    """

    from app.models import HealthReading

    table = HealthReading.__table__
    kept: set[str] = set()
    for index in list(table.indexes):
        if index.name in kept:
            table.indexes.discard(index)
        else:
            kept.add(index.name)


def _guard_ingest_schema() -> None:
    import app.ingest.models as ingest_models

    _collapse_duplicate_reading_indexes()
    current = ingest_models.ensure_ingest_schema
    if getattr(current, "_deduped", False):
        return

    def guarded() -> None:
        current()
        _collapse_duplicate_reading_indexes()

    guarded._deduped = True  # type: ignore[attr-defined]
    ingest_models.ensure_ingest_schema = guarded


_guard_ingest_schema()


def _document_model():
    try:
        from app.models import Document
    except ImportError:
        return None
    if getattr(Document, "__tablename__", None) != "documents":
        return None
    return Document


def _columns(model) -> set[str]:
    return set(model.__table__.columns.keys())


def _write(model, logical: dict):
    columns = _columns(model)
    aliases = {
        "extracted": _PAYLOAD_COLUMNS,
        "message": ("message", "disclaimer", "note"),
        "filename": ("filename", "file_name", "source_filename"),
        "extraction_error": ("extraction_error", "error"),
        "extraction_status": ("extraction_status", "status"),
    }
    kwargs = {}
    for key, value in logical.items():
        names = aliases.get(key, (key,))
        for name in names:
            if name in columns:
                kwargs[name] = value
                break
    return model(**kwargs)


def _raw_payload(row) -> dict:
    for name in _PAYLOAD_COLUMNS:
        if name not in _columns(ExtractionModel):
            continue
        value = getattr(row, name, None)
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                return {}
        if isinstance(value, dict):
            inner = value.get("extracted")
            if isinstance(inner, dict) and ("labs" in inner or "medications" in inner):
                return inner
            return value
    return {}


def _public_extracted(payload: dict) -> dict:
    labs = payload.get("labs")
    medications = payload.get("medications")
    return {
        "labs": labs if isinstance(labs, list) else [],
        "medications": medications if isinstance(medications, list) else [],
    }


def _meta(payload: dict) -> dict:
    meta = payload.get("meta")
    return dict(meta) if isinstance(meta, dict) else {}


def _pack_extracted(
    extracted: dict,
    *,
    filename: str,
    status: str,
    confirmed_by: str | None,
    extraction_error: str | None,
) -> dict:
    """Keep lab and medication fields, plus review metadata the chart table may omit."""

    return {
        "labs": list(extracted.get("labs") or []),
        "medications": list(extracted.get("medications") or []),
        "meta": {
            "filename": filename,
            "extraction_status": status,
            "confirmed_by": confirmed_by,
            "extraction_error": extraction_error,
        },
    }


def _pick(row, meta: dict, name: str):
    if name in _columns(ExtractionModel):
        value = getattr(row, name, None)
        if value is not None:
            return value
    return meta.get(name)


def _body(row) -> dict:
    payload = _raw_payload(row)
    meta = _meta(payload)
    confirmed = bool(getattr(row, "confirmed", False))
    document_id = getattr(row, "document_id", None)
    created_at = getattr(row, "created_at", None)
    confirmed_at = getattr(row, "confirmed_at", None)
    body = {
        "id": str(row.id),
        "patient_id": str(row.patient_id),
        "document_id": None if document_id is None else str(document_id),
        "document_type": getattr(row, "document_type", None),
        "filename": _pick(row, meta, "filename"),
        "extraction_status": _pick(row, meta, "extraction_status"),
        "extracted": _public_extracted(payload),
        "confirmed": confirmed,
        "confirmed_by": _pick(row, meta, "confirmed_by"),
        "confirmation_required": not confirmed,
        "message": NOT_A_CONFIRMED_PRESCRIPTION,
        "extraction_error": _pick(row, meta, "extraction_error"),
        "created_at": to_iso(created_at) if isinstance(created_at, datetime) else None,
    }
    if isinstance(confirmed_at, datetime):
        body["confirmed_at"] = to_iso(confirmed_at)
    return body


def _filename(payload: dict, details: list[str]) -> str | None:
    if "filename" not in payload or payload["filename"] is None or payload["filename"] == "":
        details.append("filename is required")
        return None
    value = payload["filename"]
    if not isinstance(value, str):
        details.append("filename must be a string")
        return None
    cleaned = value.strip()
    if not cleaned:
        details.append("filename is required")
        return None
    if len(cleaned) > 200:
        details.append("filename is too long")
        return None
    if any(ord(char) < 32 for char in cleaned) or "/" in cleaned or "\\" in cleaned:
        details.append("filename must not include a path")
        return None
    return cleaned


def _optional_text(payload: dict, field: str, details: list[str]) -> str | None:
    if field not in payload or payload[field] is None:
        return None
    value = payload[field]
    if not isinstance(value, str):
        details.append(f"{field} must be a string")
        return None
    return value


@bp.post("/patients/<patient_id>/documents/extract")
def post_extract(patient_id: str):
    payload = read_json_object()
    details: list[str] = []
    reject_unknown_fields(payload, _EXTRACT_FIELDS, details)
    document_type = require_choice(payload, "document_type", _DOCUMENT_TYPES, details)
    filename = _filename(payload, details)
    text = _optional_text(payload, "text", details)
    file_base64 = _optional_text(payload, "file_base64", details)
    if file_base64 is None:
        file_base64 = _optional_text(payload, "file", details)
    raise_if(details)
    assert document_type is not None and filename is not None
    source_text, extraction_error = resolve_document_text(text, file_base64)
    if extraction_error:
        status = "failed"
        extracted = {"labs": [], "medications": []}
    else:
        status = "extracted"
        extracted = extract_fields(source_text or "")
    patient = get_patient(get_db(), patient_id)
    body = _store_extraction(
        get_db(),
        patient_id=patient.id,
        document_type=document_type,
        filename=filename,
        status=status,
        extracted=extracted,
        extraction_error=extraction_error,
    )
    return jsonify(body), 201


@bp.post("/patients/<patient_id>/documents/<extraction_id>/confirm")
def post_confirm(patient_id: str, extraction_id: str):
    payload = read_json_object()
    details: list[str] = []
    reject_unknown_fields(payload, _CONFIRM_FIELDS, details)
    confirmed_by = require_choice(payload, "confirmed_by", _CONFIRMED_BY, details)
    raise_if(details)
    assert confirmed_by is not None
    patient = get_patient(get_db(), patient_id)
    row = _load_extraction(get_db(), patient.id, extraction_id)
    if "confirmed" in _columns(ExtractionModel):
        row.confirmed = True
    if "confirmed_at" in _columns(ExtractionModel):
        row.confirmed_at = utcnow()
    if "confirmed_by" in _columns(ExtractionModel):
        row.confirmed_by = confirmed_by
    _remember_confirmed_by(row, confirmed_by)
    session = get_db()
    try:
        session.commit()
        session.refresh(row)
    except Exception:
        session.rollback()
        raise
    # Confirm records the review only. It does not insert a medication.
    return jsonify(_body(row)), 200


def _store_extraction(
    session,
    *,
    patient_id: uuid.UUID,
    document_type: str,
    filename: str,
    status: str,
    extracted: dict,
    extraction_error: str | None,
) -> dict:
    document_id = None
    document_model = _document_model()
    if document_model is not None:
        document = document_model(
            patient_id=patient_id,
            document_type=chart_document_type(document_type),
            file_location=f"inline-text:{filename}",
            extraction_status=status,
        )
        session.add(document)
        session.flush()
        document_id = document.id
    row = _write(
        ExtractionModel,
        {
            "patient_id": patient_id,
            "document_id": document_id,
            "document_type": document_type,
            "filename": filename,
            "extraction_status": status,
            "extracted": _pack_extracted(
                extracted,
                filename=filename,
                status=status,
                confirmed_by=None,
                extraction_error=extraction_error,
            ),
            "confirmed": False,
            "confirmed_by": None,
            "message": NOT_A_CONFIRMED_PRESCRIPTION,
            "extraction_error": extraction_error,
        },
    )
    session.add(row)
    try:
        session.commit()
        session.refresh(row)
    except Exception:
        session.rollback()
        raise
    return _body(row)


def _remember_confirmed_by(row, confirmed_by: str) -> None:
    payload = _raw_payload(row)
    meta = _meta(payload)
    meta["confirmed_by"] = confirmed_by
    payload = dict(payload)
    payload["meta"] = meta
    for name in _PAYLOAD_COLUMNS:
        if name in _columns(ExtractionModel):
            setattr(row, name, payload)
            return


def _load_extraction(session, patient_id: uuid.UUID, extraction_id: str):
    try:
        parsed = uuid.UUID(extraction_id)
    except ValueError:
        raise NotFoundError("Extraction not found") from None
    row = session.get(ExtractionModel, parsed)
    if row is None or getattr(row, "patient_id", None) != patient_id:
        raise NotFoundError("Extraction not found")
    return row
