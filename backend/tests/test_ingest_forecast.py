"""Glucose forecast estimates stay out of the reading table."""

import os
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from app.ingest import forecast, glucofm
from app.models import HealthReading, Patient
from tests.helpers import assert_error, count_rows

UNKNOWN = "99999999-9999-4999-8999-999999999999"


@pytest.fixture
def client(app):
    from app.ingest.forecast_routes import bp

    if bp.name not in app.blueprints:
        app.register_blueprint(bp)
    return app.test_client()


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


def _patient() -> Patient:
    return Patient(
        id=uuid.uuid4(),
        preferred_name="Forecast Chart",
        date_of_birth=date(1975, 3, 2),
        preferred_language="en",
        contact_number="+910000000101",
        medical_history="",
        allergies=[],
        emergency_contact={},
    )


def _glucose(patient_id, measured_at: datetime, value: float, unit: str = "mg/dL") -> HealthReading:
    return HealthReading(
        patient_id=patient_id,
        measurement_type="blood_glucose",
        value=value,
        secondary_value=None,
        unit=unit,
        measurement_context="fasting",
        measured_at=measured_at,
        source="glucometer",
        device_id=None,
        data_quality="valid",
        support=None,
    )


def _forecast_path(patient_id) -> str:
    return f"/api/v1/patients/{patient_id}/ingest/glucose/forecast"


def _representation_path(patient_id) -> str:
    return f"/api/v1/patients/{patient_id}/ingest/glucose/representation"


def test_patient_with_no_readings_is_unavailable(client, app):
    patient = _patient()
    _insert(app, patient)
    before = count_rows(app, HealthReading)

    response = client.get(_forecast_path(patient.id))

    assert response.status_code == 200
    body = response.get_json()
    assert body["model"] == "timesfm"
    assert body["available"] is False
    assert body["origin"] == "unavailable"
    assert body["estimates"] == []
    assert body["disclaimer"] == forecast.DISCLAIMER
    assert "Not a glucose measurement" in body["disclaimer"]
    assert "not medical advice" in body["disclaimer"].lower()
    assert count_rows(app, HealthReading) == before
    payload = response.get_data(as_text=True)
    assert "ingest_origin" not in payload
    assert "cgm" not in payload.lower()


def test_fewer_than_six_readings_are_not_filled_in(client, app):
    patient = _patient()
    start = datetime(2026, 11, 10, 8, 0, tzinfo=timezone.utc)
    readings = [
        _glucose(patient.id, start + timedelta(minutes=15 * index), 100 + index)
        for index in range(5)
    ]
    _insert(app, patient, *readings)
    before = count_rows(app, HealthReading)

    response = client.get(_forecast_path(patient.id))

    body = response.get_json()
    assert body["available"] is False
    assert body["estimates"] == []
    assert body["disclaimer"] == forecast.DISCLAIMER
    assert "not medical advice" in body["disclaimer"].lower()
    assert count_rows(app, HealthReading) == before


def test_six_readings_stay_unavailable_without_a_local_model(client, app):
    patient = _patient()
    start = datetime(2026, 11, 12, 7, 0, tzinfo=timezone.utc)
    readings = [
        _glucose(patient.id, start + timedelta(minutes=15 * index), 110 + index)
        for index in range(6)
    ]
    _insert(app, patient, *readings)
    before = count_rows(app, HealthReading)
    status = forecast.runtime_status()

    response = client.get(_forecast_path(patient.id))

    assert response.status_code == 200
    body = response.get_json()
    assert body["model"] == "timesfm"
    assert "Not a glucose measurement" in body["disclaimer"]
    assert "not medical advice" in body["disclaimer"].lower()
    assert count_rows(app, HealthReading) == before
    payload = response.get_data(as_text=True)
    assert "ingest_origin" not in payload
    assert '"source"' not in payload
    if status != "ready" or body["available"] is False:
        assert body["available"] is False
        assert body["origin"] == "unavailable"
        assert body["estimates"] == []
        if status == "missing":
            assert forecast.LIBRARY_NOTE in body["disclaimer"]
        elif status == "weights":
            assert forecast.WEIGHTS_NOTE in body["disclaimer"]
    else:
        assert body["origin"] == "model"
        assert body["disclaimer"] == forecast.DISCLAIMER
        assert body["estimates"]
        for estimate in body["estimates"]:
            assert set(estimate) == {"measured_at", "value", "unit"}
            assert estimate["unit"] == "mg/dL"


