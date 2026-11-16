"""Knowledge page for one chart. These tests do not dial or call Bolna."""

import inspect

import app.knowledge as knowledge
from app.demo.ravi import PARTICIPANT_PHONE, PATIENT_ID as RAVI_ID
from app.models import PatientKnowledgeLink
from app.services.knowledge_service import DISCLAIMER
from app.services.seed_service import PATIENT_ID
from tests.helpers import assert_error

UNKNOWN = "99999999-9999-4999-8999-999999999999"
RAVI_KNOWLEDGE = f"/api/v1/patients/{RAVI_ID}/knowledge"
MEERA_KNOWLEDGE = f"/api/v1/patients/{PATIENT_ID}/knowledge"


def test_route_is_registered_on_the_knowledge_blueprint(app):
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/v1/patients/<patient_id>/knowledge" in rules
    assert "/api/v1/patients/<patient_id>/knowledge/refresh" in rules
    assert any(rule.endpoint == "knowledge.get_knowledge" for rule in app.url_map.iter_rules())
    assert knowledge.bp.name == "knowledge"
    source = inspect.getsource(knowledge)
    assert "create_knowledgebase" not in source
    assert "start_outbound_call" not in source
    service = inspect.getsource(__import__("app.services.knowledge_service", fromlist=["build_document"]))
    assert "create_knowledgebase" not in service
    assert "start_outbound_call" not in service


def test_ravi_document_lists_his_chart(client):
    assert client.get("/api/v1/demo/ravi").status_code == 200
    response = client.get(RAVI_KNOWLEDGE)
    assert response.status_code == 200
    assert response.mimetype == "text/markdown"
    text = response.get_data(as_text=True)
    assert text.splitlines()[0] == DISCLAIMER
    assert "Ravi Sharma" in text
    assert str(RAVI_ID) in text
    assert "Preferred language: en" in text
    assert "type_2_diabetes" in text
    assert "hypertension" in text
    assert "Metformin, dose 500 mg, times 20:00" in text
    assert "mg/dL" in text
    assert "source glucometer" in text
    assert "mmHg" in text
    assert "source clinic" in text or "source home_monitor" in text
    assert "Dr. Mehta" in text
    assert "medication_followup" in text
    assert PARTICIPANT_PHONE in text
    assert "Meera" not in text
    assert str(PATIENT_ID) not in text


def test_unknown_patient_is_not_found(client):
    response = client.get(f"/api/v1/patients/{UNKNOWN}/knowledge")
    assert_error(response, 404, "not_found")
    refresh = client.post(f"/api/v1/patients/{UNKNOWN}/knowledge/refresh")
    assert_error(refresh, 404, "not_found")


def test_meera_document_is_only_her_chart(client):
    response = client.get(MEERA_KNOWLEDGE)
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert text.splitlines()[0] == (
        "Care coordination facts. Not medical advice. Do not diagnose or change medicines."
    )
    assert "Meera Iyer" in text
    assert str(PATIENT_ID) in text
    assert "Metformin, dose" in text
    assert "mg/dL" in text
    assert "mmHg" in text
    assert str(RAVI_ID) not in text


def test_refresh_records_last_built_at(client, app):
    assert client.get("/api/v1/demo/ravi").status_code == 200
    response = client.post(f"{RAVI_KNOWLEDGE}/refresh")
    assert response.status_code == 200
    body = response.get_json()
    assert body["patient_id"] == str(RAVI_ID)
    assert body["source_url"] == RAVI_KNOWLEDGE
    assert body["bolna_knowledgebase_id"] is None
    assert isinstance(body["last_built_at"], str) and body["last_built_at"].endswith("Z")

    from app.db import SessionLocal

    with app.app_context():
        session = SessionLocal()
        try:
            row = session.get(PatientKnowledgeLink, RAVI_ID)
            assert row is not None
            assert row.last_built_at is not None
            assert row.source_url == RAVI_KNOWLEDGE
        finally:
            session.close()
