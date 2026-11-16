"""Completed Bolna executions map onto adherence, care events, and the voice call."""

import uuid

from sqlalchemy import select

from app.calls.results import save_call_result
from app.db import SessionLocal
from app.models import AdherenceLog, CareEvent, Document, HealthReading, Medication, VoiceCall
from app.services.seed_service import (
    METFORMIN_ID,
    PATIENT_ID,
    SEEDED_HEALTH_READINGS,
    TELMISARTAN_ID,
)
from tests.helpers import count_rows, voice_calls

WEBHOOK = "/api/v1/bolna/webhook"
SUMMARY = "Evening metformin was missed."
CONCERN = "Felt unsteady on the way home"
SCHEDULE = "2026-11-15T14:30:00Z"


def _missed_payload(**extracted) -> dict:
    data = {
        "medication_status": "missed",
        "medication_id": str(METFORMIN_ID),
        "missed_reason": "Away from home",
        "concern": CONCERN,
        "follow_up_required": True,
        "schedule_time": SCHEDULE,
    }
    data.update(extracted)
    return {
        "id": "exec-missed-1",
        "status": "completed",
        "patient_id": str(PATIENT_ID),
        "call_type": "outbound",
        "language": "en",
        "summary": SUMMARY,
        "extracted_data": data,
    }


def _save(app, payload: dict) -> dict:
    with app.app_context():
        session = SessionLocal()
        try:
            return save_call_result(session, payload)
        finally:
            session.close()


def _rows(app, model) -> list[dict]:
    with app.app_context():
        session = SessionLocal()
        try:
            rows = session.scalars(select(model)).all()
            return [row.to_dict() for row in rows]
        finally:
            session.close()


def test_missed_medication_payload_saves_adherence_concern_follow_up_and_summary(app):
    before_medications = _rows(app, Medication)
    before_documents = count_rows(app, Document)
    before_readings = count_rows(app, HealthReading)

    saved = _save(app, _missed_payload())

    logs = _rows(app, AdherenceLog)
    events = {row["event_type"]: row for row in _rows(app, CareEvent)}
    calls = voice_calls(app)
    assert len(logs) == 1
    assert logs[0]["patient_id"] == str(PATIENT_ID)
    assert logs[0]["medication_id"] == str(METFORMIN_ID)
    assert logs[0]["reported_status"] == "missed"
    assert logs[0]["reported_reason"] == "Away from home"
    assert logs[0]["source"] == "call_self_report"
    assert logs[0]["schedule_time"] == SCHEDULE
    assert events["patient_concern"]["event_description"] == CONCERN
    assert events["patient_concern"]["priority"] == "medium"
    assert events["patient_concern"]["status"] == "open"
    assert events["patient_concern"]["resolved_at"] is None
    assert events["follow_up_task"]["event_description"] == "Follow-up requested from the call."
    assert events["follow_up_task"]["priority"] == "medium"
    assert events["follow_up_task"]["status"] == "open"
    assert len(calls) == 1
    assert calls[0]["bolna_call_id"] == "exec-missed-1"
    assert calls[0]["summary"] == SUMMARY
    assert calls[0]["call_status"] == "completed"
    assert calls[0]["patient_id"] == str(PATIENT_ID)
    assert saved["adherence_logs"][0]["reported_status"] == "missed"
    assert _rows(app, Medication) == before_medications
    assert count_rows(app, Document) == before_documents
    assert count_rows(app, HealthReading) == before_readings == SEEDED_HEALTH_READINGS


def test_uncertain_is_stored_as_unknown(app):
    _save(
        app,
        _missed_payload(
            medication_status="uncertain",
            concern="",
            follow_up_required=False,
            missed_reason=None,
        ),
    )
    logs = _rows(app, AdherenceLog)
    assert len(logs) == 1
    assert logs[0]["reported_status"] == "unknown"
    assert logs[0]["reported_status"] not in {"taken", "missed"}
    assert logs[0]["source"] == "call_self_report"
    assert logs[0]["medication_id"] == str(METFORMIN_ID)
    assert _rows(app, CareEvent) == []