def test_history_keeps_the_latest_thirty_six_in_order(app):
    patient = _patient()
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    readings = [
        _glucose(patient.id, start + timedelta(hours=index), 80 + index) for index in range(40)
    ]
    readings.append(
        HealthReading(
            patient_id=patient.id,
            measurement_type="systolic_blood_pressure",
            value=120,
            secondary_value=80,
            unit="mmHg",
            measurement_context=None,
            measured_at=start + timedelta(hours=50),
            source="home_monitor",
            device_id=None,
            data_quality="valid",
            support=None,
        )
    )
    _insert(app, patient, *reversed(readings))

    from app.db import SessionLocal

    with app.app_context():
        session = SessionLocal()
        try:
            series = forecast.load_glucose_series(session, patient.id)
        finally:
            session.close()

    assert [value for _moment, value in series] == list(range(84, 120))
    assert series[0][0] < series[-1][0]


def test_unknown_patient_is_not_found(client):
    response = client.get(_forecast_path(UNKNOWN))
    assert_error(response, 404, "not_found")
    missing = client.get(_representation_path(UNKNOWN))
    assert_error(missing, 404, "not_found")


def test_glucofm_companion_skips_network_and_inserts_nothing(client, app, monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.delenv("GLUCOFM_ENCODER_PATH", raising=False)
    monkeypatch.setattr(glucofm, "_encoder_file", lambda: None)

    def fail_download(*_args, **_kwargs):
        raise AssertionError("network")

    monkeypatch.setattr("urllib.request.urlopen", fail_download)
    try:
        import huggingface_hub
    except ImportError:
        huggingface_hub = None
    if huggingface_hub is not None:
        monkeypatch.setattr(huggingface_hub, "hf_hub_download", fail_download, raising=False)
        monkeypatch.setattr(huggingface_hub, "snapshot_download", fail_download, raising=False)

    patient = _patient()
    _insert(app, patient)
    before = count_rows(app, HealthReading)

    response = client.get(_forecast_path(patient.id))

    assert response.status_code == 200
    body = response.get_json()
    companion = body["glucofm"]
    assert companion["model"] == glucofm.MODEL_NAME
    assert "unofficial reconstruction" in companion["model"]
    assert companion["available"] is False
    assert companion["reason"] == "unofficial GlucoFM encoder not installed"
    assert companion["source_url"] == "https://huggingface.co/eugenehp/glucofm-encoder"
    assert companion["disclaimer"] == glucofm.DISCLAIMER
    assert "Not Google's GlucoFM checkpoint" in companion["disclaimer"]
    assert "Not a glucose measurement and not medical advice." in companion["disclaimer"]
    assert companion["estimates"] == []
    assert companion["embedding_metadata"]["dimension"] == 128
    assert companion["embedding_metadata"]["source_repo"] == companion["source_url"]
    assert companion["embedding_metadata"]["computed"] is False
    assert companion["trajectory_forecast"]["available"] is False
    assert companion["trajectory_forecast"]["model"] == glucofm.MODEL_NAME
    assert companion["trajectory_forecast"]["estimates"] == []
    assert companion["trajectory_forecast"]["requires"] == [
        "meal_nutrition",
        "fasting_glucose",
        "bmi",
        "diabetes_status",
    ]
    assert "demo does not have them" in companion["trajectory_forecast"]["reason"]
    assert body["model"] == "timesfm"
    assert count_rows(app, HealthReading) == before
    payload = response.get_data(as_text=True)
    assert "ingest_origin" not in payload
    assert "cgm" not in payload.lower()
    assert "opencgm" not in payload.lower()


def test_glucofm_embedding_is_not_a_glucose_forecast(client, app, monkeypatch):
    monkeypatch.setattr(glucofm, "_encoder_installed", lambda: True)
    monkeypatch.setattr(glucofm, "_embedding_dimension", lambda *_args, **_kwargs: 128)
    patient = _patient()
    start = datetime(2026, 11, 12, 7, 0, tzinfo=timezone.utc)
    readings = [
        _glucose(patient.id, start + timedelta(minutes=15 * index), 110 + index)
        for index in range(6)
    ]
    _insert(app, patient, *readings)
    before = count_rows(app, HealthReading)

    response = client.get(_forecast_path(patient.id))

    assert response.status_code == 200
    companion = response.get_json()["glucofm"]
    assert companion["available"] is True
    assert companion["model"] == glucofm.MODEL_NAME
    assert companion["disclaimer"] == glucofm.DISCLAIMER
    assert companion["kind"] == "embedding"
    assert companion["estimates"] == []
    assert companion["observed_points"] == 6
    assert companion["embedding_metadata"] == {
        "dimension": 128,
        "source_repo": glucofm.SOURCE_URL,
        "computed": True,
    }
    assert companion["trajectory_forecast"]["available"] is False
    assert companion["trajectory_forecast"]["estimates"] == []
    encoded = response.get_data(as_text=True)
    glucofm_text = encoded[encoded.index('"glucofm"') :]
    for index in range(6):
        assert str(110 + index) not in glucofm_text
    assert "mg/dL" not in glucofm_text
    assert "ingest_origin" not in encoded
    assert count_rows(app, HealthReading) == before

    series = [(start + timedelta(minutes=15 * index), float(110 + index)) for index in range(6)]
    values, mask, _circadian = glucofm._build_window(series)
    assert sum(mask) == 6
    assert [values[index] for index, flag in enumerate(mask) if flag] == [
        float(110 + offset) for offset in range(6)
    ]
    empty_slots = [values[index] for index, flag in enumerate(mask) if flag == 0.0]
    assert len(empty_slots) == glucofm.GRID_POINTS - 6
    assert set(empty_slots) == {0.0}


def test_representation_lists_timesfm_and_unofficial_encoder(client, app, monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setattr(glucofm, "_encoder_file", lambda: None)
    patient = _patient()
    _insert(app, patient)
    before = count_rows(app, HealthReading)

    response = client.get(_representation_path(patient.id))

    assert response.status_code == 200
    body = response.get_json()
    assert body["timesfm"]["model"] == "timesfm"
    assert body["glucofm"]["model"] == glucofm.MODEL_NAME
    assert body["glucofm"]["disclaimer"] == glucofm.DISCLAIMER
    assert body["glucofm"]["reason"] == glucofm.NOT_INSTALLED
    assert body["glucofm"]["estimates"] == []
    urls = [item["url"] for item in body["repositories"]]
    assert urls == [
        "https://huggingface.co/eugenehp/glucofm-encoder",
        "https://github.com/sfourdrinier/opencgm",
        "https://github.com/ViSaReVe/glucofm-replication",
        "https://github.com/eugenehp/glucofm-rs",
        "https://huggingface.co/datasets/glucofmbench/GlucoFM-Bench",
        "https://arxiv.org/abs/2605.30865",
        "https://research.google/blog/glucofm-foundation-model-for-continuous-glucose-monitoring",
    ]
    assert body["repositories"][0]["integrated"] is True
    assert all(item["integrated"] is False for item in body["repositories"][1:])
    assert count_rows(app, HealthReading) == before
    payload = response.get_data(as_text=True)
    assert "ingest_origin" not in payload
    assert '"device"' not in payload


def test_encoder_lookup_does_not_download(monkeypatch):
    monkeypatch.delenv("GLUCOFM_ENCODER_PATH", raising=False)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")

    def fail_download(*_args, **_kwargs):
        raise AssertionError("network")

    monkeypatch.setattr("urllib.request.urlopen", fail_download)
    try:
        import huggingface_hub
    except ImportError:
        huggingface_hub = None
    if huggingface_hub is not None:
        monkeypatch.setattr(huggingface_hub, "hf_hub_download", fail_download, raising=False)
        monkeypatch.setattr(huggingface_hub, "snapshot_download", fail_download, raising=False)

    found = glucofm._encoder_file()
    assert found is None or os.path.isfile(found)
