"""Upcoming consultation and status or time updates."""

from datetime import datetime, timedelta, timezone

from app.services.seed_service import CONSULTATION_ID, PATIENT_ID
from tests.helpers import assert_error

UPCOMING = f"/api/v1/patients/{PATIENT_ID}/consultations/upcoming"
CONSULTATION = f"/api/v1/consultations/{CONSULTATION_ID}"


def test_upcoming_seed_and_update(client):
    history = client.get(f"/api/v1/patients/{PATIENT_ID}/history").get_json()
    seeded = next(row for row in history["consultations"] if row["id"] == str(CONSULTATION_ID))
    assert seeded["appointment_date"].startswith("2026-11-20")
    assert seeded["status"] == "scheduled"
    assert seeded["consultation_type"] == "consultation"
    assert seeded["clinician"] == "Dr. Anika Shah"

    upcoming = client.get(UPCOMING)
    assert upcoming.status_code == 200
    current = upcoming.get_json()["consultation"]
    seed_at = datetime.fromisoformat(seeded["appointment_date"].replace("Z", "+00:00"))
    if datetime.now(timezone.utc) <= seed_at:
        assert current["id"] == str(CONSULTATION_ID)
        assert current["appointment_date"].startswith("2026-11-20")
    else:
        assert current is None

    future = (datetime.now(timezone.utc) + timedelta(days=10)).replace(microsecond=0)
    updated = client.post(
        CONSULTATION,
        json={
            "status": "scheduled",
            "appointment_date": future.isoformat().replace("+00:00", "Z"),
        },
    )
    assert updated.status_code == 200
    body = updated.get_json()
    assert body["status"] == "scheduled"
    assert body["appointment_date"] == future.isoformat().replace("+00:00", "Z")
    again = client.get(UPCOMING).get_json()["consultation"]
    assert again["id"] == str(CONSULTATION_ID)

    rescheduled = client.post(CONSULTATION, json={"status": "rescheduled"})
    assert rescheduled.status_code == 200
    assert rescheduled.get_json()["status"] == "rescheduled"
    assert client.get(UPCOMING).get_json()["consultation"] is None

    completed = client.post(
        CONSULTATION,
        json={"status": "completed", "appointment_date": "2026-11-20T09:30:00+05:30"},
    )
    assert completed.status_code == 200
    assert completed.get_json()["appointment_date"] == "2026-11-20T04:00:00Z"
    assert client.get(UPCOMING).get_json()["consultation"] is None


def test_consultation_unknown_is_not_found(client):
    response = client.post(
        "/api/v1/consultations/99999999-9999-4999-8999-999999999999",
        json={"status": "completed"},
    )
    assert_error(response, 404, "not_found")
    assert_error(
        client.post("/api/v1/consultations/not-a-uuid", json={"status": "completed"}),
        404,
        "not_found",
    )


def test_consultation_validation(client):
    naive = assert_error(
        client.post(CONSULTATION, json={"appointment_date": "2026-11-21T09:30:00"}),
        400,
        "validation_error",
    )
    assert any("timezone" in item for item in naive["details"])
    bad_status = assert_error(
        client.post(CONSULTATION, json={"status": "confirmed"}),
        400,
        "validation_error",
    )
    assert any("status must be one of" in item for item in bad_status["details"])
    empty = assert_error(client.post(CONSULTATION, json={}), 400, "validation_error")
    assert any("status or appointment_date" in item for item in empty["details"])
    dose = assert_error(
        client.post(CONSULTATION, json={"status": "scheduled", "prescribed_dosage": "1000 mg"}),
        400,
        "validation_error",
    )
    assert any("prescribed_dosage" in item for item in dose["details"])
    unchanged = client.get(UPCOMING).get_json()["consultation"]
    if unchanged is not None:
        assert unchanged["status"] == "scheduled"
