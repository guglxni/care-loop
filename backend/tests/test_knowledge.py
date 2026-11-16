"""Live patient knowledge document. These tests do not dial."""

import inspect

from app.db import SessionLocal
from app.demo.ravi import PARTICIPANT_PHONE, PATIENT_ID as RAVI_ID
from app.models import PatientKnowledgeLink
from app.services import knowledge_service
from app.services.seed_service import PATIENT_ID
from tests.helpers import assert_error

DISCLAIMER = (
    "Care coordination facts. Not medical advice. Do not diagnose or change medicines."
)

UNKNOWN = "99999999-9999-4999-8999-999999999999"
RAVI_KNOWLEDGE = f"/api/v1/patients/{RAVI_ID}/knowledge"
MEERA_KNOWLEDGE = f"/api/v1/patients/{PATIENT_ID}/knowledge"


def test_ravi_document_names_him_and_metformin_when_present(client):
    assert client.get("/api/v1/demo/ravi").status_code == 200
    profile = client.get(f"/api/v1/patients/{RAVI_ID}").get_json()
    response = client.get(RAVI_KNOWLEDGE)
    assert response.status_code == 200
    assert response.mimetype == "text/markdown"
    text = response.get_data(as_text=True)
    assert text.startswith(DISCLAIMER)
    assert "Not medical advice" in text
    for heading in (
        "## Patient",
        "## Conditions",
        "## Active medications",
        "## Recent glucose",
        "## Recent blood pressure",
        "## Next consultation",
        "## Open care events",
        "## Linked phone numbers",
    ):
        assert heading in text
    assert "measured_at" in text
    assert "source " in text
    assert "Ravi" in text
    assert profile["preferred_name"] in text
    assert str(RAVI_ID) in text
    assert PARTICIPANT_PHONE in text
    medications = client.get(f"/api/v1/patients/{RAVI_ID}/medications").get_json()["medications"]
    if any("metformin" in row["medication_name"].casefold() for row in medications):
        assert "metformin" in text.casefold()


def test_unknown_patient_knowledge_is_not_found(client):
    response = client.get(f"/api/v1/patients/{UNKNOWN}/knowledge")
    assert_error(response, 404, "not_found")
    refresh = client.post(f"/api/v1/patients/{UNKNOWN}/knowledge/refresh")
    assert_error(refresh, 404, "not_found")


def test_ingest_origin_appears_only_when_the_reading_has_one(client, app):
    from sqlalchemy import select

    from app.models import HealthReading

    with app.app_context():
        knowledge_service._map_ingest_origin()
        session = SessionLocal()
        try:
            row = session.scalars(
                select(HealthReading).where(
                    HealthReading.patient_id == PATIENT_ID,
                    HealthReading.measurement_type == "blood_glucose",
                    HealthReading.data_quality == "valid",
                )
            ).first()
            assert row is not None
            assert row.ingest_origin is None
            row.ingest_origin = "manual"
            session.commit()
        finally:
            session.close()
    text = client.get(MEERA_KNOWLEDGE).get_data(as_text=True)
    assert "ingest origin manual" in text


def test_document_follows_the_requested_chart(client):
    meera = client.get(MEERA_KNOWLEDGE)
    assert meera.status_code == 200
    text = meera.get_data(as_text=True)
    assert text.startswith(DISCLAIMER)
    assert "Meera" in text
    assert str(PATIENT_ID) in text
    assert str(RAVI_ID) not in text
    assert "Synthetic chart note" not in text


def test_refresh_records_path_and_does_not_accept_an_external_id(client, app):
    assert client.get("/api/v1/demo/ravi").status_code == 200
    response = client.post(
        f"{RAVI_KNOWLEDGE}/refresh",
        json={
            "source_url": "https://example.invalid/chart",
            "bolna_knowledgebase_id": "kb_injected",
        },
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["patient_id"] == str(RAVI_ID)
    assert body["source_url"] == RAVI_KNOWLEDGE
    assert "://" not in body["source_url"]
    assert body["bolna_knowledgebase_id"] is None
    assert body["last_built_at"].endswith("Z")

    _set_knowledgebase_id(app, "kb_existing")
    again = client.post(f"{RAVI_KNOWLEDGE}/refresh")
    stored = again.get_json()
    assert again.status_code == 200
    assert stored["source_url"] == RAVI_KNOWLEDGE
    assert stored["bolna_knowledgebase_id"] == "kb_existing"
    assert stored["last_built_at"] >= body["last_built_at"]

    source = inspect.getsource(knowledge_service)
    assert "create_knowledgebase" not in source
    assert "start_outbound_call" not in source


def _set_knowledgebase_id(app, value: str) -> None:
    with app.app_context():
        session = SessionLocal()
        try:
            row = session.get(PatientKnowledgeLink, RAVI_ID)
            assert row is not None
            row.bolna_knowledgebase_id = value
            session.commit()
        finally:
            session.close()
