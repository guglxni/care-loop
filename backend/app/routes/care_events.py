"""Care event routes. Responses repeat stored fields and do not add advice."""

from flask import Blueprint, jsonify

from app.db import get_db
from app.services import care_event_service
from app.validation import read_json_object

bp = Blueprint("care_events", __name__)


@bp.get("/api/v1/patients/<patient_id>/care-events")
def get_care_events(patient_id: str):
    rows = care_event_service.list_care_events(get_db(), patient_id)
    return jsonify({"care_events": [row.to_dict() for row in rows]})


@bp.post("/api/v1/patients/<patient_id>/care-events")
def post_care_event(patient_id: str):
    row = care_event_service.create_care_event(get_db(), patient_id, read_json_object())
    return jsonify(row.to_dict()), 201
