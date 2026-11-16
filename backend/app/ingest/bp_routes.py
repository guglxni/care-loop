"""Blood pressure common-ingest route.

``url_prefix`` is ``/api/v1``. Channel ``bluetooth`` returns 501 and does not
open a device connection.
"""

from flask import Blueprint, jsonify, request

from app.db import get_db
from app.errors import ValidationError
from app.ingest.blood_pressure import NOT_CONNECTED, BluetoothUnavailable, ingest_blood_pressure
from app.validation import read_json_object

bp = Blueprint("bp_routes", __name__, url_prefix="/api/v1")


def read_bp_request() -> dict:
    content_type = (request.content_type or "").split(";", 1)[0].strip().lower()
    if content_type in {"text/csv", "application/csv"}:
        text = request.get_data(as_text=True)
        if not text or not text.strip():
            raise ValidationError("Request validation failed", ["csv_text is required"])
        return {"channel": "csv", "csv_text": text}
    return read_json_object()


@bp.post("/patients/<patient_id>/ingest/blood-pressure")
def post_ingest_blood_pressure(patient_id: str):
    payload = read_bp_request()
    channel = payload.get("channel")
    if isinstance(channel, str) and channel.strip().lower() == "bluetooth":
        return jsonify(NOT_CONNECTED), 501
    try:
        body, status = ingest_blood_pressure(get_db(), patient_id, payload)
    except BluetoothUnavailable:
        return jsonify(NOT_CONNECTED), 501
    return jsonify(body), status
