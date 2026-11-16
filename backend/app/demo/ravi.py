"""Synthetic Ravi Sharma chart and three resettable call scenarios.

This module does not dial. The stored contact +15555501052 is not a real
person. Outbound tests must use the operator-entered participant number,
never this stored contact.

The evening metformin dose stays scheduled_unconfirmed until a call result
reports it. An inferred log does not mark that dose missed.
"""

import json
import sqlite3
import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy.exc import OperationalError

from app.timeutil import json_number, to_iso

PATIENT_ID = uuid.UUID("a52a0000-0000-4000-8000-000000000052")
PARTICIPANT_PHONE = "+919372501954"
PARTICIPANT_PHONE_LINK_ID = uuid.UUID("a52a0000-0000-4000-8000-0000000000f1")
DIABETES_ID = uuid.UUID("a52a0000-0000-4000-8000-0000000000d1")
HYPERTENSION_ID = uuid.UUID("a52a0000-0000-4000-8000-0000000000d2")
METFORMIN_ID = uuid.UUID("a52a0000-0000-4000-8000-0000000000e1")
CONSULTATION_ID = uuid.UUID("a52a0000-0000-4000-8000-0000000000c1")
CARE_PLAN_ID = uuid.UUID("a52a0000-0000-4000-8000-0000000000b1")
ONBOARDING_EVENT_ID = uuid.UUID("a52a0000-0000-4000-8000-00000000e001")
MEDICATION_EVENT_ID = uuid.UUID("a52a0000-0000-4000-8000-00000000e002")
WEEKLY_EVENT_ID = uuid.UUID("a52a0000-0000-4000-8000-00000000e003")

STORED_CONTACT = "+15555501052"
OUTBOUND_CONTACT_POLICY = (
    "The stored contact +15555501052 is synthetic and is not a real person. "
    "Outbound tests must use the operator-entered participant number, never this stored contact."
)
CLINIC = "CityCare Clinic"
DOCTOR = "Dr. Mehta"
PREFERRED_LANGUAGE = "en"
CHART_DATE = date(2026, 11, 15)
DATE_OF_BIRTH = date(1974, 3, 18)
CLINIC_TZ = timezone(timedelta(hours=5, minutes=30))
EVENING_DOSE_AT = datetime.combine(CHART_DATE, time(20, 0), tzinfo=CLINIC_TZ)
WINDOW_START = date(2026, 11, 9)
WINDOW_END = date(2026, 11, 15)
GLUCOSE_GAP_DAYS = (date(2026, 11, 11), date(2026, 11, 14))

SCHEDULED_UNCONFIRMED = "scheduled_unconfirmed"
PATIENT_REPORTED_TAKEN = "patient_reported_taken"
PATIENT_REPORTED_MISSED = "patient_reported_missed"
ADHERENCE_STATUSES = (
    SCHEDULED_UNCONFIRMED,
    PATIENT_REPORTED_TAKEN,
    PATIENT_REPORTED_MISSED,
)
NOT_ONBOARDED = "not_onboarded"
ONBOARDED = "onboarded"
VOICE_CALLS_AFTER_CONSENT = "allowed_only_after_consent"
CALL_RESULT_SOURCE = "call_self_report"

MEDICAL_HISTORY = (
    "Synthetic chart for CityCare Clinic. Not a real patient. "
    "Type 2 diabetes and hypertension are followed by Dr. Mehta. "
    "Voice calls are allowed only after consent. "
    "Onboarding stays not onboarded until a call records consent. "
    + OUTBOUND_CONTACT_POLICY
)

MONITORING_SCHEDULE = {
    "blood_glucose": {
        "window_start": WINDOW_START.isoformat(),
        "window_end": WINDOW_END.isoformat(),
        "expected": "daily",
    }
}
ESCALATION_PROTOCOL = {
    "clinic": CLINIC,
    "doctor": DOCTOR,
    "voice_calls": VOICE_CALLS_AFTER_CONSENT,
    "onboarding_rule": "not_onboarded_until_call_records_consent",
    "outbound_contact_policy": OUTBOUND_CONTACT_POLICY,
}

