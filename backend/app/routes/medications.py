"""Medication schedule and adherence routes."""

from flask import Blueprint, jsonify

from app.db import get_db
from app.services import medication_service
from app.validation import read_json_object

bp = Blueprint("medications", __name__)


@bp.get("/api/v1/patients/<patient_id>/medications")
def get_medications(patient_id: str):
    rows = medication_service.list_active_medications(get_db(), patient_id)
    return jsonify({"medications": [row.to_dict() for row in rows]})


@bp.post("/api/v1/patients/<patient_id>/adherence")
def post_adherence(patient_id: str):
    row = medication_service.record_adherence(get_db(), patient_id, read_json_object())
    return jsonify(row.to_dict()), 201
