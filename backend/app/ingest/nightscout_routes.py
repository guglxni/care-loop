"""Nightscout mock and live ingest routes."""

from flask import Blueprint, jsonify

from app.db import get_db
from app.errors import error_payload
from app.ingest.nightscout import ingest_fixture, latest_run, sync_live

bp = Blueprint("ingest_nightscout", __name__)


@bp.post("/api/v1/patients/<patient_id>/ingest/nightscout/mock")
def post_nightscout_mock(patient_id: str):
    return jsonify(ingest_fixture(get_db(), patient_id)), 201


@bp.post("/api/v1/patients/<patient_id>/ingest/nightscout/sync")
def post_nightscout_sync(patient_id: str):
    result = sync_live(get_db(), patient_id)
    if result.http_status == 503:
        return jsonify(error_payload("unavailable", result.message, [])), 503
    return jsonify(result.body), result.http_status


@bp.get("/api/v1/patients/<patient_id>/ingest/status")
def get_ingest_status(patient_id: str):
    return jsonify(latest_run(get_db(), patient_id).to_dict())
