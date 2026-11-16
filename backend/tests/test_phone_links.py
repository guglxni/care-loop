"""Phone links resolve inbound and outbound numbers onto one chart."""

import uuid
from datetime import date
from urllib.parse import quote

from sqlalchemy import delete

from app.db import SessionLocal
from app.demo.ravi import PARTICIPANT_PHONE, PATIENT_ID as RAVI_ID
from app.models import HealthReading, Patient
from app.phones import CARELOOP_LINE, PatientPhoneLink, resolve_patient_id_by_phone
from app.services.bolna_outbound import FROM_NUMBER
from app.services.seed_service import PATIENT_ID, SEEDED_HEALTH_READINGS, seed
from tests.helpers import assert_error, count_rows, voice_calls

PROFILE = f"/api/v1/patients/{PATIENT_ID}"
LINKS = f"{PROFILE}/phone-links"
RAVI_LINKS = f"/api/v1/patients/{RAVI_ID}/phone-links"
WEBHOOK = "/api/v1/bolna/webhook"
OTHER_ID = uuid.UUID("88888888-8888-4888-8888-888888888888")


def test_seed_keeps_meera_chart_contact_and_links_the_mobile_to_ravi(client, app):
    profile = client.get(PROFILE).get_json()
    assert profile["preferred_name"] == "Meera Iyer"
    assert profile["contact_number"] == "+919840011223"
    assert client.get(LINKS).get_json()["phone_links"] == []
    assert count_rows(app, HealthReading) == SEEDED_HEALTH_READINGS
    assert CARELOOP_LINE == FROM_NUMBER

    assert client.get("/api/v1/demo/ravi").status_code == 200
    body = client.get(RAVI_LINKS).get_json()
    assert [row["phone_e164"] for row in body["phone_links"]] == [PARTICIPANT_PHONE]
    assert body["phone_links"][0]["label"] == "mobile"
    assert body["phone_links"][0]["patient_id"] == str(RAVI_ID)
    assert client.get(LINKS).get_json()["phone_links"] == []
    assert client.get(PROFILE).get_json()["contact_number"] == "+919840011223"


def test_reseed_restores_the_mobile_on_ravi_without_dropping_clinical_rows(client, app):
    assert client.get("/api/v1/demo/ravi").status_code == 200
    before = count_rows(app, HealthReading)
    with app.app_context():
        session = SessionLocal()
        try:
            session.execute(delete(PatientPhoneLink))
            session.commit()
            assert seed(session) is False
            assert seed(session) is False
        finally:
            session.close()
    assert client.get(PROFILE).get_json()["contact_number"] == "+919840011223"
    assert client.get(LINKS).get_json()["phone_links"] == []
    phones = client.get(RAVI_LINKS).get_json()["phone_links"]
    assert [row["phone_e164"] for row in phones] == [PARTICIPANT_PHONE]
    assert phones[0]["label"] == "mobile"
    assert phones[0]["patient_id"] == str(RAVI_ID)
    assert count_rows(app, HealthReading) == before


def test_resolve_matches_exact_e164_after_stripping_spaces(client, app):
    assert client.get("/api/v1/demo/ravi").status_code == 200
    with app.app_context():
        session = SessionLocal()
        try:
            assert resolve_patient_id_by_phone(session, "+91 93725 01954") == RAVI_ID
            assert resolve_patient_id_by_phone(session, PARTICIPANT_PHONE) == RAVI_ID
            assert resolve_patient_id_by_phone(session, "+1 423 583 8428") is None
            assert resolve_patient_id_by_phone(session, "+15555550999") is None
            assert resolve_patient_id_by_phone(session, "919372501954") is None
            assert resolve_patient_id_by_phone(session, "+919840011223") is None
        finally:
            session.close()


