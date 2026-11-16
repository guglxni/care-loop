"""Runtime settings. Secrets and the database URL come from the environment."""

import os


def normalize_database_url(url: str) -> str:
    """Use psycopg 3 for postgresql:// URLs. Leave sqlite URLs unchanged."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql+psycopg2://"):
        return "postgresql+psycopg://" + url[len("postgresql+psycopg2://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def load_settings() -> dict:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is required. Copy backend/.env.example to backend/.env "
            "or export DATABASE_URL before starting Flask."
        )
    secret = os.environ.get("BOLNA_WEBHOOK_SECRET", "").strip() or None
    flask_env = os.environ.get("FLASK_ENV", "development").strip() or "development"
    return {
        "DATABASE_URL": normalize_database_url(database_url),
        "BOLNA_WEBHOOK_SECRET": secret,
        "FLASK_ENV": flask_env,
    }