def test_unconfirmed_dose_is_not_marked_missed(app):
    _save(app, _missed_payload(medication_status="not_discussed"))
    assert _rows(app, AdherenceLog) == []

    omitted = _missed_payload()
    omitted["id"] = "exec-omitted"
    omitted["extracted_data"].pop("medication_status")
    _save(app, omitted)
    assert _rows(app, AdherenceLog) == []

    skipped = {
        "id": "exec-skipped",
        "status": "completed",
        "patient_id": str(PATIENT_ID),
        "summary": "The dose was not confirmed.",
        "extracted_data": {
            "Call outcomes": {
                "medication_status": {
                    "objective": "Missed",
                    "status": "skipped",
                },
                "medication_id": {"objective": str(METFORMIN_ID), "status": "completed"},
            }
        },
    }
    _save(app, skipped)
    assert _rows(app, AdherenceLog) == []
    assert all(row["reported_status"] != "missed" for row in _rows(app, AdherenceLog))


def test_empty_extracted_data_and_non_completed_calls_are_ignored(app):
    _save(app, {**_missed_payload(), "extracted_data": {}})
    _save(app, {**_missed_payload(), "extracted_data": None, "id": "exec-none"})
    _save(app, {**_missed_payload(), "status": "no-answer", "id": "exec-no-answer"})
    assert voice_calls(app) == []
    assert _rows(app, AdherenceLog) == []
    assert _rows(app, CareEvent) == []


def test_medication_is_resolved_by_name_or_the_only_active_medicine(app):
    named = _missed_payload(medication_status="taken", medication_name="Metformin")
    named["id"] = "exec-named"
    named["extracted_data"].pop("medication_id")
    named["extracted_data"].pop("concern")
    named["extracted_data"]["follow_up_required"] = False
    _save(app, named)
    named_logs = _rows(app, AdherenceLog)
    assert len(named_logs) == 1
    assert named_logs[0]["reported_status"] == "taken"
    assert named_logs[0]["medication_id"] == str(METFORMIN_ID)

    with app.app_context():
        session = SessionLocal()
        try:
            telmisartan = session.get(Medication, TELMISARTAN_ID)
            assert telmisartan is not None
            telmisartan.active = False
            session.commit()
            save_call_result(
                session,
                {
                    "id": "exec-only-active",
                    "status": "completed",
                    "patient_id": str(PATIENT_ID),
                    "summary": "The only active dose was missed.",
                    "extracted_data": {"medication_status": "missed"},
                },
            )
        finally:
            session.close()
    logs = _rows(app, AdherenceLog)
    only_active = next(row for row in logs if row["medication_id"] == str(METFORMIN_ID) and row["reported_status"] == "missed")
    assert only_active["source"] == "call_self_report"
    assert count_rows(app, Medication) == 2


def test_unresolved_or_foreign_medication_does_not_create_a_prescription(app):
    before_medications = _rows(app, Medication)
    before_documents = count_rows(app, Document)
    missing = _missed_payload(medication_status="missed")
    missing["id"] = "exec-unresolved"
    missing["extracted_data"].pop("medication_id")
    missing["summary"] = "A dose was missed, medicine not named."
    _save(app, missing)
    assert _rows(app, AdherenceLog) == []
    assert voice_calls(app)[0]["summary"] == "A dose was missed, medicine not named."

    foreign = _missed_payload(medication_id=str(uuid.uuid4()))
    foreign["id"] = "exec-foreign"
    _save(app, foreign)
    assert _rows(app, AdherenceLog) == []
    assert _rows(app, Medication) == before_medications
    assert count_rows(app, Document) == before_documents


