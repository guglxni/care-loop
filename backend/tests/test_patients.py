"""Profile, profile updates, and the chart history endpoint."""

import uuid
from datetime import date

import pytest

from app.models import Medication, Patient
from app.services.seed_service import (
    CLINICIAN,
    CONSULTATION_ID,
    MEDICAL_HISTORY,
    METFORMIN_ID,
    PATIENT_ID,
    TELMISARTAN_ID,
)
from tests.helpers import assert_error

UNKNOWN = "99999999-9999-4999-8999-999999999999"
PROFILE = f"/api/v1/patients/{PATIENT_ID}"


def test_routes_are_registered(app):
    found = set()
    for rule in app.url_map.iter_rules():
        methods = rule.methods - {"HEAD", "OPTIONS"}
        for method in methods:
            found.add((method, rule.rule))
    expected = {
        ("GET", "/api/v1/patients/<patient_id>"),
        ("PATCH", "/api/v1/patients/<patient_id>"),
        ("GET", "/api/v1/patients/<patient_id>/history"),
        ("POST", "/api/v1/patients/<patient_id>/readings/glucose"),
        ("POST", "/api/v1/patients/<patient_id>/readings/blood-pressure"),
        ("GET", "/api/v1/patients/<patient_id>/medications"),
        ("POST", "/api/v1/patients/<patient_id>/adherence"),
        ("GET", "/api/v1/patients/<patient_id>/consultations/upcoming"),
        ("POST", "/api/v1/consultations/<consultation_id>"),
        ("GET", "/api/v1/patients/<patient_id>/care-events"),
        ("POST", "/api/v1/patients/<patient_id>/care-events"),
        ("GET", "/api/v1/patients/<patient_id>/bolna/context"),
        ("POST", "/api/v1/patients/<patient_id>/bolna/call-outcomes"),
        ("POST", "/api/v1/bolna/webhook"),
    }
    assert expected <= found


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", f"/api/v1/patients/{UNKNOWN}"),
        ("get", f"/api/v1/patients/{UNKNOWN}/history"),
        ("get", f"/api/v1/patients/{UNKNOWN}/medications"),
        ("get", f"/api/v1/patients/{UNKNOWN}/consultations/upcoming"),
        ("get", f"/api/v1/patients/{UNKNOWN}/care-events"),
        ("get", f"/api/v1/patients/{UNKNOWN}/bolna/context?purpose=general"),
        ("get", "/api/v1/patients/not-a-uuid"),
    ],
)
def test_unknown_patient_is_not_found(client, method, path):
    response = getattr(client, method)(path)
    assert_error(response, 404, "not_found")


def test_get_profile(client):
    response = client.get(PROFILE)
    assert response.status_code == 200
    body = response.get_json()
    assert body["id"] == str(PATIENT_ID)
    assert body["preferred_name"] == "Meera Iyer"
    assert body["date_of_birth"] == "1978-04-12"
    assert body["preferred_language"] == "en"
    assert body["contact_number"] == "+919840011223"
    assert body["medical_history"] == MEDICAL_HISTORY
    assert "Synthetic chart note" in body["medical_history"]
    assert body["allergies"] == ["Penicillin"]
    assert body["emergency_contact"]["name"] == "Arjun Iyer"
    assert body["created_at"].endswith("Z")
    assert body["updated_at"].endswith("Z")


