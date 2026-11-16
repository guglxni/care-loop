"""Voice context, call outcomes, and the webhook inbox."""

import json
from datetime import datetime, timezone

import pytest

from app.models import HealthReading
from app.services.context_service import PURPOSES, VOICE_INSTRUCTIONS
from app.services.seed_service import (
    MEDICAL_HISTORY,
    METFORMIN_ID,
    PATIENT_ID,
    SEEDED_HEALTH_READINGS,
)
from tests.helpers import assert_error, count_rows, voice_calls

CONTEXT = f"/api/v1/patients/{PATIENT_ID}/bolna/context"
OUTCOMES = f"/api/v1/patients/{PATIENT_ID}/bolna/call-outcomes"
WEBHOOK = "/api/v1/bolna/webhook"
ALLOWED_CONTEXT_KEYS = {
    "patient_id",
    "preferred_name",
    "preferred_language",
    "purpose",
    "due_medications",
    "latest_glucose",
    "latest_blood_pressure",
    "next_consultation",
    "instructions",
}


def test_bolna_context_is_an_allow_list(client):
    response = client.get(CONTEXT, query_string={"purpose": "glucose_check"})
    assert response.status_code == 200
    body = response.get_json()
    assert set(body) <= ALLOWED_CONTEXT_KEYS
    assert body["patient_id"] == str(PATIENT_ID)
    assert body["preferred_name"] == "Meera Iyer"
    assert body["preferred_language"] == "en"
    assert body["purpose"] == "glucose_check"
    assert body["instructions"] == VOICE_INSTRUCTIONS
    assert {item["name"]: item["times"] for item in body["due_medications"]} == {
        "Metformin": ["08:00", "20:00"],
        "Telmisartan": ["08:00"],
    }
    for item in body["due_medications"]:
        assert set(item) == {"name", "times"}
    assert set(body["latest_glucose"]) == {"value", "unit", "context", "source", "measured_at"}
    assert body["latest_glucose"]["value"] == 125
    assert body["latest_glucose"]["unit"] == "mg/dL"
    assert body["latest_glucose"]["context"] == "fasting"
    assert body["latest_glucose"]["source"] == "glucometer"
    assert body["latest_glucose"]["measured_at"] == "2026-11-15T01:50:00Z"
    assert set(body["latest_blood_pressure"]) == {
        "systolic",
        "diastolic",
        "unit",
        "source",
        "measured_at",
    }
    assert body["latest_blood_pressure"]["systolic"] == 126
    assert body["latest_blood_pressure"]["diastolic"] == 80
    assert body["latest_blood_pressure"]["unit"] == "mmHg"
    assert body["latest_blood_pressure"]["source"] == "home_monitor"
    assert body["latest_blood_pressure"]["measured_at"] == "2026-11-15T02:40:00Z"
    seed_at = datetime(2026, 11, 20, 4, 0, tzinfo=timezone.utc)
    if datetime.now(timezone.utc) <= seed_at:
        assert set(body["next_consultation"]) == {
            "clinician",
            "appointment_date",
            "consultation_type",
        }
        assert body["next_consultation"]["clinician"] == "Dr. Anika Shah"
        assert body["next_consultation"]["consultation_type"] == "consultation"
        assert body["next_consultation"]["appointment_date"].startswith("2026-11-20")
    encoded = json.dumps(body)
    assert MEDICAL_HISTORY not in encoded
    assert "Synthetic chart note" not in encoded
    assert "medical_history" not in encoded
    assert "Penicillin" not in encoded
    assert "500 mg" not in encoded
    assert "40 mg" not in encoded
    assert "synthetic://chart" not in encoded
    assert "file_location" not in encoded
    assert str(METFORMIN_ID) not in encoded


@pytest.mark.parametrize("purpose", PURPOSES)
def test_bolna_context_accepts_each_purpose(client, purpose):
    response = client.get(CONTEXT, query_string={"purpose": purpose})
    assert response.status_code == 200
    assert response.get_json()["purpose"] == purpose
    assert response.get_json()["instructions"] == VOICE_INSTRUCTIONS


def test_onboarding_context_follows_the_linked_destination(client):
    assert client.get("/api/v1/demo/ravi").status_code == 200
    ravi = "a52a0000-0000-4000-8000-000000000052"
    direct = client.get(f"/api/v1/patients/{ravi}/bolna/context", query_string={"purpose": "onboarding"})
    assert direct.status_code == 200
    assert direct.get_json()["patient_id"] == ravi
    assert direct.get_json()["preferred_name"] == "Ravi Sharma"
    assert direct.get_json()["purpose"] == "onboarding"

    linked = client.get(
        CONTEXT,
        query_string={"purpose": "onboarding", "to_number": "+91 93725 01954"},
    )
    assert linked.status_code == 200
    body = linked.get_json()
    assert body["patient_id"] == ravi
    assert body["preferred_name"] == "Ravi Sharma"
    assert body["preferred_language"] == "en"
    assert body["purpose"] == "onboarding"
    assert set(body) <= ALLOWED_CONTEXT_KEYS
    encoded = json.dumps(body)
    assert MEDICAL_HISTORY not in encoded
    assert "Penicillin" not in encoded


def test_bolna_context_rejects_unknown_purpose(client):
    missing = assert_error(client.get(CONTEXT), 400, "validation_error")
    assert any("purpose must be one of" in item for item in missing["details"])
    invalid = assert_error(
        client.get(CONTEXT, query_string={"purpose": "diagnosis"}),
        400,
        "validation_error",
    )
    assert any("purpose must be one of" in item for item in invalid["details"])


