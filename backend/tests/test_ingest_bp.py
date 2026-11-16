"""Common blood-pressure ingest: manual, CSV, and a refused Bluetooth channel."""

from datetime import datetime, timezone

import pytest

from app.models import HealthReading
from app.services.seed_service import PATIENT_ID
from tests.helpers import assert_error, count_rows

INGEST = f"/api/v1/patients/{PATIENT_ID}/ingest/blood-pressure"


@pytest.fixture
def client(app):
    from app.ingest.bp_routes import bp

    if bp.name not in app.blueprints:
        app.register_blueprint(bp)
    return app.test_client()


def _readings_at(app, measured_at: str) -> list[dict]:
    from sqlalchemy import select

    from app.db import SessionLocal

    moment = datetime.fromisoformat(measured_at.replace("Z", "+00:00")).astimezone(timezone.utc)
    with app.app_context():
        session = SessionLocal()
        try:
            rows = session.scalars(
                select(HealthReading).where(HealthReading.patient_id == PATIENT_ID)
            ).all()
        finally:
            session.close()
    matched = []
    for row in rows:
        stored = row.measured_at.astimezone(timezone.utc).replace(microsecond=0)
        if stored == moment.replace(microsecond=0):
            body = row.to_dict()
            if "ingest_origin" in HealthReading.__table__.columns:
                body["ingest_origin"] = row.ingest_origin
            matched.append(body)
    return matched


def test_bluetooth_is_not_connected(client, app):
    before = count_rows(app, HealthReading)
    response = client.post(
        INGEST,
        json={"channel": "bluetooth", "rows": [{"systolic": 10}]},
    )
    assert response.status_code == 501
    assert response.get_json() == {
        "error": {
            "code": "not_connected",
            "message": "Bluetooth blood pressure devices are not connected.",
        }
    }
    assert count_rows(app, HealthReading) == before


def test_csv_device_reported_row_is_stored(client, app):
    csv_text = (
        "systolic,diastolic,pulse,measured_at,source,device_reported\n"
        "118,76,64,2026-10-03T09:30:00Z,home_monitor,true\n"
    )
    response = client.post(INGEST, json={"channel": "csv", "csv_text": csv_text})
    assert response.status_code == 201
    body = response.get_json()
    assert body["channel"] == "csv"
    assert body["skipped_duplicates"] == []
    kinds = [row["measurement_type"] for row in body["readings"]]
    assert kinds == [
        "systolic_blood_pressure",
        "diastolic_blood_pressure",
        "pulse",
    ]
    systolic, diastolic, pulse = body["readings"]
    assert systolic["value"] == 118
    assert systolic["secondary_value"] == 76
    assert systolic["unit"] == "mmHg"
    assert diastolic["value"] == 76
    assert diastolic["secondary_value"] is None
    assert diastolic["unit"] == "mmHg"
    assert pulse["value"] == 64
    assert pulse["unit"] == "bpm"
    for row in body["readings"]:
        assert row["source"] == "home_monitor"
        assert row["ingest_origin"] == "device"
        assert row["patient_id"] == str(PATIENT_ID)
        assert row["data_quality"] == "valid"
    stored = _readings_at(app, "2026-10-03T09:30:00Z")
    assert {row["measurement_type"] for row in stored} == {
        "systolic_blood_pressure",
        "diastolic_blood_pressure",
        "pulse",
    }
    assert {row["source"] for row in stored} == {"home_monitor"}
    if "ingest_origin" in HealthReading.__table__.columns:
        assert {row["ingest_origin"] for row in stored} == {"device"}


def test_csv_without_device_flag_defaults_to_manual(client):
    csv_text = (
        "systolic,diastolic,pulse,measured_at,source,device_reported\n"
        "119,77,,2026-10-04T09:30:00Z,home_monitor,false\n"
    )
    response = client.post(INGEST, json={"channel": "csv", "csv_text": csv_text})
    assert response.status_code == 201
    readings = response.get_json()["readings"]
    assert [row["measurement_type"] for row in readings] == [
        "systolic_blood_pressure",
        "diastolic_blood_pressure",
    ]
    assert all(row["source"] == "manual" for row in readings)
    assert all(row["ingest_origin"] == "manual" for row in readings)


def test_csv_source_device_maps_to_home_monitor(client):
    csv_text = (
        "systolic,diastolic,pulse,measured_at,source\n"
        "117,75,63,2026-10-06T09:30:00Z,device\n"
    )
    response = client.post(INGEST, json={"channel": "csv", "csv_text": csv_text})
    assert response.status_code == 201
    readings = response.get_json()["readings"]
    assert readings
    assert all(row["source"] == "home_monitor" for row in readings)
    assert all(row["ingest_origin"] == "device" for row in readings)