def test_patch_profile_updates_allowed_fields(client):
    response = client.patch(
        PROFILE,
        json={
            "preferred_name": "Meera",
            "preferred_language": "en",
            "contact_number": "+91 98400 77889",
            "allergies": ["Penicillin", "Peanuts"],
            "emergency_contact": {"name": "Arjun Iyer", "relation": "Spouse", "phone": "+919840044556"},
        },
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["preferred_name"] == "Meera"
    assert body["preferred_language"] == "en"
    assert body["contact_number"] == "+919840077889"
    assert body["allergies"] == ["Penicillin", "Peanuts"]
    assert body["medical_history"] == MEDICAL_HISTORY
    assert body["date_of_birth"] == "1978-04-12"


@pytest.mark.parametrize("code", ["hi", "kn"])
def test_patch_accepts_hindi_and_kannada(client, code):
    response = client.patch(PROFILE, json={"preferred_language": code})
    assert response.status_code == 200
    assert response.get_json()["preferred_language"] == code


def test_patch_rejects_contact_without_leading_plus(client):
    response = client.patch(PROFILE, json={"contact_number": "919840011223"})
    error = assert_error(response, 400, "validation_error")
    assert any("contact_number" in item for item in error["details"])
    assert client.get(PROFILE).get_json()["contact_number"] == "+919840011223"


def test_patch_rejects_diagnosis_prescription_and_dose(client):
    response = client.patch(
        PROFILE,
        json={
            "preferred_name": "Changed Name",
            "diagnosis": "type 2 diabetes",
            "prescribed_dosage": "1000 mg",
            "prescription": "increase metformin",
        },
    )
    error = assert_error(response, 400, "validation_error")
    assert any("diagnosis" in item for item in error["details"])
    assert any("prescribed_dosage" in item for item in error["details"])
    profile = client.get(PROFILE).get_json()
    assert profile["preferred_name"] == "Meera Iyer"


def test_history_returns_the_chart(client):
    response = client.get(f"{PROFILE}/history")
    assert response.status_code == 200
    body = response.get_json()
    assert body["patient_id"] == str(PATIENT_ID)
    assert {row["condition_type"] for row in body["conditions"]} == {
        "type_2_diabetes",
        "hypertension",
    }
    assert {row["treating_clinician"] for row in body["conditions"]} == {CLINICIAN}
    medications = {row["id"]: row for row in body["medications"]}
    assert set(medications) == {str(METFORMIN_ID), str(TELMISARTAN_ID)}
    assert medications[str(METFORMIN_ID)]["prescribed_dosage"] == "500 mg"
    assert medications[str(METFORMIN_ID)]["schedule"]["times"] == ["08:00", "20:00"]
    types = [row["measurement_type"] for row in body["recent_readings"]]
    assert types.count("blood_glucose") == 5
    assert "systolic_blood_pressure" in types
    assert "diastolic_blood_pressure" in types
    assert "pulse" in types
    consultations = {row["id"]: row for row in body["consultations"]}
    assert consultations[str(CONSULTATION_ID)]["appointment_date"].startswith("2026-11-20")
    assert consultations[str(CONSULTATION_ID)]["status"] == "scheduled"
    assert body["care_plan"][0]["condition"] == "type_2_diabetes"
    assert body["care_plan"][0]["clinician"] == CLINICIAN
    assert {row["document_type"] for row in body["documents"]} == {"prescription", "lab_report"}
    assert all(row["file_location"].startswith("synthetic://chart/") for row in body["documents"])
    assert "medical_history" not in body


def test_history_includes_inactive_medication_schedule_does_not(client, app):
    inactive_id = uuid.UUID("99999999-9999-4999-8999-999999999991")
    _insert(
        app,
        Medication(
            id=inactive_id,
            patient_id=PATIENT_ID,
            medication_name="Vitamin D",
            prescribed_dosage="60000 IU",
            frequency="Weekly",
            schedule={"times": ["08:00"], "weekdays": ["monday"]},
            start_date=date(2025, 1, 6),
            end_date=date(2025, 3, 31),
            prescribing_clinician=CLINICIAN,
            active=False,
        ),
    )
    listed = [row["id"] for row in client.get(f"{PROFILE}/medications").get_json()["medications"]]
    assert str(inactive_id) not in listed
    history_ids = [row["id"] for row in client.get(f"{PROFILE}/history").get_json()["medications"]]
    assert str(inactive_id) in history_ids


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


def test_other_patient_is_not_in_meera_profile(client, app):
    other_id = uuid.UUID("88888888-8888-4888-8888-888888888888")
    _insert(
        app,
        Patient(
            id=other_id,
            preferred_name="Nila Rao",
            date_of_birth=date(1980, 1, 1),
            preferred_language="en",
            contact_number="+910000000000",
            medical_history="A different synthetic chart.",
            allergies=[],
            emergency_contact={},
        ),
    )
    body = client.get(PROFILE).get_json()
    assert body["preferred_name"] == "Meera Iyer"
    assert "Nila Rao" not in body["preferred_name"]
