"""Glucose and blood pressure validation."""

import re
from datetime import datetime, timedelta, timezone

import pytest

from app.services.seed_service import PATIENT_ID
from tests.helpers import assert_error

GLUCOSE = f"/api/v1/patients/{PATIENT_ID}/readings/glucose"
PRESSURE = f"/api/v1/patients/{PATIENT_ID}/readings/blood-pressure"
LABEL_WORDS = re.compile(r"\b(high|low|hyper|hypo)\b", re.IGNORECASE)


def _past_iso(hours: int = 2) -> str:
    moment = (datetime.now(timezone.utc) - timedelta(hours=hours)).replace(microsecond=0)
    return moment.isoformat().replace("+00:00", "Z")


def glucose_body(**changes) -> dict:
    body = {
        "value": 125,
        "unit": "mg/dL",
        "measurement_context": "fasting",
        "measured_at": _past_iso(),
        "source": "glucometer",
        "device_id": "meter-1",
        "support": "spouse present",
    }
    body.update(changes)
    return body


def pressure_body(**changes) -> dict:
    body = {
        "systolic": 126,
        "diastolic": 80,
        "pulse": 71,
        "unit": "mmHg",
        "measured_at": _past_iso(3),
        "source": "home_monitor",
        "device_id": "cuff-1",
    }
    body.update(changes)
    return body


def test_record_glucose(client):
    measured = (datetime.now(timezone.utc) - timedelta(hours=2)).replace(microsecond=0)
    payload = glucose_body(measured_at=measured.isoformat().replace("+00:00", "Z"), value=182)
    response = client.post(GLUCOSE, json=payload)
    assert response.status_code == 201
    body = response.get_json()
    assert body["measurement_type"] == "blood_glucose"
    assert body["value"] == 182
    assert body["secondary_value"] is None
    assert body["unit"] == "mg/dL"
    assert body["measurement_context"] == "fasting"
    assert body["source"] == "glucometer"
    assert body["device_id"] == "meter-1"
    assert body["support"] == "spouse present"
    assert body["data_quality"] == "valid"
    assert body["patient_id"] == str(PATIENT_ID)
    returned = datetime.fromisoformat(body["measured_at"].replace("Z", "+00:00"))
    assert returned == measured
    assert body["measured_at"].endswith("Z")
    assert LABEL_WORDS.search(response.get_data(as_text=True)) is None
    assert "interpretation" not in body


def test_record_glucose_accepts_a_numeric_string(client):
    response = client.post(GLUCOSE, json=glucose_body(value="131"))
    assert response.status_code == 201
    assert response.get_json()["value"] == 131


def test_record_glucose_mmol(client):
    response = client.post(GLUCOSE, json=glucose_body(value=7.5, unit="mmol/L", source="manual"))
    assert response.status_code == 201
    body = response.get_json()
    assert body["unit"] == "mmol/L"
    assert body["value"] == 7.5
    assert body["source"] == "manual"
    assert LABEL_WORDS.search(response.get_data(as_text=True)) is None


def test_glucose_accepts_a_timestamp_within_five_minutes(client):
    soon = (datetime.now(timezone.utc) + timedelta(minutes=4)).replace(microsecond=0)
    response = client.post(
        GLUCOSE,
        json=glucose_body(measured_at=soon.isoformat().replace("+00:00", "Z")),
    )
    assert response.status_code == 201


def test_glucose_rejects_a_timestamp_more_than_five_minutes_ahead(client):
    future = datetime.now(timezone.utc) + timedelta(minutes=6)
    response = client.post(GLUCOSE, json=glucose_body(measured_at=future.isoformat()))
    error = assert_error(response, 400, "validation_error")
    assert any("5 minutes" in item for item in error["details"])


