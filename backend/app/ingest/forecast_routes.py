"""Glucose forecast routes. Register bp on the Flask app to expose them."""

from flask import Blueprint, jsonify

from app.db import get_db
from app.ingest.forecast import forecast_for_patient
from app.ingest.glucofm import glucofm_for_patient, repositories

bp = Blueprint("glucose_forecast", __name__, url_prefix="/api/v1")


@bp.get("/patients/<patient_id>/ingest/glucose/forecast")
def get_glucose_forecast(patient_id: str):
    session = get_db()
    body = forecast_for_patient(session, patient_id)
    body["glucofm"] = glucofm_for_patient(session, patient_id)
    return jsonify(body)


@bp.get("/patients/<patient_id>/ingest/glucose/representation")
def get_glucose_representation(patient_id: str):
    session = get_db()
    return jsonify(
        {
            "timesfm": forecast_for_patient(session, patient_id),
            "glucofm": glucofm_for_patient(session, patient_id),
            "repositories": repositories(),
        }
    )
