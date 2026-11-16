"""Outbound reminder. The Bolna call function is mocked, so pytest does not dial."""

import pytest

from app.demo.ravi import PATIENT_ID as RAVI_ID
from app.services.bolna_outbound import AGENT_ID, FROM_NUMBER
from app.services.seed_service import PATIENT_ID
from tests.helpers import assert_error, voice_calls

REMIND = f"/api/v1/patients/{PATIENT_ID}/bolna/remind"
USER_NUMBER = "+15555550123"
SYNTHETIC_NUMBER = "+919840011223"


@pytest.fixture
def bolna_calls(monkeypatch):
    captured: list[dict] = []

    def fake_start_outbound_call(**kwargs):
        captured.append(kwargs)
        return "exec-remind-1"

    def block_network(*_args, **_kwargs):
        raise AssertionError("Bolna was contacted")

    monkeypatch.setattr("urllib.request.urlopen", block_network)
    monkeypatch.setattr(
        "app.services.outbound_call.start_outbound_call",
        fake_start_outbound_call,
    )
    return captured


def test_remind_rejects_synthetic_number(client, bolna_calls, monkeypatch):
    monkeypatch.setenv("USER_PHONE_NUMBER", SYNTHETIC_NUMBER)
    explicit = client.post(REMIND, json={"to": SYNTHETIC_NUMBER, "purpose": "medication_check"})
    explicit_error = assert_error(explicit, 400, "validation_error")
    assert any("+919840011223" in item for item in explicit_error["details"])

    spaced = client.post(REMIND, json={"to": "+91 98400 11223"})
    spaced_error = assert_error(spaced, 400, "validation_error")
    assert any("+919840011223" in item for item in spaced_error["details"])

    implicit = client.post(REMIND, json={})
    assert_error(implicit, 400, "validation_error")
    assert bolna_calls == []
    assert voice_calls(client.application) == []


def test_remind_rejects_the_careloop_line(client, bolna_calls):
    response = client.post(REMIND, json={"to": FROM_NUMBER})
    assert_error(response, 400, "validation_error")
    assert bolna_calls == []


def test_remind_queues_default_medication_check(client, bolna_calls, monkeypatch):
    client.get("/api/v1/demo/ravi")
    monkeypatch.setenv("USER_PHONE_NUMBER", USER_NUMBER)
    response = client.post(f"/api/v1/patients/{RAVI_ID}/bolna/remind", json={})
    assert response.status_code == 201
    body = response.get_json()
    assert body["execution_id"] == "exec-remind-1"
    assert body["purpose"] == "medication_adherence"
    assert body["call_type"] == "medication_adherence"
    assert body["preferred_language"] == "en"
    assert body["call_status"] == "queued"
    assert body["patient_id"] == str(RAVI_ID)
    user_data = bolna_calls[0]["user_data"]
    assert bolna_calls[0]["agent_id"] == AGENT_ID
    assert bolna_calls[0]["recipient_phone_number"] == USER_NUMBER
    assert bolna_calls[0]["from_phone_number"] == FROM_NUMBER
    assert user_data["patient_id"] == str(RAVI_ID)
    assert user_data["patient_name"] == "Ravi Sharma"
    assert user_data["call_type"] == "medication_adherence"
    assert "Metformin" in user_data["relevant_context"]
    assert "unconfirmed" in user_data["relevant_context"]
    stored = voice_calls(client.application)
    assert len(stored) == 1
    assert stored[0]["bolna_call_id"] == "exec-remind-1"
    assert stored[0]["patient_id"] == str(RAVI_ID)
    assert stored[0]["call_type"] == "outbound"
    assert stored[0]["language"] == "en"
    assert stored[0]["call_status"] == "queued"
    assert stored[0]["extracted_data"]["call_type"] == "medication_adherence"


def test_remind_uses_explicit_purpose(client, bolna_calls):
    client.get("/api/v1/demo/ravi")
    response = client.post(
        f"/api/v1/patients/{RAVI_ID}/bolna/remind",
        json={"to": USER_NUMBER, "purpose": "glucose_check"},
    )
    assert response.status_code == 201
    assert response.get_json()["call_type"] == "weekly_checkin"
    assert "2026-11-11" in bolna_calls[0]["user_data"]["relevant_context"]
    assert bolna_calls[0]["recipient_phone_number"] == USER_NUMBER


def test_remind_keeps_the_selected_patient_when_the_phone_is_linked(client, bolna_calls):
    client.get("/api/v1/demo/ravi")
    response = client.post(
        f"/api/v1/patients/{RAVI_ID}/bolna/remind",
        json={"to": "+91 93725 01954", "purpose": "medication_check"},
    )
    assert response.status_code == 201
    assert bolna_calls[0]["recipient_phone_number"] == "+919372501954"
    assert bolna_calls[0]["from_phone_number"] == FROM_NUMBER
    assert bolna_calls[0]["user_data"]["patient_id"] == str(RAVI_ID)
    assert bolna_calls[0]["user_data"]["patient_name"] == "Ravi Sharma"
    stored = voice_calls(client.application)
    assert len(stored) == 1
    assert stored[0]["patient_id"] == str(RAVI_ID)
    assert stored[0]["call_status"] == "queued"


def test_remind_user_data_follows_the_linked_mobile(client, bolna_calls):
    assert client.get("/api/v1/demo/ravi").status_code == 200
    response = client.post(
        REMIND,
        json={"to": "+919372501954", "purpose": "medication_check"},
    )
    assert response.status_code == 201
    assert response.get_json()["patient_id"] == str(RAVI_ID)
    assert bolna_calls[0]["user_data"]["patient_id"] == str(RAVI_ID)
    assert bolna_calls[0]["user_data"]["patient_name"] == "Ravi Sharma"
    assert bolna_calls[0]["user_data"]["doctor_name"] == "Dr. Mehta"
    assert bolna_calls[0]["recipient_phone_number"] == "+919372501954"
    stored = voice_calls(client.application)
    assert stored[0]["patient_id"] == str(RAVI_ID)


def test_remind_requires_a_destination(client, bolna_calls, monkeypatch):
    monkeypatch.delenv("USER_PHONE_NUMBER", raising=False)
    response = client.post(REMIND, json={})
    error = assert_error(response, 400, "validation_error")
    assert any("USER_PHONE_NUMBER" in item for item in error["details"])
    assert bolna_calls == []
