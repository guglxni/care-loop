"""Outbound context is required before Bolna is called. These tests do not dial."""

import logging
from datetime import timedelta

import pytest

from app.demo.ravi import EVENING_DOSE_AT, METFORMIN_ID, PATIENT_ID as RAVI_ID
from app.services.bolna_outbound import AGENT_ID, FROM_NUMBER
from app.services.seed_service import PATIENT_ID as MEERA_ID
from tests.helpers import assert_error, voice_calls

DEMO_CALLS = "/api/v1/demo/calls"
MISSING_PATIENT = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
USER_NUMBER = "+15555550123"
MEERA_MOBILE = "+919372501954"
CONTEXT_FIELDS = {
    "patient_id",
    "patient_name",
    "call_type",
    "call_reason",
    "call_objective",
    "preferred_language",
    "language_policy",
    "supported_languages",
    "clinic_name",
    "doctor_name",
    "relevant_context",
}


@pytest.fixture
def bolna_calls(monkeypatch):
    captured: list[dict] = []

    def fake_start_outbound_call(**kwargs):
        captured.append(kwargs)
        return "exec-context-1"

    def block_network(*_args, **_kwargs):
        raise AssertionError("Bolna was contacted")

    monkeypatch.setattr("urllib.request.urlopen", block_network)
    monkeypatch.setattr("app.services.outbound_call.start_outbound_call", fake_start_outbound_call)
    monkeypatch.setattr("app.services.bolna_outbound.start_outbound_call", fake_start_outbound_call)
    return captured


def test_missing_patient_does_not_dial(client, bolna_calls, caplog):
    caplog.set_level(logging.INFO)
    response = client.post(
        DEMO_CALLS,
        json={"patient_id": MISSING_PATIENT, "scenario": "onboarding", "to": USER_NUMBER},
    )
    error = assert_error(response, 409, "conflict")
    assert "not found" in error["message"].lower()
    assert bolna_calls == []
    assert voice_calls(client.application) == []
    assert f"patient_id={MISSING_PATIENT}" in caplog.text
    assert "call_type=onboarding" in caplog.text
    assert "outcome=failure" in caplog.text
    assert USER_NUMBER not in caplog.text
    assert "Synthetic chart" not in caplog.text


def test_medication_context_includes_the_unconfirmed_dose(client, bolna_calls, caplog):
    caplog.set_level(logging.INFO)
    response = client.post(
        DEMO_CALLS,
        json={"patient_id": str(RAVI_ID), "scenario": "medication", "to": USER_NUMBER},
    )
    assert response.status_code == 201
    assert len(bolna_calls) == 1
    call = bolna_calls[0]
    assert call["agent_id"] == AGENT_ID
    assert call["recipient_phone_number"] == USER_NUMBER
    assert call["from_phone_number"] == FROM_NUMBER
    user_data = call["user_data"]
    assert set(user_data) == CONTEXT_FIELDS
    assert all(isinstance(value, str) for value in user_data.values())
    assert user_data["patient_id"] == str(RAVI_ID)
    assert user_data["patient_name"] == "Ravi Sharma"
    assert user_data["call_type"] == "medication_adherence"
    assert user_data["preferred_language"] == "en"
    assert_language_follows_the_speaker(user_data)
    assert user_data["clinic_name"] == "CityCare Clinic"
    assert user_data["doctor_name"] == "Dr. Mehta"
    assert "Metformin 500 mg scheduled at 20:00" in user_data["relevant_context"]
    assert "event_status unconfirmed" in user_data["relevant_context"]
    assert "Metformin" in user_data["call_reason"]
    assert "20:00" in user_data["call_objective"]
    blob = "\n".join(user_data.values())
    assert "missed" not in blob.lower()
    assert "Synthetic chart" not in blob
    assert "what can I help you with" not in blob.lower()
    stored = voice_calls(client.application)
    assert stored[0]["patient_id"] == str(RAVI_ID)
    assert stored[0]["extracted_data"]["call_type"] == "medication_adherence"
    assert "Synthetic chart" not in (stored[0]["summary"] or "")
    assert f"patient_id={RAVI_ID}" in caplog.text
    assert "call_type=medication_adherence" in caplog.text
    assert "outcome=success" in caplog.text
    assert USER_NUMBER not in caplog.text
    assert "Metformin" not in caplog.text


