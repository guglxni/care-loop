"""Glucose and blood pressure routes."""

from flask import Blueprint, jsonify

from app.db import get_db
from app.services import reading_service
from app.validation import read_json_object

bp = Blueprint("readings", __name__)


@bp.post("/api/v1/patients/<patient_id>/readings/glucose")
def post_glucose(patient_id: str):
    row = reading_service.record_glucose(get_db(), patient_id, read_json_object())
    return jsonify(row.to_dict()), 201


@bp.post("/api/v1/patients/<patient_id>/readings/blood-pressure")
def post_blood_pressure(patient_id: str):
    rows = reading_service.record_blood_pressure(get_db(), patient_id, read_json_object())
    return jsonify({"readings": [row.to_dict() for row in rows]}), 201
