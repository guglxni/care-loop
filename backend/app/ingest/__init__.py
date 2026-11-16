"""External ingest registration.

Nightscout is always registered. The document, blood-pressure, and forecast
modules are registered when they import. ImportError means that sibling file
is not present yet and is ignored.
"""

import importlib

from flask import Flask


def register_ingest_blueprints(app: Flask) -> None:
    """Register Nightscout and any sibling ingest blueprints that are present."""
    from app.ingest.models import ensure_ingest_schema
    from app.ingest.nightscout_routes import bp as nightscout_bp

    ensure_ingest_schema()
    app.register_blueprint(nightscout_bp)
    for module_name in (
        "app.ingest.document_routes",
        "app.ingest.bp_routes",
        "app.ingest.forecast_routes",
    ):
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        app.register_blueprint(module.bp)