def test_phone_link_create_list_and_conflict(client, app):
    assert client.get("/api/v1/demo/ravi").status_code == 200
    _insert_other(app)
    other_links = f"/api/v1/patients/{OTHER_ID}/phone-links"
    created = client.post(
        LINKS,
        json={"phone_e164": "+1 555 555 0133", "label": "home"},
    )
    assert created.status_code == 201
    created_body = created.get_json()
    assert created_body["phone_e164"] == "+15555550133"
    assert created_body["label"] == "home"
    assert created_body["patient_id"] == str(PATIENT_ID)

    again = client.post(LINKS, json={"phone_e164": "+15555550133", "label": "home"})
    assert again.status_code == 200
    assert again.get_json()["id"] == created_body["id"]

    conflict = client.post(other_links, json={"phone_e164": "+15555550133", "label": "mobile"})
    assert_error(conflict, 409, "conflict")
    owned = client.post(
        other_links,
        json={"phone_e164": "+91 93725 01954", "label": "mobile"},
    )
    assert_error(owned, 409, "conflict")
    meera_conflict = client.post(
        LINKS,
        json={"phone_e164": "+919372501954", "label": "mobile"},
    )
    assert_error(meera_conflict, 409, "conflict")

    listed = client.get(LINKS).get_json()["phone_links"]
    assert {row["phone_e164"] for row in listed} == {"+15555550133"}
    ravi_listed = client.get(RAVI_LINKS).get_json()["phone_links"]
    assert [row["phone_e164"] for row in ravi_listed] == [PARTICIPANT_PHONE]
    assert ravi_listed[0]["label"] == "mobile"
    assert client.get(other_links).get_json()["phone_links"] == []
    assert client.get(PROFILE).get_json()["contact_number"] == "+919840011223"


def test_delete_phone_link_removes_it_from_the_owner_only(client):
    assert client.get("/api/v1/demo/ravi").status_code == 200
    missing = client.delete(f"{LINKS}/{quote(PARTICIPANT_PHONE, safe='')}")
    assert_error(missing, 404, "not_found")
    assert [row["phone_e164"] for row in client.get(RAVI_LINKS).get_json()["phone_links"]] == [
        PARTICIPANT_PHONE
    ]

    deleted = client.delete(f"{RAVI_LINKS}/{quote(PARTICIPANT_PHONE, safe='')}")
    assert deleted.status_code == 204
    assert client.get(RAVI_LINKS).get_json()["phone_links"] == []
    assert client.get(LINKS).get_json()["phone_links"] == []
    assert client.get(PROFILE).get_json()["contact_number"] == "+919840011223"

    replaced = client.post(
        RAVI_LINKS,
        json={"phone_e164": "+91 93725 01954", "label": "mobile"},
    )
    assert replaced.status_code == 201
    assert replaced.get_json()["patient_id"] == str(RAVI_ID)
    assert replaced.get_json()["label"] == "mobile"
    assert client.get(LINKS).get_json()["phone_links"] == []

    careloop = client.delete(f"{RAVI_LINKS}/{quote(CARELOOP_LINE, safe='')}")
    assert_error(careloop, 400, "validation_error")
    phones = [row["phone_e164"] for row in client.get(RAVI_LINKS).get_json()["phone_links"]]
    assert phones == [PARTICIPANT_PHONE]
    assert CARELOOP_LINE not in phones


def test_phone_link_rejects_non_e164_and_the_careloop_line(client, app):
    missing_plus = client.post(LINKS, json={"phone_e164": "919372501954", "label": "mobile"})
    assert_error(missing_plus, 400, "validation_error")
    dashed = client.post(LINKS, json={"phone_e164": "+91-9372501954", "label": "mobile"})
    assert_error(dashed, 400, "validation_error")
    careloop = client.post(LINKS, json={"phone_e164": "+1 423 583 8428", "label": "line"})
    error = assert_error(careloop, 400, "validation_error")
    assert any("CareLoop" in item for item in error["details"])
    missing_label = client.post(LINKS, json={"phone_e164": "+15555550144"})
    assert_error(missing_label, 400, "validation_error")
    unknown = client.post(
        f"/api/v1/patients/{uuid.uuid4()}/phone-links",
        json={"phone_e164": "+15555550144", "label": "x"},
    )
    assert_error(unknown, 404, "not_found")
    phones = [row["phone_e164"] for row in client.get(LINKS).get_json()["phone_links"]]
    assert phones == []
    assert count_rows(app, PatientPhoneLink) == 0
    assert resolve_owner(app, CARELOOP_LINE) is None
    assert resolve_owner(app, PARTICIPANT_PHONE) is None


