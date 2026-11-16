"""Care Loop Flask application."""

import click
from dotenv import load_dotenv
from flask import Flask

from app.config import load_settings
from app.db import close_db, init_engine, session_scope
from app.errors import register_error_handlers
from app.ingest import register_ingest_blueprints
from app.routes import register_blueprints


def create_app() -> Flask:
    load_dotenv(override=False)
    app = Flask(__name__)
    settings = load_settings()
    app.config.update(settings)
    init_engine(settings["DATABASE_URL"])
    register_error_handlers(app)
    register_blueprints(app)
    register_ingest_blueprints(app)
    _register_demo_ravi(app)
    app.teardown_appcontext(close_db)
    _register_commands(app)
    return app


def _register_demo_ravi(app: Flask) -> None:
    """Synthetic Ravi Sharma chart. Does not replace the other blueprints."""
    from app.demo.routes import bp as demo_ravi_bp

    app.register_blueprint(demo_ravi_bp)


def _register_commands(app: Flask) -> None:
    @app.cli.command("seed")
    def seed_command() -> None:
        """Insert the synthetic development chart. Apply database migrations first."""
        from app.services.seed_service import seed

        with session_scope() as session:
            created = seed(session)
        click.echo(
            "Inserted the synthetic Meera Iyer chart."
            if created
            else "Synthetic chart already present."
        )