def test_onboarding_context_includes_the_clinic_name(client, bolna_calls):
    response = client.post(
        DEMO_CALLS,
        json={
            "patient_name": "Ravi Sharma",
            "scenario": "onboarding",
            "to": "+91 93725 01954",
        },
    )
    assert response.status_code == 201
    call = bolna_calls[0]
    assert call["recipient_phone_number"] == MEERA_MOBILE
    user_data = call["user_data"]
    assert user_data["patient_id"] == str(RAVI_ID)
    assert user_data["patient_name"] == "Ravi Sharma"
    assert user_data["call_type"] == "onboarding"
    assert user_data["clinic_name"] == "CityCare Clinic"
    assert user_data["doctor_name"] == "Dr. Mehta"
    assert "CityCare Clinic" in user_data["relevant_context"]
    assert "Consent is not yet recorded." in user_data["relevant_context"]
    assert "type 2 diabetes and hypertension" in user_data["relevant_context"]
    assert_language_follows_the_speaker(user_data)
    objective = user_data["call_objective"].lower()
    assert "preferred language" in objective
    assert "record" in objective
    assert "only english" not in objective
    assert MEERA_MOBILE not in "\n".join(user_data.values())
    assert voice_calls(client.application)[0]["patient_id"] == str(RAVI_ID)


def test_weekly_checkin_includes_counts_and_missing_readings(client, bolna_calls):
    response = client.post(
        DEMO_CALLS,
        json={"scenario": "weekly", "to": USER_NUMBER},
    )
    assert response.status_code == 201
    user_data = bolna_calls[0]["user_data"]
    relevant = user_data["relevant_context"]
    assert_language_follows_the_speaker(user_data)
    assert user_data["patient_id"] == str(RAVI_ID)
    assert bolna_calls[0]["user_data"]["call_type"] == "weekly_checkin"
    assert "Recent glucose readings: 5." in relevant
    assert "Recent blood pressure readings: 3." in relevant
    assert "Missing scheduled glucose readings: 2026-11-11, 2026-11-14." in relevant


def test_inferred_miss_stays_unconfirmed(client, bolna_calls):
    client.get("/api/v1/demo/ravi")
    _mark_inferred_missed(client.application)
    response = client.post(
        DEMO_CALLS,
        json={"patient_id": str(RAVI_ID), "scenario": "medication", "to": USER_NUMBER},
    )
    assert response.status_code == 201
    relevant = bolna_calls[0]["user_data"]["relevant_context"]
    assert "Metformin 500 mg scheduled at 20:00" in relevant
    assert "event_status unconfirmed" in relevant
    assert "missed" not in relevant.lower()


def test_unknown_reason_does_not_dial(client, bolna_calls):
    response = client.post(
        DEMO_CALLS,
        json={"patient_id": str(RAVI_ID), "scenario": "general", "to": USER_NUMBER},
    )
    error = assert_error(response, 409, "conflict")
    assert "known reason" in error["message"].lower()
    assert bolna_calls == []


def test_patient_without_a_clinic_does_not_dial(client, bolna_calls):
    response = client.post(
        DEMO_CALLS,
        json={"patient_id": str(MEERA_ID), "scenario": "onboarding", "to": USER_NUMBER},
    )
    error = assert_error(response, 409, "conflict")
    assert "clinic" in error["message"].lower()
    assert bolna_calls == []
    assert voice_calls(client.application) == []


def assert_language_follows_the_speaker(user_data: dict) -> None:
    assert user_data["language_policy"] == (
        "Follow the language the person is speaking. Start in the chart language. "
        "Switch if they switch. English, Hindi, and Kannada are supported."
    )
    assert user_data["supported_languages"] == "English, Hindi, Kannada"
    for field in ("call_reason", "call_objective", "relevant_context"):
        assert "only English" not in user_data[field]


def _mark_inferred_missed(app) -> None:
    from app.db import SessionLocal
    from app.models import AdherenceLog

    with app.app_context():
        session = SessionLocal()
        try:
            session.add(
                AdherenceLog(
                    patient_id=RAVI_ID,
                    medication_id=METFORMIN_ID,
                    schedule_time=EVENING_DOSE_AT,
                    reported_status="missed",
                    reported_reason=None,
                    recorded_at=EVENING_DOSE_AT + timedelta(hours=1),
                    source="inferred",
                )
            )
            session.commit()
        finally:
            session.close()
