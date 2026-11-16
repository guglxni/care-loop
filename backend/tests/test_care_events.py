"""Care events store the description that was submitted."""

from app.services.seed_service import PATIENT_ID
from tests.helpers import assert_error

EVENTS = f"/api/v1/patients/{PATIENT_ID}/care-events"


def test_create_and_list_care_event(client):
    description = "Patient asked for a clinician to review the log."
    created = client.post(
        EVENTS,
        json={
            "event_type": "clinician_review_requested",
            "event_description": description,
            "priority": "medium",
        },
    )
    assert created.status_code == 201
    body = created.get_json()
    assert body["event_description"] == description
    assert body["event_type"] == "clinician_review_requested"
    assert body["priority"] == "medium"
    assert body["status"] == "open"
    assert body["resolved_at"] is None
    assert body["patient_id"] == str(PATIENT_ID)
    assert "advice" not in body
    assert "recommendation" not in body
    assert "you should" not in created.get_data(as_text=True).lower()

    listed = client.get(EVENTS)
    assert listed.status_code == 200
    rows = listed.get_json()["care_events"]
    assert rows[0]["id"] == body["id"]
    assert rows[0]["event_description"] == description


def test_care_event_can_be_opened_as_resolved(client):
    response = client.post(
        EVENTS,
        json={
            "event_type": "note",
            "event_description": "Stored note only.",
            "priority": "low",
            "status": "resolved",
        },
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["status"] == "resolved"
    assert body["resolved_at"].endswith("Z")
    assert body["event_description"] == "Stored note only."


def test_care_event_validation(client):
    response = client.post(
        EVENTS,
        json={
            "event_type": "clinician_review_requested",
            "event_description": "Patient asked for a clinician to review the log.",
            "priority": "urgent",
        },
    )
    error = assert_error(response, 400, "validation_error")
    assert any("priority must be one of" in item for item in error["details"])
    missing = assert_error(client.post(EVENTS, json={"priority": "low"}), 400, "validation_error")
    assert any("event_description is required" in item for item in missing["details"])
    assert client.get(EVENTS).get_json()["care_events"] == []


def test_unknown_patient_care_events_are_not_found(client):
    unknown = "99999999-9999-4999-8999-999999999999"
    assert_error(client.get(f"/api/v1/patients/{unknown}/care-events"), 404, "not_found")
    assert_error(client.post(f"/api/v1/patients/{unknown}/care-events", json={}), 404, "not_found")