def test_existing_voice_call_is_updated_by_bolna_call_id(app):
    with app.app_context():
        session = SessionLocal()
        try:
            session.add(
                VoiceCall(
                    patient_id=PATIENT_ID,
                    bolna_call_id="exec-queued",
                    call_type="outbound",
                    language="en",
                    call_status="queued",
                    summary="evening medication check-in",
                    extracted_data={"purpose": "medication_check"},
                )
            )
            session.commit()
            save_call_result(
                session,
                {
                    "bolna_call_id": "exec-queued",
                    "status": "completed",
                    "patient_id": str(PATIENT_ID),
                    "summary": "Patient took the evening metformin.",
                    "extracted_data": {
                        "medication_status": "taken",
                        "medication_id": str(METFORMIN_ID),
                    },
                },
            )
        finally:
            session.close()
    calls = voice_calls(app)
    assert len(calls) == 1
    assert calls[0]["bolna_call_id"] == "exec-queued"
    assert calls[0]["summary"] == "Patient took the evening metformin."
    assert calls[0]["call_status"] == "completed"
    logs = _rows(app, AdherenceLog)
    assert len(logs) == 1
    assert logs[0]["reported_status"] == "taken"
    assert logs[0]["source"] == "call_self_report"


def test_nested_disposition_maps_a_missed_dose(app):
    _save(
        app,
        {
            "id": "exec-nested",
            "status": "completed",
            "patient_id": str(PATIENT_ID),
            "summary": "Missed the evening dose.",
            "extracted_data": {
                "Call outcomes": {
                    "medication_status": {
                        "objective": "Missed",
                        "subjective": None,
                        "status": "completed",
                    },
                    "medication_id": {
                        "objective": str(METFORMIN_ID),
                        "status": "completed",
                    },
                    "concern": {
                        "subjective": "Dizzy while walking",
                        "objective": None,
                        "status": "completed",
                    },
                    "follow_up_required": {
                        "objective": True,
                        "status": "completed",
                    },
                }
            },
        },
    )
    logs = _rows(app, AdherenceLog)
    events = {row["event_type"]: row for row in _rows(app, CareEvent)}
    assert len(logs) == 1
    assert logs[0]["reported_status"] == "missed"
    assert logs[0]["medication_id"] == str(METFORMIN_ID)
    assert logs[0]["source"] == "call_self_report"
    assert events["patient_concern"]["event_description"] == "Dizzy while walking"
    assert events["patient_concern"]["priority"] == "medium"
    assert events["follow_up_task"]["event_type"] == "follow_up_task"
    assert voice_calls(app)[0]["summary"] == "Missed the evening dose."


def test_webhook_saves_a_missed_medication_once(client, app):
    payload = _missed_payload()
    payload["id"] = "exec-webhook-missed"
    first = client.post(WEBHOOK, json=payload)
    assert first.status_code == 200
    assert first.get_json()["duplicate"] is False
    second = client.post(WEBHOOK, json={**payload, "summary": "Retry must not add another dose."})
    assert second.status_code == 200
    assert second.get_json() == {"duplicate": True}

    logs = _rows(app, AdherenceLog)
    assert len(logs) == 1
    assert logs[0]["reported_status"] == "missed"
    assert logs[0]["source"] == "call_self_report"
    assert logs[0]["medication_id"] == str(METFORMIN_ID)
    assert len(_rows(app, CareEvent)) == 2
    calls = voice_calls(app)
    assert len(calls) == 1
    assert calls[0]["summary"] == SUMMARY
    assert count_rows(app, Medication) == 2
    assert count_rows(app, HealthReading) == SEEDED_HEALTH_READINGS


def test_not_discussed_alias_does_not_mark_a_dose_missed(app):
    _save(
        app,
        {
            "id": "exec-alias",
            "status": "completed",
            "patient_id": str(PATIENT_ID),
            "summary": "Glucose was discussed.",
            "extracted_data": {
                "medication_adherence": "Not_Discussed",
                "medication_id": str(METFORMIN_ID),
            },
        },
    )
    assert _rows(app, AdherenceLog) == []
    assert voice_calls(app)[0]["summary"] == "Glucose was discussed."


def test_invalid_schedule_time_does_not_save_a_guessed_miss(app):
    payload = _missed_payload(schedule_time="tomorrow evening")
    _save(app, payload)
    assert _rows(app, AdherenceLog) == []
    assert voice_calls(app)[0]["summary"] == SUMMARY
