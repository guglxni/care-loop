"""Nightscout fixture ingest and live-sync failure handling."""

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from app.ingest import nightscout
from app.models import HealthReading
from app.services.seed_service import PATIENT_ID
from tests.helpers import assert_error

MOCK = f"/api/v1/patients/{PATIENT_ID}/ingest/nightscout/mock"
SYNC = f"/api/v1/patients/{PATIENT_ID}/ingest/nightscout/sync"
STATUS = f"/api/v1/patients/{PATIENT_ID}/ingest/status"


def _rows(app, origin: str) -> list:
    table = HealthReading.__table__
    from app.db import SessionLocal

    with app.app_context():
        session = SessionLocal()
        try:
            return list(
                session.execute(
                    select(
                        table.c.value,
                        table.c.unit,
                        table.c.source,
                        table.c.device_id,
                        table.c.data_quality,
                        table.c.support,
                        table.c.ingest_origin,
                        table.c.measured_at,
                    )
                    .where(table.c.ingest_origin == origin)
                    .order_by(table.c.measured_at)
                ).all()
            )
        finally:
            session.close()


def _numbers(rows) -> list[str]:
    return [format(Decimal(str(row.value)), "f").rstrip("0").rstrip(".") for row in rows]


def test_status_before_any_sync_is_not_found(client):
    assert_error(client.get(STATUS), 404, "not_found")


def test_mock_fixture_ingests_synthetic_glucometer_rows(client, app, monkeypatch):
    def fail_open(*_args, **_kwargs):
        raise AssertionError("mock ingest must not call Nightscout")

    monkeypatch.setattr(nightscout, "_urlopen", fail_open)
    response = client.post(MOCK)
    assert response.status_code == 201
    body = response.get_json()
    assert body["connector"] == "nightscout_mock"
    assert body["status"] == "partial"
    assert body["ingest_origin"] == "synthetic"
    assert body["source"] == "glucometer"
    assert body["support"] == "synthetic_nightscout_fixture"
    assert body["inserted_count"] == 3
    assert body["duplicate_count"] == 0
    assert body["skipped_count"] == 5
    assert "not from a live sensor" in body["message"]
    assert "physical CGM" in body["message"]

    rows = _rows(app, "synthetic")
    assert len(rows) == 3
    assert _numbers(rows) == ["142", "7.4", "155"]
    assert [row.unit for row in rows] == ["mg/dL", "mmol/L", "mg/dL"]
    assert {row.source for row in rows} == {"glucometer"}
    assert {row.ingest_origin for row in rows} == {"synthetic"}
    assert {row.support for row in rows} == {"synthetic_nightscout_fixture"}
    assert {row.device_id for row in rows} == {"careloop-demo-nightscout"}
    assert {row.data_quality for row in rows} == {"valid"}
    assert rows[0].measured_at == datetime(2026, 11, 14, 8, 0, tzinfo=timezone.utc)
    assert rows[1].measured_at == datetime(2026, 11, 14, 8, 5, tzinfo=timezone.utc)
    assert rows[2].measured_at == datetime(2026, 11, 14, 8, 20, tzinfo=timezone.utc)
    assert _rows(app, "device") == []

    status = client.get(STATUS)
    assert status.status_code == 200
    latest = status.get_json()
    assert latest["connector"] == "nightscout_mock"
    assert latest["status"] == "partial"
    assert latest["inserted_count"] == 3
    assert "ingest_origin" not in latest
    assert "source" not in latest


def test_incomplete_fixture_entries_are_not_stored(client, app):
    client.post(MOCK)
    stored = {value for value in _numbers(_rows(app, "synthetic"))}
    assert stored.isdisjoint({"118", "166", "144", "99"})


def test_second_mock_post_skips_duplicates(client, app):
    first = client.post(MOCK)
    assert first.status_code == 201
    second = client.post(MOCK)
    assert second.status_code == 201
    body = second.get_json()
    assert body["inserted_count"] == 0
    assert body["duplicate_count"] == 3
    assert body["skipped_count"] == 5
    assert body["ingest_origin"] == "synthetic"
    assert body["source"] == "glucometer"
    assert len(_rows(app, "synthetic")) == 3


def test_dedupe_index_rejects_a_second_identical_row(client, app):
    assert client.post(MOCK).status_code == 201
    table = HealthReading.__table__
    from app.db import SessionLocal

    with app.app_context():
        session = SessionLocal()
        try:
            existing = session.execute(
                select(table).where(table.c.ingest_origin == "synthetic").limit(1)
            ).mappings().one()
            payload = dict(existing)
            payload["id"] = uuid.uuid4()
            with pytest.raises(IntegrityError):
                session.execute(insert(table).values(**payload))
                session.commit()
        finally:
            session.rollback()
            session.close()


