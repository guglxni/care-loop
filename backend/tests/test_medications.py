"""Active medication schedule and adherence reports."""

import uuid
from datetime import date, datetime, timedelta, timezone

from app.models import AdherenceLog, Medication, Patient
from app.services.seed_service import CLINICIAN, METFORMIN_ID, PATIENT_ID, TELMISARTAN_ID
from tests.helpers import assert_error, count_rows

MEDICATIONS = f"/api/v1/patients/{PATIENT_ID}/medications"
ADHERENCE = f"/api/v1/patients/{PATIENT_ID}/adherence"


def _schedule_time() -> str:
    moment = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(microsecond=0)
    return moment.isoformat().replace("+00:00", "Z")


def adherence_body(**changes) -> dict:
    body = {
        "medication_id": str(METFORMIN_ID),
        "schedule_time": _schedule_time(),
        "reported_status": "missed",
        "reported_reason": "The morning dose was not taken",
        "source": "app",
    }
    body.update(changes)
    return body


def _insert(app, *rows) -> None:
    from app.db import SessionLocal

    with app.app_context():
        session = SessionLocal()
        try:
            for row in rows:
                session.add(row)
                session.flush()
            session.commit()
        finally:
            session.close()


def test_active_medication_schedule(client):
    response = client.get(MEDICATIONS)
    assert response.status_code == 200
    rows = {row["id"]: row for row in response.get_json()["medications"]}
    assert set(rows) == {str(METFORMIN_ID), str(TELMISARTAN_ID)}
    assert rows[str(METFORMIN_ID)]["medication_name"] == "Metformin"
    assert rows[str(METFORMIN_ID)]["prescribed_dosage"] == "500 mg"
    assert rows[str(METFORMIN_ID)]["frequency"] == "Twice daily"
    assert rows[str(METFORMIN_ID)]["schedule"] == {"times": ["08:00", "20:00"]}
    assert rows[str(METFORMIN_ID)]["active"] is True
    assert rows[str(TELMISARTAN_ID)]["schedule"]["times"] == ["08:00"]
    assert rows[str(TELMISARTAN_ID)]["prescribed_dosage"] == "40 mg"


def test_record_adherence_does_not_change_dosage(client):
    before = client.get(MEDICATIONS).get_json()
    measured = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(microsecond=0)
    response = client.post(
        ADHERENCE,
        json=adherence_body(
            schedule_time=measured.isoformat().replace("+00:00", "Z"),
            source="call_self_report",
        ),
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["medication_id"] == str(METFORMIN_ID)
    assert body["patient_id"] == str(PATIENT_ID)
    assert body["reported_status"] == "missed"
    assert body["reported_reason"] == "The morning dose was not taken"
    assert body["source"] == "call_self_report"
    returned = datetime.fromisoformat(body["schedule_time"].replace("Z", "+00:00"))
    assert returned == measured
    assert "prescribed_dosage" not in body
    assert "dosage" not in body
    assert client.get(MEDICATIONS).get_json() == before


def test_adherence_rejects_unknown_medication(client, app):
    before = count_rows(app, AdherenceLog)
    response = client.post(
        ADHERENCE,
        json=adherence_body(medication_id="99999999-9999-4999-8999-999999999999"),
    )
    error = assert_error(response, 400, "validation_error")
    assert any("medication_id" in item for item in error["details"])
    assert count_rows(app, AdherenceLog) == before


def test_adherence_rejects_another_patients_medication(client, app):
    other_patient = uuid.UUID("88888888-8888-4888-8888-888888888888")
    other_medication = uuid.UUID("88888888-8888-4888-8888-888888888889")
    _insert(
        app,
        Patient(
            id=other_patient,
            preferred_name="Nila Rao",
            date_of_birth=date(1980, 1, 1),
            preferred_language="en",
            contact_number="+910000000000",
            allergies=[],
            emergency_contact={},
        ),
        Medication(
            id=other_medication,
            patient_id=other_patient,
            medication_name="Example",
            prescribed_dosage="1 mg",
            frequency="Once daily",
            schedule={"times": ["09:00"]},
            start_date=date(2024, 1, 1),
            prescribing_clinician=CLINICIAN,
            active=True,
        ),
    )
    response = client.post(ADHERENCE, json=adherence_body(medication_id=str(other_medication)))
    error = assert_error(response, 400, "validation_error")
    assert any("does not match a medication for this patient" in item for item in error["details"])
    assert count_rows(app, AdherenceLog) == 0


def test_adherence_rejects_a_dose_change(client, app):
    before = client.get(MEDICATIONS).get_json()
    response = client.post(
        ADHERENCE,
        json=adherence_body(prescribed_dosage="1000 mg", dose="1000 mg"),
    )
    error = assert_error(response, 400, "validation_error")
    assert any("prescribed_dosage" in item and "dose change" in item for item in error["details"])
    assert any(item.startswith("dose ") for item in error["details"])
    assert client.get(MEDICATIONS).get_json() == before
    assert count_rows(app, AdherenceLog) == 0


def test_unknown_patient_adherence_is_not_found(client):
    unknown = "99999999-9999-4999-8999-999999999999"
    assert_error(client.post(f"/api/v1/patients/{unknown}/adherence", json={}), 404, "not_found")
    assert_error(client.get(f"/api/v1/patients/{unknown}/medications"), 404, "not_found")