def test_webhook_stores_a_voice_call_from_user_number_alone(client, app):
    assert client.get("/api/v1/demo/ravi").status_code == 200
    before = count_rows(app, HealthReading)
    response = client.post(
        WEBHOOK,
        json={
            "id": "phone-only-ravi",
            "user_number": "+919372501954",
            "status": "completed",
            "summary": "The caller matched the linked mobile.",
        },
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["duplicate"] is False
    assert body["patient_id"] == str(RAVI_ID)
    assert body["bolna_call_id"] == "phone-only-ravi"
    stored = voice_calls(app)
    assert len(stored) == 1
    assert stored[0]["patient_id"] == str(RAVI_ID)
    assert stored[0]["bolna_call_id"] == "phone-only-ravi"
    assert stored[0]["summary"] == "The caller matched the linked mobile."
    assert count_rows(app, HealthReading) == before


def test_webhook_resolves_to_and_from_and_ignores_the_careloop_line(client, app):
    assert client.get("/api/v1/demo/ravi").status_code == 200
    inbound = client.post(
        WEBHOOK,
        json={
            "id": "from-ravi",
            "user_number": "+14235838428",
            "status": "completed",
            "summary": "Inbound from the linked mobile.",
            "telephony_data": {
                "call_type": "inbound",
                "to_number": "+14235838428",
                "from_number": "+91 93725 01954",
            },
        },
    )
    assert inbound.status_code == 200
    assert inbound.get_json()["patient_id"] == str(RAVI_ID)
    stored = voice_calls(app)
    assert stored[0]["patient_id"] == str(RAVI_ID)
    assert stored[0]["call_type"] == "inbound"

    outbound = client.post(
        WEBHOOK,
        json={
            "id": "to-ravi",
            "status": "completed",
            "telephony_data": {"to_number": "+919372501954", "call_type": "outbound"},
        },
    )
    assert outbound.status_code == 200
    assert outbound.get_json()["patient_id"] == str(RAVI_ID)
    assert len(voice_calls(app)) == 2


def test_webhook_linked_number_wins_over_another_patient_id(client, app):
    assert client.get("/api/v1/demo/ravi").status_code == 200
    response = client.post(
        WEBHOOK,
        json={
            "id": "phone-overrides-chart-id",
            "patient_id": str(PATIENT_ID),
            "user_number": "+919372501954",
            "status": "completed",
            "summary": "The number selects the chart.",
        },
    )
    assert response.status_code == 200
    assert response.get_json()["patient_id"] == str(RAVI_ID)
    stored = voice_calls(app)
    assert stored[0]["patient_id"] == str(RAVI_ID)


def test_webhook_unknown_number_is_ignored(client, app):
    response = client.post(
        WEBHOOK,
        json={
            "id": "unknown-mobile",
            "user_number": "+15555550999",
            "status": "completed",
            "summary": "No chart for this number.",
            "telephony_data": {
                "to_number": "+14235838428",
                "from_number": "+15555550999",
            },
        },
    )
    assert response.status_code == 202
    assert response.get_json() == {"ignored": True}
    assert voice_calls(app) == []
    assert count_rows(app, HealthReading) == SEEDED_HEALTH_READINGS


def _insert_other(app) -> None:
    with app.app_context():
        session = SessionLocal()
        try:
            session.add(
                Patient(
                    id=OTHER_ID,
                    preferred_name="Nila Rao",
                    date_of_birth=date(1980, 1, 1),
                    preferred_language="en",
                    contact_number="+15555550100",
                    medical_history="",
                    allergies=[],
                    emergency_contact={},
                )
            )
            session.commit()
        finally:
            session.close()


def resolve_owner(app, number: str):
    with app.app_context():
        session = SessionLocal()
        try:
            return resolve_patient_id_by_phone(session, number)
        finally:
            session.close()