def test_missing_nightscout_env_returns_unavailable(client, app, monkeypatch):
    monkeypatch.delenv("NIGHTSCOUT_URL", raising=False)
    monkeypatch.delenv("NIGHTSCOUT_API_TOKEN", raising=False)

    def fail_open(*_args, **_kwargs):
        raise AssertionError("missing credentials must not call Nightscout")

    monkeypatch.setattr(nightscout, "_urlopen", fail_open)
    response = client.post(SYNC)
    error = assert_error(response, 503, "unavailable")
    assert "NIGHTSCOUT_URL" in error["message"]
    assert "Traceback" not in response.get_data(as_text=True)
    status = client.get(STATUS)
    assert status.status_code == 200
    body = status.get_json()
    assert body["connector"] == "nightscout"
    assert body["status"] == "unavailable"
    assert body["inserted_count"] == 0
    assert _rows(app, "device") == []


@pytest.mark.parametrize("present", ["url", "token"])
def test_partial_nightscout_env_returns_unavailable(client, monkeypatch, present):
    monkeypatch.delenv("NIGHTSCOUT_URL", raising=False)
    monkeypatch.delenv("NIGHTSCOUT_API_TOKEN", raising=False)
    if present == "url":
        monkeypatch.setenv("NIGHTSCOUT_URL", "https://nightscout.example")
    else:
        monkeypatch.setenv("NIGHTSCOUT_API_TOKEN", "hashed-token-not-real")
    response = client.post(SYNC)
    assert_error(response, 503, "unavailable")
    assert client.get(STATUS).get_json()["status"] == "unavailable"


def test_nightscout_http_failure_returns_unavailable(client, app, monkeypatch):
    monkeypatch.setenv("NIGHTSCOUT_URL", "https://nightscout.example")
    monkeypatch.setenv("NIGHTSCOUT_API_TOKEN", "hashed-token-not-real")

    def fail_open(*_args, **_kwargs):
        raise nightscout.urllib.error.URLError("down")

    monkeypatch.setattr(nightscout, "_urlopen", fail_open)
    response = client.post(SYNC)
    error = assert_error(response, 503, "unavailable")
    text = response.get_data(as_text=True)
    assert "Traceback" not in text
    assert "hashed-token-not-real" not in text
    assert error["code"] == "unavailable"
    assert client.get(STATUS).get_json()["status"] == "unavailable"
    assert _rows(app, "device") == []


def test_live_sync_labels_device_cgm_and_sends_api_secret(client, app, monkeypatch):
    monkeypatch.setenv("NIGHTSCOUT_URL", "https://nightscout.example/care")
    monkeypatch.setenv("NIGHTSCOUT_API_TOKEN", "hashed-token-not-real")
    seen = []

    class _Body:
        def __init__(self, payload: bytes):
            self._payload = payload

        def read(self, _limit=-1):
            return self._payload

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def fake_open(request, timeout):
        headers = {name.lower(): value for name, value in request.header_items()}
        seen.append({"url": request.full_url, "secret": headers.get("api-secret"), "timeout": timeout})
        if request.full_url.endswith("/api/v1/status.json"):
            return _Body(b'{"settings":{"units":"mmol"}}')
        return _Body(
            json.dumps(
                [
                    {
                        "type": "sgv",
                        "sgv": 6.5,
                        "dateString": "2026-11-14T09:00:00.000Z",
                        "device": "demo-nightscout-site",
                        "direction": "Flat",
                    },
                    {
                        "type": "sgv",
                        "sgv": 6.5,
                        "dateString": "2026-11-14T09:00:00.000Z",
                        "device": "demo-nightscout-site",
                        "direction": "Flat",
                    },
                    {
                        "type": "mbg",
                        "sgv": 90,
                        "dateString": "2026-11-14T09:05:00.000Z",
                    },
                ]
            ).encode()
        )

    monkeypatch.setattr(nightscout, "_urlopen", fake_open)
    response = client.post(SYNC)
    assert response.status_code == 201
    body = response.get_json()
    assert body["status"] == "partial"
    assert body["ingest_origin"] == "device"
    assert body["source"] == "cgm"
    assert body["connector"] == "nightscout"
    assert body["inserted_count"] == 1
    assert body["duplicate_count"] == 1
    assert body["skipped_count"] == 1
    assert "support" not in body
    assert "physical CGM transmitter is not connected" in body["message"]
    urls = {item["url"] for item in seen}
    assert "https://nightscout.example/care/api/v1/entries.json?count=288" in urls
    assert "https://nightscout.example/care/api/v1/status.json" in urls
    assert {item["secret"] for item in seen} == {"hashed-token-not-real"}
    assert {item["timeout"] for item in seen} == {10}

    rows = _rows(app, "device")
    assert len(rows) == 1
    row = rows[0]
    assert Decimal(str(row.value)) == Decimal("6.5")
    assert row.unit == "mmol/L"
    assert row.source == "cgm"
    assert row.ingest_origin == "device"
    assert row.support == "Flat"
    assert row.device_id == "demo-nightscout-site"
    assert row.data_quality == "valid"
    assert row.measured_at == datetime(2026, 11, 14, 9, 0, tzinfo=timezone.utc)
