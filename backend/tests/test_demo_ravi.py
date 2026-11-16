"""Synthetic Ravi Sharma demo chart. These tests do not dial."""

import socket
from datetime import timedelta

from sqlalchemy import delete

from app.demo.ravi import (
    EVENING_DOSE_AT,
    GLUCOSE_READING_IDS,
    MEDICATION_EVENT_ID,
    METFORMIN_ID,
    PATIENT_ID,
    PATIENT_REPORTED_MISSED,
    PATIENT_REPORTED_TAKEN,
    SCHEDULED_UNCONFIRMED,
    STORED_CONTACT,
)
from app.models import AdherenceLog, CareEvent, HealthReading, VoiceCall
from app.timeutil import utcnow

DEMO = "/api/v1/demo/ravi"


def test_profile_has_both_conditions(client):
    response = client.get(DEMO)
    assert response.status_code == 200
    body = response.get_json()
    profile = body["profile"]
    assert profile["id"] == str(PATIENT_ID)
    assert profile["preferred_name"] == "Ravi Sharma"
    assert profile["date_of_birth"] == "1974-03-18"
    assert profile["age"] == 52
    assert profile["preferred_language"] == "en"
    assert profile["contact_number"] == STORED_CONTACT
    assert profile["contact_number"] == "+15555501052"
    assert "operator-entered participant number" in profile["outbound_contact_policy"]
    assert profile["clinic"] == "CityCare Clinic"
    assert profile["doctor"] == "Dr. Mehta"
    assert {row["condition_type"] for row in profile["conditions"]} == {
        "type_2_diabetes",
        "hypertension",
    }
    assert all(row["treating_clinician"] == "Dr. Mehta" for row in profile["conditions"])
    assert profile["communication_preference"]["voice_calls"] == "allowed_only_after_consent"
    assert profile["onboarding_status"] == "not_onboarded"
    assert profile["consent_recorded"] is False
    assert [row["key"] for row in body["scenarios"]] == [
        "onboarding",
        "medication_followup",
        "weekly_checkin",
    ]
    consultation = body["schedule"]["next_consultation"]
    assert consultation["clinician"] == "Dr. Mehta"
    assert consultation["clinic"] == "CityCare Clinic"
    assert consultation["status"] == "scheduled"
    assert [(row["systolic"], row["diastolic"]) for row in body["schedule"]["blood_pressure_history"]] == [
        (136, 86),
        (142, 88),
        (130, 82),
    ]


def test_weekly_checkin_lists_two_missing_glucose_days(client):
    body = client.get(DEMO).get_json()
    missing = ["2026-11-11", "2026-11-14"]
    assert body["gaps"]["glucose_days_without_reading"] == missing
    assert body["gaps"]["glucose_days_with_reading"] == [
        "2026-11-09",
        "2026-11-10",
        "2026-11-12",
        "2026-11-13",
        "2026-11-15",
    ]
    weekly = next(row for row in body["scenarios"] if row["key"] == "weekly_checkin")
    assert weekly["state"]["glucose_days_without_reading"] == missing


def test_evening_dose_is_unconfirmed_not_missed(client, app):
    body = client.get(DEMO).get_json()
    dose = body["schedule"]["evening_dose"]
    assert dose["medication_name"] == "Metformin"
    assert dose["prescribed_dosage"] == "500 mg"
    assert dose["time_local"] == "20:00"
    assert dose["adherence_status"] == SCHEDULED_UNCONFIRMED
    assert dose["adherence_status"] != PATIENT_REPORTED_MISSED
    assert dose["presumed_missed"] is False
    followup = next(row for row in body["scenarios"] if row["key"] == "medication_followup")
    assert followup["state"]["adherence_status"] == SCHEDULED_UNCONFIRMED

    _add_log(app, reported_status="missed", source="inferred", hours_later=1)
    again = client.get(DEMO).get_json()
    assert again["schedule"]["evening_dose"]["adherence_status"] == SCHEDULED_UNCONFIRMED
    assert again["schedule"]["evening_dose"]["presumed_missed"] is False