SCENARIOS = (
    {
        "id": ONBOARDING_EVENT_ID,
        "key": "onboarding",
        "summary": (
            "Voice calls are allowed only after consent. "
            "Onboarding stays not onboarded until a call records consent."
        ),
        "priority": "low",
        "status": "open",
    },
    {
        "id": MEDICATION_EVENT_ID,
        "key": "medication_followup",
        "summary": (
            "Evening metformin 500 mg at 20:00 is scheduled and unconfirmed. "
            "Do not mark the dose missed until a call result says so."
        ),
        "priority": "low",
        "status": "open",
    },
    {
        "id": WEEKLY_EVENT_ID,
        "key": "weekly_checkin",
        "summary": "Two glucose days have no reading: 2026-11-11 and 2026-11-14.",
        "priority": "low",
        "status": "open",
    },
)

_GLUCOSE_AT = (
    datetime(2026, 11, 9, 7, 10, tzinfo=CLINIC_TZ),
    datetime(2026, 11, 10, 7, 5, tzinfo=CLINIC_TZ),
    datetime(2026, 11, 12, 7, 15, tzinfo=CLINIC_TZ),
    datetime(2026, 11, 13, 7, 8, tzinfo=CLINIC_TZ),
    datetime(2026, 11, 15, 7, 20, tzinfo=CLINIC_TZ),
)
_GLUCOSE_VALUES = (128, 134, 141, 136, 122)
GLUCOSE_READING_IDS = (
    uuid.UUID("a52a0000-0000-4000-8000-000000000101"),
    uuid.UUID("a52a0000-0000-4000-8000-000000000102"),
    uuid.UUID("a52a0000-0000-4000-8000-000000000103"),
    uuid.UUID("a52a0000-0000-4000-8000-000000000104"),
    uuid.UUID("a52a0000-0000-4000-8000-000000000105"),
)
_BP_AT = (
    datetime(2026, 11, 8, 8, 0, tzinfo=CLINIC_TZ),
    datetime(2026, 11, 10, 8, 15, tzinfo=CLINIC_TZ),
    datetime(2026, 11, 13, 9, 0, tzinfo=CLINIC_TZ),
)
_BP_PAIRS = ((136, 86), (142, 88), (130, 82))
_BP_SOURCES = ("home_monitor", "home_monitor", "clinic")


def chart_models_available() -> bool:
    """True when the chart ORM classes this demo reads are importable."""
    try:
        from app import models
    except ImportError:
        return False
    required = (
        "Patient",
        "Condition",
        "Medication",
        "HealthReading",
        "Consultation",
        "AdherenceLog",
        "CarePlan",
        "CareEvent",
        "VoiceCall",
    )
    return all(hasattr(models, name) for name in required)


def load_ravi(session) -> dict:
    """Profile, schedule, gaps, and scenario state.

    Reads the chart tables when those models exist. Otherwise applies this
    seed to a private SQLite database and reads that.
    """
    if not chart_models_available():
        return _payload_from_sqlite_seed()
    try:
        ensure_seeded(session)
        return assemble(snapshot_from_session(session))
    except OperationalError:
        session.rollback()
        return _payload_from_sqlite_seed()


def reset_ravi(session) -> dict:
    """Restore the synthetic scenario rows. Does not dial."""
    if not chart_models_available():
        return _payload_from_sqlite_seed()
    try:
        restore(session)
        return assemble(snapshot_from_session(session))
    except OperationalError:
        session.rollback()
        return _payload_from_sqlite_seed()


def ensure_seeded(session) -> bool:
    """Insert Ravi when the patient row is absent. Returns True if it inserted.

    The participant mobile is linked to Ravi when the row is created and when
    it is already present. Meera's chart contact is left unchanged.
    """
    from app.models import Patient

    inserted = session.get(Patient, PATIENT_ID) is None
    if inserted:
        _save_patient(session)
        session.add_all(_child_rows())
    linked = claim_participant_phone(session)
    if inserted or linked:
        session.commit()
    return inserted


def claim_participant_phone(session) -> bool:
    """Point +919372501954 at Ravi. Does not commit. No-op when Ravi is absent."""
    from app.models import Patient
    from app.phones import claim_phone_link

    if session.get(Patient, PATIENT_ID) is None:
        return False
    return claim_phone_link(
        session,
        PATIENT_ID,
        PARTICIPANT_PHONE,
        "mobile",
        link_id=PARTICIPANT_PHONE_LINK_ID,
    )


