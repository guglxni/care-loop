"""Bolna context, reminder, call outcome, and webhook routes."""

import hmac

from flask import Blueprint, current_app, jsonify, request

from app.db import get_db
from app.errors import UnauthorizedError, ValidationError
from app.services import context_service, reminder_service, voice_service
from app.validation import read_json_object

bp = Blueprint("bolna", __name__)


@bp.get("/api/v1/patients/<patient_id>/bolna/context")
def bolna_context(patient_id: str):
    packet = context_service.get_bolna_context(
        get_db(),
        patient_id,
        request.args.get("purpose"),
        request.args.get("to_number") or request.args.get("to"),
    )
    return jsonify(packet)


@bp.post("/api/v1/patients/<patient_id>/bolna/remind")
def remind(patient_id: str):
    result = reminder_service.queue_reminder(get_db(), patient_id, _optional_object())
    return jsonify(result), 201


@bp.post("/api/v1/patients/<patient_id>/bolna/call-outcomes")
def call_outcomes(patient_id: str):
    row, created = voice_service.record_call_outcome(get_db(), patient_id, read_json_object())
    return jsonify(row.to_dict()), 201 if created else 200


@bp.post("/api/v1/bolna/webhook")
def webhook():
    _authorize_webhook()
    result = voice_service.accept_webhook(get_db(), read_json_object())
    return jsonify(result.body), result.status


def _optional_object() -> dict:
    if not request.data and not request.form:
        return {}
    body = request.get_json(silent=True)
    if body is None:
        if request.data:
            raise ValidationError("Request validation failed", ["body must be a JSON object"])
        return {}
    if not isinstance(body, dict):
        raise ValidationError("Request validation failed", ["body must be a JSON object"])
    return body


def _authorize_webhook() -> None:
    secret = current_app.config.get("BOLNA_WEBHOOK_SECRET")
    if isinstance(secret, str):
        secret = secret.strip() or None
    if not secret:
        if current_app.config.get("FLASK_ENV") == "production":
            raise UnauthorizedError("BOLNA_WEBHOOK_SECRET must be set in production")
        return
    provided = request.headers.get("X-Care-Loop-Secret", "")
    if not hmac.compare_digest(provided.encode("utf-8"), secret.encode("utf-8")):
        raise UnauthorizedError("Webhook secret does not match")
