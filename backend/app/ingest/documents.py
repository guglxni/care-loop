"""Text extraction for synthetic prescriptions and lab reports.

A reliable PDF parser may not be installed. Callers pass the report text.
``file_base64`` is accepted when it decodes as UTF-8 text. A PDF is read only
when ``pypdf`` or ``pdfminer`` can be imported. Otherwise binary input is
reported as ``extraction_status`` ``failed`` and the caller must send text.

Patterns are explicit. Nothing here calls a medical model, and nothing here
inserts a medication.
"""

import base64
import math
import re
from datetime import date
from io import BytesIO

from app.errors import ValidationError

NOT_A_CONFIRMED_PRESCRIPTION = (
    "Extracted medication text is not a confirmed prescription."
)
MAX_TEXT_CHARS = 200_000
MAX_FILE_BYTES = 5_000_000

_LAB_LINE = re.compile(
    r"(?P<test_name>[A-Za-z][A-Za-z0-9 /()+-]{0,80}?)\s*:\s*"
    r"(?P<value>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>%|mmol/mol|mg/dL|mmol/L|g/dL)\s+"
    r"on\s+(?P<report_date>\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)
_MED_LINE = re.compile(
    r"^[ \t]*Medication:\s*"
    r"(?P<medication_name>[A-Za-z][A-Za-z0-9.'+/-]*(?:\s+[A-Za-z][A-Za-z0-9.'+/-]*)*?)"
    r"\s+"
    r"(?P<dosage>\d+(?:\.\d+)?\s*(?:mg|mcg|µg|ug|g|ml|units|iu))"
    r"\s+"
    r"(?P<frequency>.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_UNIT_CANON = {
    "%": "%",
    "mg/dl": "mg/dL",
    "mmol/l": "mmol/L",
    "mmol/mol": "mmol/mol",
    "g/dl": "g/dL",
}
_DOSE_UNIT = {
    "mg": "mg",
    "mcg": "mcg",
    "ug": "mcg",
    "µg": "mcg",
    "g": "g",
    "ml": "mL",
    "units": "units",
    "iu": "IU",
}
_CHART_DOCUMENT_TYPE = {
    "prescription": "prescription",
    "lab_report": "lab_report",
    "hba1c": "lab_report",
}


def chart_document_type(document_type: str) -> str:
    """Map an upload type onto the chart ``documents`` check constraint."""

    return _CHART_DOCUMENT_TYPE[document_type]


def resolve_document_text(
    text: str | None,
    file_base64: str | None,
) -> tuple[str | None, str | None]:
    """Return ``(text, extraction_error)``.

    A non-empty ``text`` value wins. Unreadable binary sets ``extraction_error``
    and returns no text. Invalid base64 raises ``ValidationError``.
    """

    if text is not None:
        if len(text) > MAX_TEXT_CHARS:
            raise ValidationError("Request validation failed", ["text is too long"])
        stripped = text.strip()
        if stripped:
            return stripped, None
    if file_base64 is None:
        raise ValidationError(
            "Request validation failed",
            ["text is required"],
        )
    raw = _decode_base64(file_base64)
    if raw.startswith(b"%PDF"):
        extracted, error = _pdf_text(raw)
        if error:
            return None, error
        if extracted is None:
            return None, (
                "Cannot read this PDF. pypdf and pdfminer are not installed. "
                "Send the report as text."
            )
        if not extracted.strip():
            return None, "The PDF contained no extractable text. Send the report as text."
        if len(extracted) > MAX_TEXT_CHARS:
            raise ValidationError("Request validation failed", ["text is too long"])
        return extracted.strip(), None
    if b"\x00" in raw[:1024]:
        return None, "Cannot read this binary file. Send the report as text."
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None, "Cannot read this file as text. Send the report as text."
    if len(decoded) > MAX_TEXT_CHARS:
        raise ValidationError("Request validation failed", ["text is too long"])
    stripped = decoded.strip()
    if not stripped:
        raise ValidationError("Request validation failed", ["text is required"])
    return stripped, None


def extract_fields(text: str) -> dict:
    """Pull lab rows and medication lines out of synthetic report text."""

    labs: list[dict] = []
    seen_labs: set[tuple] = set()
    for match in _LAB_LINE.finditer(text):
        try:
            date.fromisoformat(match.group("report_date"))
        except ValueError:
            continue
        value = float(match.group("value"))
        if not math.isfinite(value):
            continue
        unit = _UNIT_CANON.get(match.group("unit").lower())
        if unit is None:
            continue
        test_name = " ".join(match.group("test_name").split())
        if not test_name:
            continue
        row = {
            "test_name": test_name,
            "value": _json_number(value),
            "unit": unit,
            "report_date": match.group("report_date"),
        }
        key = (test_name.lower(), row["value"], unit, row["report_date"])
        if key in seen_labs:
            continue
        seen_labs.add(key)
        labs.append(row)

    medications: list[dict] = []
    seen_meds: set[tuple] = set()
    for match in _MED_LINE.finditer(text):
        name = " ".join(match.group("medication_name").split())
        dosage = _dosage(match.group("dosage"))
        frequency = " ".join(match.group("frequency").split())
        if not name or dosage is None or not frequency or len(frequency) > 120:
            continue
        row = {
            "medication_name": name,
            "dosage": dosage,
            "frequency": frequency,
        }
        key = (name.lower(), dosage.lower(), frequency.lower())
        if key in seen_meds:
            continue
        seen_meds.add(key)
        medications.append(row)
    return {"labs": labs, "medications": medications}


def _json_number(value: float) -> int | float:
    if value.is_integer():
        return int(value)
    return value


def _dosage(raw: str) -> str | None:
    match = re.fullmatch(
        r"(\d+(?:\.\d+)?)\s*([A-Za-zµ]+)",
        " ".join(raw.split()),
        re.IGNORECASE,
    )
    if match is None:
        return None
    number, unit = match.group(1), match.group(2)
    canon = _DOSE_UNIT.get(unit.lower())
    if canon is None:
        return None
    if number.endswith(".0"):
        number = number[:-2]
    return f"{number} {canon}"


def _decode_base64(value: str) -> bytes:
    stripped = value.strip()
    if stripped.lower().startswith("data:"):
        _, separator, data = stripped.partition(",")
        if not separator or not data.strip():
            raise ValidationError(
                "Request validation failed",
                ["file_base64 is not valid base64"],
            )
        stripped = data.strip()
    compact = "".join(stripped.split())
    if not re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", compact):
        raise ValidationError(
            "Request validation failed",
            ["file_base64 is not valid base64"],
        )
    padded = compact + ("=" * (-len(compact) % 4))
    try:
        raw = base64.b64decode(padded, validate=True)
    except Exception as exc:
        raise ValidationError(
            "Request validation failed",
            ["file_base64 is not valid base64"],
        ) from exc
    if len(raw) > MAX_FILE_BYTES:
        raise ValidationError("Request validation failed", ["file_base64 is too large"])
    return raw


def _pdf_text(raw: bytes) -> tuple[str | None, str | None]:
    """Return ``(text, error)``. ``(None, None)`` means no parser is installed."""

    extractor = _pdf_extractor()
    if extractor is None:
        return None, None
    try:
        return extractor(raw) or "", None
    except Exception:
        return None, "The PDF could not be read. Send the report as text."


def _pdf_extractor():
    try:
        from pypdf import PdfReader
    except ImportError:
        PdfReader = None
    if PdfReader is not None:
        def _pypdf(raw: bytes) -> str:
            reader = PdfReader(BytesIO(raw))
            return "\n".join(page.extract_text() or "" for page in reader.pages)

        return _pypdf
    try:
        from pdfminer.high_level import extract_text
    except ImportError:
        return None

    def _pdfminer(raw: bytes) -> str:
        return extract_text(BytesIO(raw)) or ""

    return _pdfminer