def restore(session) -> None:
    """Replace Ravi's child rows with the canonical scenario chart."""
    _delete_children(session)
    session.flush()
    session.expunge_all()
    _save_patient(session)
    session.add_all(_child_rows())
    claim_participant_phone(session)
    session.commit()


def classify_adherence(logs: list[dict]) -> str:
    """Status for one scheduled dose.

    Missed becomes patient_reported_missed only when a call result says so.
    Inferred logs leave the dose scheduled_unconfirmed.
    """
    call_results = [row for row in logs if row["source"] == CALL_RESULT_SOURCE]
    if call_results:
        latest = max(call_results, key=lambda row: (row["recorded_at"], row["id"]))
        if latest["reported_status"] == "taken":
            return PATIENT_REPORTED_TAKEN
        if latest["reported_status"] == "missed":
            return PATIENT_REPORTED_MISSED
        return SCHEDULED_UNCONFIRMED
    taken_reports = [
        row for row in logs if row["source"] == "app" and row["reported_status"] == "taken"
    ]
    if taken_reports:
        return PATIENT_REPORTED_TAKEN
    return SCHEDULED_UNCONFIRMED


def assemble(snapshot: dict) -> dict:
    """Build the demo payload from plain chart rows."""
    patient = snapshot["patient"]
    protocol = (snapshot.get("care_plan") or {}).get("escalation_protocol") or {}
    clinic = protocol.get("clinic") or CLINIC
    doctor = protocol.get("doctor") or DOCTOR
    policy = protocol.get("outbound_contact_policy") or OUTBOUND_CONTACT_POLICY
    voice_calls = protocol.get("voice_calls") or VOICE_CALLS_AFTER_CONSENT
    consent = _consent_recorded(snapshot["voice_calls"])
    onboarding = ONBOARDED if consent else NOT_ONBOARDED
    dose_status = classify_adherence(_logs_for_evening_dose(snapshot["adherence_logs"]))
    gaps = _glucose_gaps(snapshot)
    conditions = sorted(snapshot["conditions"], key=lambda row: row["condition_type"])
    consultation = _next_consultation(snapshot["consultations"])
    dose = _evening_dose(snapshot["medications"], dose_status)
    return {
        "profile": {
            "id": patient["id"],
            "preferred_name": patient["preferred_name"],
            "date_of_birth": _as_date(patient["date_of_birth"]).isoformat(),
            "age": _age_on(DATE_OF_BIRTH, CHART_DATE),
            "age_as_of": CHART_DATE.isoformat(),
            "preferred_language": patient["preferred_language"],
            "contact_number": patient["contact_number"],
            "outbound_contact_policy": policy,
            "clinic": clinic,
            "doctor": doctor,
            "conditions": [
                {
                    "id": row["id"],
                    "condition_type": row["condition_type"],
                    "diagnosis_date": _as_date(row["diagnosis_date"]).isoformat(),
                    "treating_clinician": row["treating_clinician"],
                }
                for row in conditions
            ],
            "communication_preference": {"voice_calls": voice_calls},
            "onboarding_status": onboarding,
            "consent_recorded": consent,
            "medical_history": patient["medical_history"],
        },
        "schedule": {
            "evening_dose": dose,
            "medications": [_medication_row(row, dose_status) for row in snapshot["medications"]],
            "next_consultation": _consultation_payload(consultation, clinic),
            "blood_pressure_history": _blood_pressure_history(snapshot["readings"]),
        },
        "gaps": gaps,
        "scenarios": _scenario_payloads(snapshot["scenarios"], onboarding, consent, dose_status, gaps),
    }


