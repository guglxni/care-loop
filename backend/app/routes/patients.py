"""Patient profile and chart history routes."""

from urllib.parse import unquote

from flask import Blueprint, jsonify

from app.db import get_db
from app.phones import link_phone, list_phone_links, unlink_phone
from app.services import patient_service
from app.validation import read_json_object

bp = Blueprint("patients", __name__)


@bp.get("/api/v1/patients/<patient_id>")
def get_patient(patient_id: str):
    patient = patient_service.get_patient(get_db(), patient_id)
    return jsonify(patient.to_profile())


@bp.patch("/api/v1/patients/<patient_id>")
def patch_patient(patient_id: str):
    patient = patient_service.update_profile(get_db(), patient_id, read_json_object())
    return jsonify(patient.to_profile())


@bp.get("/api/v1/patients/<patient_id>/history")
def get_history(patient_id: str):
    return jsonify(patient_service.get_history(get_db(), patient_id))


@bp.get("/api/v1/patients/<patient_id>/phone-links")
def get_phone_links(patient_id: str):
    rows = list_phone_links(get_db(), patient_id)
    return jsonify({"phone_links": [row.to_dict() for row in rows]})


@bp.post("/api/v1/patients/<patient_id>/phone-links")
def post_phone_link(patient_id: str):
    row, created = link_phone(get_db(), patient_id, read_json_object())
    return jsonify(row.to_dict()), 201 if created else 200


@bp.delete("/api/v1/patients/<patient_id>/phone-links/<path:phone_e164>")
def delete_phone_link(patient_id: str, phone_e164: str):
    unlink_phone(get_db(), patient_id, unquote(phone_e164))
    return "", 204
