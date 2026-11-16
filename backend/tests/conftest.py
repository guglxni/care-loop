"""Pytest fixtures. SQLite memory is for tests only."""

import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["FLASK_ENV"] = "development"
os.environ["BOLNA_WEBHOOK_SECRET"] = ""

import pytest

from app import create_app
from app.db import Base, SessionLocal, get_engine
from app.services.seed_service import seed


@pytest.fixture
def app():
    application = create_app()
    application.config["TESTING"] = True
    application.config["PROPAGATE_EXCEPTIONS"] = False
    with application.app_context():
        Base.metadata.create_all(get_engine())
        session = SessionLocal()
        try:
            seed(session)
        finally:
            session.close()
    yield application
    with application.app_context():
        Base.metadata.drop_all(get_engine())


@pytest.fixture
def client(app):
    return app.test_client()