def test_csv_synthetic_origin(client):
    csv_text = (
        "systolic,diastolic,pulse,measured_at,source,device_reported,synthetic\n"
        "121,79,65,2026-10-05T09:30:00Z,manual,false,true\n"
    )
    response = client.post(INGEST, json={"channel": "csv", "csv_text": csv_text})
    assert response.status_code == 201
    readings = response.get_json()["readings"]
    assert readings
    assert all(row["source"] == "manual" for row in readings)
    assert all(row["ingest_origin"] == "synthetic" for row in readings)


def test_text_csv_body_is_stored(client):
    csv_text = (
        "systolic,diastolic,pulse,measured_at\n"
        "116,74,62,2026-10-07T09:30:00Z\n"
    )
    response = client.post(INGEST, data=csv_text, content_type="text/csv")
    assert response.status_code == 201
    readings = response.get_json()["readings"]
    assert readings[0]["value"] == 116
    assert all(row["source"] == "manual" for row in readings)
    assert all(row["ingest_origin"] == "manual" for row in readings)


def test_bad_timestamp_is_400(client, app):
    before = count_rows(app, HealthReading)
    response = client.post(
        INGEST,
        json={
            "channel": "manual",
            "rows": [
                {
                    "systolic": 120,
                    "diastolic": 80,
                    "pulse": None,
                    "measured_at": "2026-11-15T07:20:00",
                    "source": "manual",
                }
            ],
        },
    )
    error = assert_error(response, 400, "validation_error")
    assert any("timezone" in item for item in error["details"])
    assert count_rows(app, HealthReading) == before


def test_duplicate_seed_reading_is_skipped(client, app):
    before = count_rows(app, HealthReading)
    response = client.post(
        INGEST,
        json={
            "channel": "manual",
            "rows": [
                {
                    "systolic": 126,
                    "diastolic": 80,
                    "pulse": 71,
                    "measured_at": "2026-11-15T08:10:00+05:30",
                    "source": "home_monitor",
                    "unit": "mmHg",
                }
            ],
        },
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["readings"] == []
    assert {item["measurement_type"] for item in body["skipped_duplicates"]} == {
        "systolic_blood_pressure",
        "diastolic_blood_pressure",
        "pulse",
    }
    assert count_rows(app, HealthReading) == before


def test_manual_clinic_origin_is_manual(client):
    response = client.post(
        INGEST,
        json={
            "channel": "manual",
            "rows": [
                {
                    "systolic": 130,
                    "diastolic": 84,
                    "pulse": 70,
                    "measured_at": "2026-10-08T09:30:00Z",
                    "source": "clinic",
                }
            ],
        },
    )
    assert response.status_code == 201
    readings = response.get_json()["readings"]
    assert all(row["source"] == "clinic" for row in readings)
    assert all(row["ingest_origin"] == "manual" for row in readings)


def test_manual_ignores_synthetic_flag(client):
    response = client.post(
        INGEST,
        json={
            "channel": "manual",
            "rows": [
                {
                    "systolic": 128,
                    "diastolic": 82,
                    "pulse": None,
                    "measured_at": "2026-10-09T09:30:00Z",
                    "source": "manual",
                    "synthetic": True,
                }
            ],
        },
    )
    assert response.status_code == 201
    assert all(row["ingest_origin"] == "manual" for row in response.get_json()["readings"])


@pytest.mark.parametrize(
    ("changes", "fragment"),
    [
        ({"systolic": 69}, "between 70 and 250"),
        ({"diastolic": 39}, "between 40 and 150"),
        ({"systolic": 80, "diastolic": 80}, "greater than diastolic"),
        ({"pulse": 20}, "between 30 and 220"),
        ({"source": "device"}, "source must be one of"),
        ({"unit": "kPa"}, "mmHg"),
    ],
)
def test_manual_validation(client, changes, fragment):
    row = {
        "systolic": 120,
        "diastolic": 80,
        "pulse": 70,
        "measured_at": "2026-10-10T09:30:00Z",
        "source": "manual",
        "unit": "mmHg",
    }
    row.update(changes)
    error = assert_error(client.post(INGEST, json={"channel": "manual", "rows": [row]}), 400, "validation_error")
    assert any(fragment in item for item in error["details"])