def test_call_result_sets_reported_taken_or_missed(client, app):
    client.get(DEMO)
    _add_log(app, reported_status="taken", source="call_self_report", hours_later=1)
    taken = client.get(DEMO).get_json()["schedule"]["evening_dose"]
    assert taken["adherence_status"] == PATIENT_REPORTED_TAKEN
    assert taken["presumed_missed"] is False

    _add_log(app, reported_status="missed", source="inferred", hours_later=2)
    still_taken = client.get(DEMO).get_json()["schedule"]["evening_dose"]
    assert still_taken["adherence_status"] == PATIENT_REPORTED_TAKEN

    _add_log(app, reported_status="missed", source="call_self_report", hours_later=3)
    missed = client.get(DEMO).get_json()["schedule"]["evening_dose"]
    assert missed["adherence_status"] == PATIENT_REPORTED_MISSED
    assert missed["presumed_missed"] is False


def test_reset_is_idempotent(client, app):
    client.get(DEMO)
    _add_log(app, reported_status="missed", source="inferred", hours_later=1)
    _add_consent_call(app)
    _rewrite_followup_summary(app)
    _delete_glucose_reading(app)

    first = client.post(f"{DEMO}/reset")
    second = client.post(f"{DEMO}/reset")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.get_json() == second.get_json()
    body = second.get_json()
    assert body["profile"]["onboarding_status"] == "not_onboarded"
    assert body["profile"]["consent_recorded"] is False
    assert body["schedule"]["evening_dose"]["adherence_status"] == SCHEDULED_UNCONFIRMED
    assert body["gaps"]["glucose_days_without_reading"] == ["2026-11-11", "2026-11-14"]
    followup = next(row for row in body["scenarios"] if row["key"] == "medication_followup")
    assert "unconfirmed" in followup["summary"]
    assert followup["state"]["adherence_status"] == SCHEDULED_UNCONFIRMED
    assert client.get(DEMO).get_json() == body


def test_demo_routes_do_not_dial(client, monkeypatch):
    attempted = []

    def connect(self, address):
        attempted.append(address)
        raise AssertionError(f"demo route dialed {address}")

    def create_connection(*args, **kwargs):
        attempted.append(args)
        raise AssertionError("demo route opened a connection")

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "create_connection", create_connection)

    fetched = client.get(DEMO)
    restored = client.post(f"{DEMO}/reset")
    assert fetched.status_code == 200
    assert restored.status_code == 200
    assert attempted == []
    assert fetched.get_json()["profile"]["contact_number"] == "+15555501052"


def test_sqlite_fallback_matches_database_payload(client, monkeypatch):
    database = client.get(DEMO).get_json()
    monkeypatch.setattr("app.demo.ravi.chart_models_available", lambda: False)
    fallback = client.get(DEMO).get_json()
    assert fallback == database
    assert client.post(f"{DEMO}/reset").get_json() == database


def _add_log(app, *, reported_status: str, source: str, hours_later: int) -> None:
    from app.db import SessionLocal

    with app.app_context():
        session = SessionLocal()
        try:
            session.add(
                AdherenceLog(
                    patient_id=PATIENT_ID,
                    medication_id=METFORMIN_ID,
                    schedule_time=EVENING_DOSE_AT,
                    reported_status=reported_status,
                    reported_reason=None,
                    recorded_at=EVENING_DOSE_AT + timedelta(hours=hours_later),
                    source=source,
                )
            )
            session.commit()
        finally:
            session.close()


def _add_consent_call(app) -> None:
    from app.db import SessionLocal

    with app.app_context():
        session = SessionLocal()
        try:
            session.add(
                VoiceCall(
                    patient_id=PATIENT_ID,
                    bolna_call_id="ravi-synthetic-consent-row",
                    call_type="outbound",
                    language="en",
                    call_status="completed",
                    summary="Synthetic consent row written by the test. Not a phone call.",
                    extracted_data={"consent_recorded": True},
                    created_at=utcnow(),
                )
            )
            session.commit()
        finally:
            session.close()


def _rewrite_followup_summary(app) -> None:
    from app.db import SessionLocal

    with app.app_context():
        session = SessionLocal()
        try:
            event = session.get(CareEvent, MEDICATION_EVENT_ID)
            event.event_description = "Dose marked missed by the test."
            session.commit()
        finally:
            session.close()


def _delete_glucose_reading(app) -> None:
    from app.db import SessionLocal

    with app.app_context():
        session = SessionLocal()
        try:
            session.execute(delete(HealthReading).where(HealthReading.id == GLUCOSE_READING_IDS[0]))
            session.commit()
        finally:
            session.close()