def snapshot_from_session(session) -> dict:
    from sqlalchemy import select

    from app.models import (
        AdherenceLog,
        CareEvent,
        CarePlan,
        Condition,
        Consultation,
        HealthReading,
        Medication,
        Patient,
        VoiceCall,
    )

    patient = session.get(Patient, PATIENT_ID)
    if patient is None:
        raise LookupError("Ravi Sharma is not seeded")
    conditions = session.scalars(select(Condition).where(Condition.patient_id == PATIENT_ID)).all()
    medications = session.scalars(select(Medication).where(Medication.patient_id == PATIENT_ID)).all()
    readings = session.scalars(
        select(HealthReading).where(HealthReading.patient_id == PATIENT_ID)
    ).all()
    consultations = session.scalars(
        select(Consultation).where(Consultation.patient_id == PATIENT_ID)
    ).all()
    care_plan = session.scalar(select(CarePlan).where(CarePlan.patient_id == PATIENT_ID))
    events = session.scalars(select(CareEvent).where(CareEvent.patient_id == PATIENT_ID)).all()
    logs = session.scalars(select(AdherenceLog).where(AdherenceLog.patient_id == PATIENT_ID)).all()
    calls = session.scalars(select(VoiceCall).where(VoiceCall.patient_id == PATIENT_ID)).all()
    return {
        "patient": {
            "id": str(patient.id),
            "preferred_name": patient.preferred_name,
            "date_of_birth": patient.date_of_birth,
            "preferred_language": patient.preferred_language,
            "contact_number": patient.contact_number,
            "medical_history": patient.medical_history,
        },
        "conditions": [
            {
                "id": str(row.id),
                "condition_type": row.condition_type,
                "diagnosis_date": row.diagnosis_date,
                "treating_clinician": row.treating_clinician,
            }
            for row in conditions
        ],
        "medications": [
            {
                "id": str(row.id),
                "medication_name": row.medication_name,
                "prescribed_dosage": row.prescribed_dosage,
                "frequency": row.frequency,
                "schedule": row.schedule or {},
            }
            for row in medications
        ],
        "readings": [
            {
                "measurement_type": row.measurement_type,
                "value": row.value,
                "secondary_value": row.secondary_value,
                "measured_at": row.measured_at,
                "source": row.source,
            }
            for row in readings
        ],
        "consultations": [
            {
                "id": str(row.id),
                "clinician": row.clinician,
                "appointment_date": row.appointment_date,
                "consultation_type": row.consultation_type,
                "status": row.status,
            }
            for row in consultations
        ],
        "care_plan": None
        if care_plan is None
        else {
            "monitoring_schedule": care_plan.monitoring_schedule or {},
            "escalation_protocol": care_plan.escalation_protocol or {},
            "clinician": care_plan.clinician,
        },
        "scenarios": [
            {
                "id": str(row.id),
                "event_type": row.event_type,
                "event_description": row.event_description,
                "status": row.status,
            }
            for row in events
        ],
        "adherence_logs": [
            {
                "id": str(row.id),
                "medication_id": str(row.medication_id),
                "schedule_time": row.schedule_time,
                "reported_status": row.reported_status,
                "source": row.source,
                "recorded_at": row.recorded_at,
            }
            for row in logs
        ],
        "voice_calls": [{"extracted_data": row.extracted_data or {}} for row in calls],
    }


def _payload_from_sqlite_seed() -> dict:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    try:
        _apply_seed_sqlite(connection)
        return assemble(_snapshot_from_sqlite(connection))
    finally:
        connection.close()


