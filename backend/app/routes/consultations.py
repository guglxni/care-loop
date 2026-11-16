"""Consultation routes."""

from flask import Blueprint, jsonify

from app.db import get_db
from app.services import consultation_service
from app.validation import read_json_object

bp = Blueprint("consultations", __name__)


@bp.get("/api/v1/patients/<patient_id>/consultations/upcoming")
def upcoming(patient_id: str):
    row = consultation_service.next_scheduled(get_db(), patient_id)
    return jsonify({"consultation": None if row is None else row.to_dict()})


@bp.post("/api/v1/consultations/<consultation_id>")
def update_consultation(consultation_id: str):
    row = consultation_service.update_consultation(get_db(), consultation_id, read_json_object())
    return jsonify(row.to_dict())
