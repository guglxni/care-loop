"""Synthetic Ravi Sharma demo routes.

GET and reset do not dial. POST /api/v1/demo/calls builds chart context first
and calls Bolna only through start_outbound_call, which tests replace. If the
context cannot be built, the route returns 409 and does not dial. GET status
reads the stored voice-call row and does not dial.
"""

from flask import Blueprint, jsonify

from app.db import get_db
from app.demo.calls import demo_call_status, start_demo_call
from app.demo.ravi import load_ravi, reset_ravi
from app.validation import read_json_object

bp = Blueprint("demo_ravi", __name__)


@bp.get("/api/v1/demo/ravi")
def get_ravi():
    return jsonify(load_ravi(get_db()))


@bp.post("/api/v1/demo/ravi/reset")
def reset_ravi_route():
    return jsonify(reset_ravi(get_db()))


@bp.post("/api/v1/demo/calls")
def post_demo_call():
    result = start_demo_call(get_db(), read_json_object())
    return jsonify(result), 201


@bp.get("/api/v1/demo/calls/<execution_id>")
def get_demo_call(execution_id: str):
    return jsonify(demo_call_status(get_db(), execution_id))