def _apply_seed_sqlite(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE patients (
          id TEXT PRIMARY KEY,
          preferred_name TEXT NOT NULL,
          date_of_birth TEXT NOT NULL,
          preferred_language TEXT NOT NULL,
          contact_number TEXT NOT NULL,
          medical_history TEXT NOT NULL
        );
        CREATE TABLE conditions (
          id TEXT PRIMARY KEY,
          condition_type TEXT NOT NULL,
          diagnosis_date TEXT NOT NULL,
          treating_clinician TEXT NOT NULL
        );
        CREATE TABLE medications (
          id TEXT PRIMARY KEY,
          medication_name TEXT NOT NULL,
          prescribed_dosage TEXT NOT NULL,
          frequency TEXT NOT NULL,
          schedule TEXT NOT NULL
        );
        CREATE TABLE health_readings (
          id TEXT PRIMARY KEY,
          measurement_type TEXT NOT NULL,
          value REAL NOT NULL,
          secondary_value REAL,
          measured_at TEXT NOT NULL,
          source TEXT NOT NULL
        );
        CREATE TABLE consultations (
          id TEXT PRIMARY KEY,
          clinician TEXT NOT NULL,
          appointment_date TEXT NOT NULL,
          consultation_type TEXT NOT NULL,
          status TEXT NOT NULL
        );
        CREATE TABLE care_plans (
          id TEXT PRIMARY KEY,
          monitoring_schedule TEXT NOT NULL,
          escalation_protocol TEXT NOT NULL,
          clinician TEXT NOT NULL
        );
        CREATE TABLE care_events (
          id TEXT PRIMARY KEY,
          event_type TEXT NOT NULL,
          event_description TEXT NOT NULL,
          status TEXT NOT NULL
        );
        CREATE TABLE adherence_logs (
          id TEXT PRIMARY KEY,
          medication_id TEXT NOT NULL,
          schedule_time TEXT NOT NULL,
          reported_status TEXT NOT NULL,
          source TEXT NOT NULL,
          recorded_at TEXT NOT NULL
        );
        CREATE TABLE voice_calls (
          id TEXT PRIMARY KEY,
          extracted_data TEXT NOT NULL
        );
        """
    )
    connection.execute(
        """
        INSERT INTO patients (
          id, preferred_name, date_of_birth, preferred_language, contact_number, medical_history
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            str(PATIENT_ID),
            "Ravi Sharma",
            DATE_OF_BIRTH.isoformat(),
            PREFERRED_LANGUAGE,
            STORED_CONTACT,
            MEDICAL_HISTORY,
        ),
    )
    connection.executemany(
        """
        INSERT INTO conditions (id, condition_type, diagnosis_date, treating_clinician)
        VALUES (?, ?, ?, ?)
        """,
        (
            (str(DIABETES_ID), "type_2_diabetes", "2019-03-18", DOCTOR),
            (str(HYPERTENSION_ID), "hypertension", "2021-11-02", DOCTOR),
        ),
    )
    connection.execute(
        """
        INSERT INTO medications (
          id, medication_name, prescribed_dosage, frequency, schedule
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            str(METFORMIN_ID),
            "Metformin",
            "500 mg",
            "Once daily",
            json.dumps({"times": ["20:00"]}),
        ),
    )
    glucose_rows = [
        (
            str(reading_id),
            "blood_glucose",
            value,
            None,
            measured_at.isoformat(),
            "glucometer",
        )
        for reading_id, measured_at, value in zip(GLUCOSE_READING_IDS, _GLUCOSE_AT, _GLUCOSE_VALUES)
    ]
    bp_rows = []
    for index, (measured_at, pair, source) in enumerate(zip(_BP_AT, _BP_PAIRS, _BP_SOURCES)):
        systolic, diastolic = pair
        bp_rows.append(
            (
                f"a52a0000-0000-4000-8000-0000000002{index * 2 + 1:02d}",
                "systolic_blood_pressure",
                systolic,
                diastolic,
                measured_at.isoformat(),
                source,
            )
        )
        bp_rows.append(
            (
                f"a52a0000-0000-4000-8000-0000000002{index * 2 + 2:02d}",
                "diastolic_blood_pressure",
                diastolic,
                None,
                measured_at.isoformat(),
                source,
            )
        )
    connection.executemany(
        """
        INSERT INTO health_readings (
          id, measurement_type, value, secondary_value, measured_at, source
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        glucose_rows + bp_rows,
    )
    connection.execute(
        """
        INSERT INTO consultations (
          id, clinician, appointment_date, consultation_type, status
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            str(CONSULTATION_ID),
            DOCTOR,
            datetime(2026, 11, 24, 11, 0, tzinfo=CLINIC_TZ).isoformat(),
            "consultation",
            "scheduled",
        ),
    )
    connection.execute(
        """
        INSERT INTO care_plans (id, monitoring_schedule, escalation_protocol, clinician)
        VALUES (?, ?, ?, ?)
        """,
        (
            str(CARE_PLAN_ID),
            json.dumps(MONITORING_SCHEDULE),
            json.dumps(ESCALATION_PROTOCOL),
            DOCTOR,
        ),
    )
    connection.executemany(
        """
        INSERT INTO care_events (id, event_type, event_description, status)
        VALUES (?, ?, ?, ?)
        """,
        [
            (str(row["id"]), row["key"], row["summary"], row["status"])
            for row in SCENARIOS
        ],
    )
    connection.commit()


def _snapshot_from_sqlite(connection: sqlite3.Connection) -> dict:
    patient = connection.execute("SELECT * FROM patients").fetchone()
    care_plan = connection.execute("SELECT * FROM care_plans").fetchone()
    return {
        "patient": {
            "id": patient["id"],
            "preferred_name": patient["preferred_name"],
            "date_of_birth": patient["date_of_birth"],
            "preferred_language": patient["preferred_language"],
            "contact_number": patient["contact_number"],
            "medical_history": patient["medical_history"],
        },
        "conditions": [
            {
                "id": row["id"],
                "condition_type": row["condition_type"],
                "diagnosis_date": row["diagnosis_date"],
                "treating_clinician": row["treating_clinician"],
            }
            for row in connection.execute("SELECT * FROM conditions")
        ],
        "medications": [
            {
                "id": row["id"],
                "medication_name": row["medication_name"],
                "prescribed_dosage": row["prescribed_dosage"],
                "frequency": row["frequency"],
                "schedule": json.loads(row["schedule"]),
            }
            for row in connection.execute("SELECT * FROM medications")
        ],
        "readings": [
            {
                "measurement_type": row["measurement_type"],
                "value": row["value"],
                "secondary_value": row["secondary_value"],
                "measured_at": row["measured_at"],
                "source": row["source"],
            }
            for row in connection.execute("SELECT * FROM health_readings")
        ],
        "consultations": [
            {
                "id": row["id"],
                "clinician": row["clinician"],
                "appointment_date": row["appointment_date"],
                "consultation_type": row["consultation_type"],
                "status": row["status"],
            }
            for row in connection.execute("SELECT * FROM consultations")
        ],
        "care_plan": {
            "monitoring_schedule": json.loads(care_plan["monitoring_schedule"]),
            "escalation_protocol": json.loads(care_plan["escalation_protocol"]),
            "clinician": care_plan["clinician"],
        },
        "scenarios": [
            {
                "id": row["id"],
                "event_type": row["event_type"],
                "event_description": row["event_description"],
                "status": row["status"],
            }
            for row in connection.execute("SELECT * FROM care_events")
        ],
        "adherence_logs": [
            {
                "id": row["id"],
                "medication_id": row["medication_id"],
                "schedule_time": row["schedule_time"],
                "reported_status": row["reported_status"],
                "source": row["source"],
                "recorded_at": row["recorded_at"],
            }
            for row in connection.execute("SELECT * FROM adherence_logs")
        ],
        "voice_calls": [
            {"extracted_data": json.loads(row["extracted_data"])}
            for row in connection.execute("SELECT * FROM voice_calls")
        ],
    }


def _save_patient(session) -> None:
    from app.models import Patient

    patient = session.get(Patient, PATIENT_ID)
    fields = {
        "preferred_name": "Ravi Sharma",
        "date_of_birth": DATE_OF_BIRTH,
        "preferred_language": PREFERRED_LANGUAGE,
        "contact_number": STORED_CONTACT,
        "medical_history": MEDICAL_HISTORY,
        "allergies": [],
        "emergency_contact": {
            "name": "CityCare Clinic desk",
            "relation": "Clinic",
            "note": "Synthetic chart contact. No outbound number is stored here.",
        },
    }
    if patient is None:
        session.add(Patient(id=PATIENT_ID, **fields))
    else:
        for name, value in fields.items():
            setattr(patient, name, value)
    session.flush()


def _child_rows() -> list:
    from app.models import CareEvent, CarePlan, Condition, Consultation, HealthReading, Medication

    rows: list = [
        Condition(
            id=DIABETES_ID,
            patient_id=PATIENT_ID,
            condition_type="type_2_diabetes",
            diagnosis_date=date(2019, 3, 18),
            treating_clinician=DOCTOR,
        ),
        Condition(
            id=HYPERTENSION_ID,
            patient_id=PATIENT_ID,
            condition_type="hypertension",
            diagnosis_date=date(2021, 11, 2),
            treating_clinician=DOCTOR,
        ),
        Medication(
            id=METFORMIN_ID,
            patient_id=PATIENT_ID,
            medication_name="Metformin",
            prescribed_dosage="500 mg",
            frequency="Once daily",
            schedule={"times": ["20:00"]},
            start_date=date(2024, 6, 1),
            end_date=None,
            prescribing_clinician=DOCTOR,
            active=True,
        ),
        Consultation(
            id=CONSULTATION_ID,
            patient_id=PATIENT_ID,
            clinician=DOCTOR,
            appointment_date=datetime(2026, 11, 24, 11, 0, tzinfo=CLINIC_TZ),
            consultation_type="consultation",
            status="scheduled",
        ),
        CarePlan(
            id=CARE_PLAN_ID,
            patient_id=PATIENT_ID,
            condition="type_2_diabetes",
            monitoring_schedule=MONITORING_SCHEDULE,
            clinician=DOCTOR,
            approved_rules=[],
            escalation_protocol=ESCALATION_PROTOCOL,
        ),
    ]
    for reading_id, measured_at, value in zip(GLUCOSE_READING_IDS, _GLUCOSE_AT, _GLUCOSE_VALUES):
        rows.append(
            _reading(
                reading_id,
                "blood_glucose",
                value,
                None,
                "mg/dL",
                "fasting",
                measured_at,
                "glucometer",
                "synthetic-ravi-glucometer",
            )
        )
    for index, (measured_at, pair, source) in enumerate(zip(_BP_AT, _BP_PAIRS, _BP_SOURCES)):
        systolic, diastolic = pair
        device = None if source == "clinic" else "synthetic-ravi-home-monitor"
        rows.append(
            _reading(
                uuid.UUID(f"a52a0000-0000-4000-8000-0000000002{index * 2 + 1:02d}"),
                "systolic_blood_pressure",
                systolic,
                diastolic,
                "mmHg",
                "resting",
                measured_at,
                source,
                device,
            )
        )
        rows.append(
            _reading(
                uuid.UUID(f"a52a0000-0000-4000-8000-0000000002{index * 2 + 2:02d}"),
                "diastolic_blood_pressure",
                diastolic,
                None,
                "mmHg",
                "resting",
                measured_at,
                source,
                device,
            )
        )
    for scenario in SCENARIOS:
        rows.append(
            CareEvent(
                id=scenario["id"],
                patient_id=PATIENT_ID,
                event_type=scenario["key"],
                event_description=scenario["summary"],
                priority=scenario["priority"],
                status=scenario["status"],
            )
        )
    return rows


def _reading(
    reading_id: uuid.UUID,
    measurement_type: str,
    value: int,
    secondary_value: int | None,
    unit: str,
    context: str,
    measured_at: datetime,
    source: str,
    device_id: str | None,
):
    from app.models import HealthReading

    row = HealthReading(
        id=reading_id,
        patient_id=PATIENT_ID,
        measurement_type=measurement_type,
        value=value,
        secondary_value=secondary_value,
        unit=unit,
        measurement_context=context,
        measured_at=measured_at,
        source=source,
        device_id=device_id,
        data_quality="valid",
        support=None,
    )
    if "ingest_origin" in HealthReading.__mapper__.attrs:
        row.ingest_origin = "synthetic"
    return row


def _delete_children(session) -> None:
    import importlib

    from sqlalchemy import delete

    from app.models import (
        AdherenceLog,
        CareEvent,
        CarePlan,
        Condition,
        Consultation,
        Document,
        HealthReading,
        Medication,
        VoiceCall,
    )

    ordered = [
        AdherenceLog,
        VoiceCall,
        HealthReading,
        Consultation,
        CarePlan,
        CareEvent,
        Condition,
        Medication,
    ]
    for module_name, class_name in (
        ("app.ingest.models", "DocumentExtraction"),
        ("app.ingest.models", "IngestSyncRun"),
    ):
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        model = getattr(module, class_name, None)
        if model is not None:
            ordered.insert(0, model)
    ordered.append(Document)
    for model in ordered:
        session.execute(delete(model).where(model.patient_id == PATIENT_ID))


def _logs_for_evening_dose(logs: list[dict]) -> list[dict]:
    matched = []
    for row in logs:
        if row["medication_id"] != str(METFORMIN_ID):
            continue
        if _instant(row["schedule_time"]) != _instant(EVENING_DOSE_AT):
            continue
        matched.append(
            {
                "id": row["id"],
                "source": row["source"],
                "reported_status": row["reported_status"],
                "recorded_at": _instant(row["recorded_at"]),
            }
        )
    return matched


def _consent_recorded(calls: list[dict]) -> bool:
    for call in calls:
        data = call.get("extracted_data") or {}
        if data.get("consent_recorded") is True:
            return True
    return False


def _glucose_gaps(snapshot: dict) -> dict:
    schedule = ((snapshot.get("care_plan") or {}).get("monitoring_schedule") or {}).get(
        "blood_glucose"
    ) or {}
    start = _as_date(schedule.get("window_start") or WINDOW_START)
    end = _as_date(schedule.get("window_end") or WINDOW_END)
    present = {
        _instant(row["measured_at"]).astimezone(CLINIC_TZ).date()
        for row in snapshot["readings"]
        if row["measurement_type"] == "blood_glucose"
    }
    days = []
    cursor = start
    while cursor <= end:
        days.append(cursor)
        cursor += timedelta(days=1)
    with_reading = [day.isoformat() for day in days if day in present]
    without_reading = [day.isoformat() for day in days if day not in present]
    return {
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "glucose_days_with_reading": with_reading,
        "glucose_days_without_reading": without_reading,
    }


def _evening_dose(medications: list[dict], status: str) -> dict | None:
    medication = next(
        (
            row
            for row in medications
            if "20:00" in ((row.get("schedule") or {}).get("times") or [])
        ),
        None,
    )
    if medication is None:
        return None
    return {
        "medication_id": medication["id"],
        "medication_name": medication["medication_name"],
        "prescribed_dosage": medication["prescribed_dosage"],
        "frequency": medication["frequency"],
        "time_local": "20:00",
        "schedule_time": to_iso(EVENING_DOSE_AT),
        "adherence_status": status,
        "presumed_missed": False,
    }


def _medication_row(medication: dict, status: str) -> dict:
    times = list((medication.get("schedule") or {}).get("times") or [])
    evening = "20:00" in times
    return {
        "id": medication["id"],
        "medication_name": medication["medication_name"],
        "prescribed_dosage": medication["prescribed_dosage"],
        "frequency": medication["frequency"],
        "times": times,
        "adherence_status": status if evening else SCHEDULED_UNCONFIRMED,
        "presumed_missed": False,
    }


def _next_consultation(consultations: list[dict]) -> dict | None:
    upcoming = [row for row in consultations if row["status"] == "scheduled"]
    if not upcoming:
        return None
    return min(upcoming, key=lambda row: _instant(row["appointment_date"]))


def _consultation_payload(consultation: dict | None, clinic: str) -> dict | None:
    if consultation is None:
        return None
    return {
        "id": consultation["id"],
        "clinician": consultation["clinician"],
        "clinic": clinic,
        "appointment_date": to_iso(_instant(consultation["appointment_date"])),
        "consultation_type": consultation["consultation_type"],
        "status": consultation["status"],
    }


def _blood_pressure_history(readings: list[dict]) -> list[dict]:
    diastolic = {
        _instant(row["measured_at"]): row
        for row in readings
        if row["measurement_type"] == "diastolic_blood_pressure"
    }
    history = []
    systolic_rows = [
        row for row in readings if row["measurement_type"] == "systolic_blood_pressure"
    ]
    for row in sorted(systolic_rows, key=lambda item: _instant(item["measured_at"])):
        instant = _instant(row["measured_at"])
        pair = diastolic.get(instant)
        diastolic_value = pair["value"] if pair is not None else row["secondary_value"]
        history.append(
            {
                "measured_at": to_iso(instant),
                "systolic": json_number(row["value"]),
                "diastolic": json_number(diastolic_value),
                "source": row["source"],
            }
        )
    return history


def _scenario_payloads(
    events: list[dict],
    onboarding: str,
    consent: bool,
    dose_status: str,
    gaps: dict,
) -> list[dict]:
    stored = {}
    for event in events:
        if event["event_type"] in {row["key"] for row in SCENARIOS}:
            stored[event["event_type"]] = event
    states = {
        "onboarding": {
            "onboarding_status": onboarding,
            "voice_calls": VOICE_CALLS_AFTER_CONSENT,
            "consent_recorded": consent,
        },
        "medication_followup": {
            "medication_name": "Metformin",
            "prescribed_dosage": "500 mg",
            "time_local": "20:00",
            "adherence_status": dose_status,
            "presumed_missed": False,
        },
        "weekly_checkin": {
            "glucose_days_without_reading": list(gaps["glucose_days_without_reading"]),
        },
    }
    payloads = []
    for scenario in SCENARIOS:
        event = stored.get(scenario["key"])
        payloads.append(
            {
                "id": str(event["id"]) if event else str(scenario["id"]),
                "key": scenario["key"],
                "summary": event["event_description"] if event else scenario["summary"],
                "record_status": event["status"] if event else scenario["status"],
                "state": states[scenario["key"]],
            }
        )
    return payloads


def _age_on(born: date, on: date) -> int:
    years = on.year - born.year
    if (on.month, on.day) < (born.month, born.day):
        years -= 1
    return years


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _instant(value) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