@pytest.mark.parametrize(
    ("changes", "fragment"),
    [
        ({"value": 20}, "greater than 20"),
        ({"value": 600}, "less than 600"),
        ({"value": 1, "unit": "mmol/L"}, "greater than 1"),
        ({"value": 33, "unit": "mmol/L"}, "less than 33"),
        ({"measured_at": None}, "measured_at is required"),
        ({"measured_at": "2026-11-15T07:20:00"}, "timezone"),
        ({"unit": None}, "unit is required"),
        ({"source": None}, "source is required"),
        ({"source": "clinic"}, "source must be one of"),
        ({"measurement_context": "resting"}, "measurement_context must be one of"),
        ({"measurement_context": None}, "measurement_context is required"),
    ],
)
def test_glucose_validation(client, changes, fragment):
    body = glucose_body()
    for key, value in changes.items():
        if value is None:
            body.pop(key, None)
        else:
            body[key] = value
    error = assert_error(client.post(GLUCOSE, json=body), 400, "validation_error")
    assert any(fragment in item for item in error["details"])


def test_record_blood_pressure_with_pulse(client):
    measured = (datetime.now(timezone.utc) - timedelta(hours=3)).replace(microsecond=0)
    payload = pressure_body(measured_at=measured.isoformat().replace("+00:00", "Z"))
    response = client.post(PRESSURE, json=payload)
    assert response.status_code == 201
    readings = response.get_json()["readings"]
    assert [row["measurement_type"] for row in readings] == [
        "systolic_blood_pressure",
        "diastolic_blood_pressure",
        "pulse",
    ]
    systolic, diastolic, pulse = readings
    assert systolic["value"] == 126
    assert systolic["secondary_value"] == 80
    assert systolic["unit"] == "mmHg"
    assert diastolic["value"] == 80
    assert diastolic["secondary_value"] is None
    assert diastolic["unit"] == "mmHg"
    assert pulse["value"] == 71
    assert pulse["unit"] == "bpm"
    assert pulse["secondary_value"] is None
    for row in readings:
        assert row["source"] == "home_monitor"
        assert row["device_id"] == "cuff-1"
        assert row["data_quality"] == "valid"
        assert row["patient_id"] == str(PATIENT_ID)
        returned = datetime.fromisoformat(row["measured_at"].replace("Z", "+00:00"))
        assert returned == measured
    assert LABEL_WORDS.search(response.get_data(as_text=True)) is None


def test_record_blood_pressure_without_pulse(client):
    payload = pressure_body()
    payload.pop("pulse")
    response = client.post(PRESSURE, json=payload)
    assert response.status_code == 201
    readings = response.get_json()["readings"]
    assert [row["measurement_type"] for row in readings] == [
        "systolic_blood_pressure",
        "diastolic_blood_pressure",
    ]
    assert readings[0]["secondary_value"] == readings[1]["value"]


@pytest.mark.parametrize(
    ("changes", "fragment"),
    [
        ({"systolic": 69}, "systolic must be between 70 and 250"),
        ({"systolic": 251}, "systolic must be between 70 and 250"),
        ({"diastolic": 39}, "diastolic must be between 40 and 150"),
        ({"diastolic": 151, "systolic": 200}, "diastolic must be between 40 and 150"),
        ({"systolic": 120, "diastolic": 120}, "systolic must be greater than diastolic"),
        ({"pulse": 29}, "pulse must be between 30 and 220"),
        ({"pulse": 221}, "pulse must be between 30 and 220"),
        ({"unit": None}, "unit is required"),
        ({"unit": "mg/dL"}, "unit must be one of: mmHg"),
        ({"measured_at": None}, "measured_at is required"),
        ({"measured_at": "2026-11-15T08:10:00"}, "timezone"),
        ({"source": None}, "source is required"),
        ({"source": "glucometer"}, "source must be one of"),
    ],
)
def test_blood_pressure_validation(client, changes, fragment):
    body = pressure_body()
    for key, value in changes.items():
        if value is None:
            body.pop(key, None)
        else:
            body[key] = value
    error = assert_error(client.post(PRESSURE, json=body), 400, "validation_error")
    assert any(fragment in item for item in error["details"])


def test_unknown_patient_readings_are_not_found(client):
    unknown = "99999999-9999-4999-8999-999999999999"
    assert_error(client.post(f"/api/v1/patients/{unknown}/readings/glucose", json={}), 404, "not_found")
    assert_error(
        client.post(f"/api/v1/patients/{unknown}/readings/blood-pressure", json={}),
        404,
        "not_found",
    )
