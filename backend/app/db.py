"""SQLAlchemy engine and session factory."""

import sqlite3
from contextlib import contextmanager

from flask import g
from sqlalchemy import DateTime, Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool
from sqlalchemy.types import TypeDecorator

class Base(DeclarativeBase):
    pass


class UTCDateTime(TypeDecorator):
    """Persist timezone-aware datetimes as UTC. SQLite stores them as naive UTC."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("naive datetime cannot be stored")
        utc_value = value.astimezone(timezone_utc())
        if dialect.name == "sqlite":
            return utc_value.replace(tzinfo=None)
        return utc_value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone_utc())
        return value.astimezone(timezone_utc())


def timezone_utc():
    from datetime import timezone

    return timezone.utc


engine: Engine | None = None
SessionLocal = sessionmaker(autoflush=False, autocommit=False, expire_on_commit=False)


@event.listens_for(Engine, "connect")
def _sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    module = type(dbapi_connection).__module__
    if isinstance(dbapi_connection, sqlite3.Connection) or module.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def init_engine(database_url: str) -> Engine:
    global engine
    if engine is not None:
        engine.dispose()
        engine = None
    options: dict = {}
    if database_url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
        # In-memory SQLite is empty on every new connection, so it keeps one
        # connection. A file database must not share that connection across
        # the threaded dev server; that path segfaults in SQLAlchemy's row
        # processors when /demo loads the chart more than once at a time.
        memory = ":memory:" in database_url or "mode=memory" in database_url
        options["poolclass"] = StaticPool if memory else NullPool
    else:
        options["pool_pre_ping"] = True
    engine = create_engine(database_url, **options)
    SessionLocal.configure(bind=engine)
    return engine


def get_engine() -> Engine:
    if engine is None:
        raise RuntimeError("Database engine is not initialized")
    return engine


def get_db() -> Session:
    session = g.get("db_session")
    if session is None:
        session = SessionLocal()
        g.db_session = session
    return session


def close_db(_exc: BaseException | None = None) -> None:
    session = g.pop("db_session", None)
    if session is not None:
        if _exc is not None:
            session.rollback()
        session.close()


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
