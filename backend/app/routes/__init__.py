"""Route registration."""

from flask import Flask


def register_blueprints(app: Flask) -> None:
    from app.knowledge import bp as knowledge_bp
    from app.routes.bolna import bp as bolna_bp
    from app.routes.care_events import bp as care_events_bp
    from app.routes.consultations import bp as consultations_bp
    from app.routes.medications import bp as medications_bp
    from app.routes.patients import bp as patients_bp
    from app.routes.readings import bp as readings_bp

    app.register_blueprint(patients_bp)
    app.register_blueprint(knowledge_bp)
    app.register_blueprint(readings_bp)
    app.register_blueprint(medications_bp)
    app.register_blueprint(consultations_bp)
    app.register_blueprint(care_events_bp)
    app.register_blueprint(bolna_bp)
