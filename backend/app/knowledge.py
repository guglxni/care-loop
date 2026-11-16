"""Patient knowledge document, built from that chart only.

GET returns markdown. POST /refresh stores last_built_at for the same path.
This module does not call an external voice or knowledge service.
"""

from flask import Blueprint, Response, jsonify

from app.db import get_db
from app.services.knowledge_service import build_document, refresh_link

bp = Blueprint("knowledge", __name__)


@bp.get("/api/v1/patients/<patient_id>/knowledge")
def get_knowledge(patient_id: str):
    document = build_document(get_db(), patient_id)
    response = Response(document, mimetype="text/markdown")
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.post("/api/v1/patients/<patient_id>/knowledge/refresh")
def refresh_knowledge(patient_id: str):
    row = refresh_link(get_db(), patient_id)
    return jsonify(row.to_dict())
