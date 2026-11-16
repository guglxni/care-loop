"""Small assertions shared by the API tests."""


def assert_error(response, status: int, code: str) -> dict:
    assert response.status_code == status
    body = response.get_json()
    assert set(body) == {"error"}
    error = body["error"]
    assert set(error) == {"code", "message", "details"}
    assert error["code"] == code
    assert isinstance(error["message"], str) and error["message"]
    assert isinstance(error["details"], list)
    return error


def count_rows(app, model) -> int:
    from sqlalchemy import func, select

    from app.db import SessionLocal

    with app.app_context():
        session = SessionLocal()
        try:
            value = session.scalar(select(func.count()).select_from(model))
            return int(value or 0)
        finally:
            session.close()


def voice_calls(app) -> list[dict]:
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import VoiceCall

    with app.app_context():
        session = SessionLocal()
        try:
            rows = session.scalars(select(VoiceCall).order_by(VoiceCall.created_at.asc())).all()
            return [row.to_dict() for row in rows]
        finally:
            session.close()
