"""Document extract and confirm. Extracted text never becomes a medication."""

import base64
import uuid
from pathlib import Path

import pytest

import app.ingest.document_routes  # noqa: F401  (registers DocumentExtraction before create_all)
from app.models import Document, Medication
from app.services.seed_service import PATIENT_ID
from tests.helpers import assert_error

FIXTURES = Path(__file__).resolve().parents[1] / "app" / "ingest" / "fixtures"
EXTRACT = f"/api/v1/patients/{PATIENT_ID}/documents/extract"
DISCLAIMER = "Extracted medication text is not a confirmed prescription."


@pytest.fixture
def client(app):
    from app.ingest.document_routes import bp

    if bp.name not in app.blueprints:
        app.register_blueprint(bp)
    return app.test_client()


def _medication_ids(app) -> set[str]:
    from sqlalchemy import select

    from app.db import SessionLocal

    with app.app_context():
        session = SessionLocal()
        try:
            return {str(value) for value in session.scalars(select(Medication.id)).all()}
        finally:
            session.close()


def _documents(app, file_location: str) -> list:
    from sqlalchemy import select

    from app.db import SessionLocal

    with app.app_context():
        session = SessionLocal()
        try:
            return list(
                session.scalars(select(Document).where(Document.file_location == file_location)).all()
            )
        finally:
            session.close()


def _extract(client, document_type: str, filename: str, text: str):
    return client.post(
        EXTRACT,
        json={"document_type": document_type, "filename": filename, "text": text},
    )


def test_unconfirmed_lab_extraction_does_not_create_medication(client, app):
    before = _medication_ids(app)
    text = (FIXTURES / "lab_report.txt").read_text(encoding="utf-8")
    assert "SYNTHETIC" in text
    response = _extract(client, "lab_report", "lab_report.txt", text)
    assert response.status_code == 201
    body = response.get_json()
    assert body["confirmed"] is False
    assert body["confirmation_required"] is True
    assert body["message"] == DISCLAIMER
    assert body["extraction_status"] == "extracted"
    assert body["extracted"]["medications"] == []
    hba1c = body["extracted"]["labs"][0]
    assert hba1c == {
        "test_name": "HbA1c",
        "value": 7.2,
        "unit": "%",
        "report_date": "2026-10-01",
    }
    assert body["extracted"]["labs"][1]["test_name"] == "Fasting glucose"
    assert _medication_ids(app) == before
    stored = _documents(app, "inline-text:lab_report.txt")
    assert len(stored) == 1
    assert stored[0].document_type == "lab_report"
    assert stored[0].extraction_status == "extracted"


def test_confirm_does_not_create_medication(client, app):
    before = _medication_ids(app)
    text = (FIXTURES / "prescription.txt").read_text(encoding="utf-8")
    extracted = _extract(client, "prescription", "prescription.txt", text)
    assert extracted.status_code == 201
    body = extracted.get_json()
    assert body["confirmed"] is False
    assert body["confirmation_required"] is True
    assert body["message"] == DISCLAIMER
    assert body["extracted"]["medications"] == [
        {
            "medication_name": "Metformin",
            "dosage": "500 mg",
            "frequency": "twice daily",
        },
        {
            "medication_name": "Telmisartan",
            "dosage": "40 mg",
            "frequency": "once daily",
        },
    ]
    assert _medication_ids(app) == before
    response = client.post(
        f"/api/v1/patients/{PATIENT_ID}/documents/{body['id']}/confirm",
        json={"confirmed_by": "clinician"},
    )
    assert response.status_code == 200
    confirmed = response.get_json()
    assert confirmed["confirmed"] is True
    assert confirmed["confirmed_by"] == "clinician"
    assert confirmed["confirmation_required"] is False
    assert confirmed["message"] == DISCLAIMER
    assert confirmed["id"] == body["id"]
    assert _medication_ids(app) == before


@pytest.mark.parametrize(
    "payload",
    [{}, {"confirmed_by": ""}, {"confirmed_by": "pharmacist"}],
)
def test_confirm_requires_confirmed_by(client, app, payload):
    before = _medication_ids(app)
    extracted = _extract(
        client,
        "prescription",
        "prescription-unconfirmed.txt",
        "Medication: Metformin 500 mg twice daily\n",
    )
    assert extracted.status_code == 201
    extraction_id = extracted.get_json()["id"]
    response = client.post(
        f"/api/v1/patients/{PATIENT_ID}/documents/{extraction_id}/confirm",
        json=payload,
    )
    error = assert_error(response, 400, "validation_error")
    assert any("confirmed_by" in item for item in error["details"])
    assert _medication_ids(app) == before


def test_hba1c_document_row_uses_lab_report(client, app):
    text = (FIXTURES / "lab_report.txt").read_text(encoding="utf-8")
    response = _extract(client, "hba1c", "hba1c.txt", text)
    assert response.status_code == 201
    body = response.get_json()
    assert body["document_type"] == "hba1c"
    assert body["extracted"]["labs"][0]["test_name"] == "HbA1c"
    stored = _documents(app, "inline-text:hba1c.txt")
    assert len(stored) == 1
    assert stored[0].document_type == "lab_report"
    assert stored[0].extraction_status == "extracted"


def test_unreadable_pdf_fails_and_does_not_create_medication(client, app):
    before = _medication_ids(app)
    encoded = base64.b64encode(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\ntrailer\n<<>>\n%%EOF").decode("ascii")
    response = client.post(
        EXTRACT,
        json={
            "document_type": "lab_report",
            "filename": "unread.pdf",
            "file_base64": encoded,
        },
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["confirmed"] is False
    assert body["confirmation_required"] is True
    assert body["message"] == DISCLAIMER
    assert body["extraction_status"] == "failed"
    assert body["extracted"] == {"labs": [], "medications": []}
    assert isinstance(body["extraction_error"], str) and "text" in body["extraction_error"].lower()
    assert _medication_ids(app) == before
    stored = _documents(app, "inline-text:unread.pdf")
    assert len(stored) == 1
    assert stored[0].extraction_status == "failed"


def test_utf8_file_base64_extracts_medication_text(client, app):
    before = _medication_ids(app)
    encoded = base64.b64encode(b"Medication: Metformin 500 mg twice daily\n").decode("ascii")
    response = client.post(
        EXTRACT,
        json={
            "document_type": "prescription",
            "filename": "note.txt",
            "file_base64": encoded,
        },
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["extraction_status"] == "extracted"
    assert body["extracted"]["medications"][0]["medication_name"] == "Metformin"
    assert body["confirmed"] is False
    assert _medication_ids(app) == before


def test_confirm_unknown_extraction_is_404(client):
    missing = uuid.uuid4()
    response = client.post(
        f"/api/v1/patients/{PATIENT_ID}/documents/{missing}/confirm",
        json={"confirmed_by": "patient"},
    )
    assert_error(response, 404, "not_found")