def test_bolna_context_omits_empty_sections(client, app):
    from sqlalchemy import delete

    from app.db import SessionLocal

    with app.app_context():
        session = SessionLocal()
        try:
            session.execute(delete(HealthReading))
            from app.models import Consultation

            session.execute(delete(Consultation))
            session.commit()
        finally:
            session.close()
    body = client.get(CONTEXT, query_string={"purpose": "general"}).get_json()
    assert "latest_glucose" not in body
    assert "latest_blood_pressure" not in body
    assert "next_consultation" not in body
    assert body["due_medications"]
    assert MEDICAL_HISTORY not in json.dumps(body)


def test_call_outcome_upserts_on_bolna_call_id(client, app):
    payload = {
        "bolna_call_id": "exec-1",
        "call_type": "outbound",
        "language": "hi",
        "call_status": "completed",
        "summary": "Patient reported the morning reading was already written down.",
        "extracted_data": {"medication_check": "not_discussed"},
    }
    created = client.post(OUTCOMES, json=payload)
    assert created.status_code == 201
    created_body = created.get_json()
    assert created_body["bolna_call_id"] == "exec-1"
    assert created_body["patient_id"] == str(PATIENT_ID)
    updated = client.post(OUTCOMES, json={**payload, "summary": "Updated summary.", "call_status": "completed"})
    assert updated.status_code == 200
    assert updated.get_json()["id"] == created_body["id"]
    assert updated.get_json()["summary"] == "Updated summary."
    stored = voice_calls(app)
    assert len(stored) == 1
    assert stored[0]["summary"] == "Updated summary."
    assert count_rows(app, HealthReading) == SEEDED_HEALTH_READINGS


def test_call_outcome_validation(client):
    response = client.post(
        OUTCOMES,
        json={"bolna_call_id": "exec-2", "call_type": "sideways", "summary": "x"},
    )
    error = assert_error(response, 400, "validation_error")
    assert any("call_type" in item for item in error["details"])
    assert voice_calls(client.application) == []


def test_webhook_is_idempotent_and_does_not_write_the_chart(client, app):
    before_readings = count_rows(app, HealthReading)
    payload = {
        "id": "bolna-1",
        "patient_id": str(PATIENT_ID),
        "status": "completed",
        "call_type": "outbound",
        "language": "hi",
        "summary": "First delivery summary.",
        "extracted_data": {"glucose_reported": {"value": 400, "unit": "mg/dL"}},
    }
    first = client.post(WEBHOOK, json=payload)
    assert first.status_code == 200
    assert first.get_json()["duplicate"] is False
    assert first.get_json()["bolna_call_id"] == "bolna-1"
    second = client.post(
        WEBHOOK,
        json={**payload, "summary": "Second delivery must not replace the first."},
    )
    assert second.status_code == 200
    assert second.get_json() == {"duplicate": True}
    stored = voice_calls(app)
    assert len(stored) == 1
    assert stored[0]["summary"] == "First delivery summary."
    assert stored[0]["call_status"] == "completed"
    assert count_rows(app, HealthReading) == before_readings


def test_webhook_uses_context_details_when_patient_id_is_not_a_known_uuid(client, app):
    response = client.post(
        WEBHOOK,
        json={
            "id": "bolna-context",
            "patient_id": "not-a-uuid",
            "status": "completed",
            "summary": "Checked the scheduled time.",
            "telephony_data": {"call_type": "inbound"},
            "context_details": {"recipient_data": {"patient_id": str(PATIENT_ID)}},
        },
    )
    assert response.status_code == 200
    assert response.get_json()["duplicate"] is False
    stored = voice_calls(app)
    assert stored[0]["patient_id"] == str(PATIENT_ID)
    assert stored[0]["call_type"] == "inbound"
    assert stored[0]["summary"] == "Checked the scheduled time."


def test_webhook_without_a_patient_stores_nothing_clinical(client, app):
    payload = {
        "id": "orphan-call",
        "patient_id": "99999999-9999-4999-8999-999999999999",
        "status": "no-answer",
        "summary": "No chart was linked.",
    }
    first = client.post(WEBHOOK, json=payload)
    assert first.status_code == 202
    assert first.get_json()["ignored"] is True
    second = client.post(WEBHOOK, json=payload)
    assert second.status_code == 200
    assert second.get_json()["duplicate"] is True
    assert voice_calls(app) == []
    assert count_rows(app, HealthReading) == SEEDED_HEALTH_READINGS


def test_webhook_requires_the_secret_when_configured(client, app):
    app.config["BOLNA_WEBHOOK_SECRET"] = "dev-secret"
    payload = {"id": "secret-call", "patient_id": str(PATIENT_ID), "status": "completed"}
    assert_error(client.post(WEBHOOK, json=payload), 401, "unauthorized")
    assert_error(
        client.post(WEBHOOK, json=payload, headers={"X-Care-Loop-Secret": "wrong"}),
        401,
        "unauthorized",
    )
    assert voice_calls(app) == []
    accepted = client.post(
        WEBHOOK,
        json=payload,
        headers={"X-Care-Loop-Secret": "dev-secret"},
    )
    assert accepted.status_code == 200
    assert accepted.get_json()["duplicate"] is False
    assert len(voice_calls(app)) == 1


def test_production_rejects_a_webhook_when_the_secret_is_unset(client, app):
    app.config["FLASK_ENV"] = "production"
    app.config["BOLNA_WEBHOOK_SECRET"] = None
    response = client.post(WEBHOOK, json={"id": "prod-call", "patient_id": str(PATIENT_ID)})
    error = assert_error(response, 401, "unauthorized")
    assert "BOLNA_WEBHOOK_SECRET" in error["message"]
    assert voice_calls(app) == []


def test_webhook_rejects_a_non_object_body(client):
    assert_error(client.post(WEBHOOK, json=["not", "an", "object"]), 400, "validation_error")
