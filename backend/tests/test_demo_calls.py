"""Demo call routing. start_outbound_call is patched, so pytest does not dial."""

from app.services.bolna_outbound import FROM_NUMBER
from tests.helpers import assert_error, voice_calls

DEMO_CALLS = "/api/v1/demo/calls"
RAVI_ID = "a52a0000-0000-4000-8000-000000000052"
MEERA_MOBILE = "+919372501954"


def _block_network(*_args, **_kwargs):
    raise AssertionError("Bolna was contacted")


def test_demo_call_to_linked_mobile_keeps_the_named_patient(client, monkeypatch):
    captured: list[dict] = []

    def fake_start_outbound_call(**kwargs):
        captured.append(kwargs)
        return "exec-demo-ravi"

    monkeypatch.setattr("urllib.request.urlopen", _block_network)
    monkeypatch.setattr("app.services.outbound_call.start_outbound_call", fake_start_outbound_call)
    response = client.post(
        DEMO_CALLS,
        json={
            "patient_name": "Ravi Sharma",
            "scenario": "onboarding",
            "to": "+91 93725 01954",
        },
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["execution_id"] == "exec-demo-ravi"
    assert body["patient_id"] == RAVI_ID
    assert body["patient_name"] == "Ravi Sharma"
    assert body["call_type"] == "onboarding"
    assert body["call_status"] == "queued"
    assert captured[0]["recipient_phone_number"] == MEERA_MOBILE
    assert captured[0]["from_phone_number"] == FROM_NUMBER
    assert captured[0]["user_data"]["patient_id"] == RAVI_ID
    assert captured[0]["user_data"]["patient_name"] == "Ravi Sharma"
    assert captured[0]["user_data"]["clinic_name"] == "CityCare Clinic"
    stored = voice_calls(client.application)
    assert len(stored) == 1
    assert stored[0]["patient_id"] == RAVI_ID
    assert stored[0]["bolna_call_id"] == "exec-demo-ravi"

    status = client.get(f"{DEMO_CALLS}/exec-demo-ravi")
    assert status.status_code == 200
    assert status.get_json()["call_status"] == "queued"
    assert status.get_json()["patient_id"] == RAVI_ID


def test_demo_call_without_a_phone_link_uses_ravi(client, monkeypatch):
    captured: list[dict] = []

    def fake_start_outbound_call(**kwargs):
        captured.append(kwargs)
        return "exec-demo-ravi"

    monkeypatch.setattr("urllib.request.urlopen", _block_network)
    monkeypatch.setattr("app.services.outbound_call.start_outbound_call", fake_start_outbound_call)
    response = client.post(
        DEMO_CALLS,
        json={"scenario": "weekly", "to": "+15555550123"},
    )
    assert response.status_code == 201
    assert response.get_json()["patient_id"] == RAVI_ID
    assert captured[0]["user_data"]["patient_id"] == RAVI_ID
    assert captured[0]["user_data"]["call_type"] == "weekly_checkin"
    assert "2026-11-11" in captured[0]["user_data"]["relevant_context"]
    assert voice_calls(client.application)[0]["patient_id"] == RAVI_ID


def test_demo_call_rejects_chart_numbers_without_dialing(client, monkeypatch):
    def fail_if_called(**kwargs):
        raise AssertionError(kwargs)

    monkeypatch.setattr("urllib.request.urlopen", _block_network)
    monkeypatch.setattr("app.services.outbound_call.start_outbound_call", fail_if_called)
    synthetic = client.post(DEMO_CALLS, json={"scenario": "onboarding", "to": "+919840011223"})
    stored = client.post(DEMO_CALLS, json={"scenario": "onboarding", "to": "+15555501052"})
    line = client.post(DEMO_CALLS, json={"scenario": "onboarding", "to": FROM_NUMBER})
    assert_error(synthetic, 400, "validation_error")
    assert_error(stored, 400, "validation_error")
    assert_error(line, 400, "validation_error")
    assert voice_calls(client.application) == []
