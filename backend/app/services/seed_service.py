"""Synthetic development chart. Not a real patient and not a Bolna call."""

import uuid
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models import (
    CarePlan,
    Condition,
    Consultation,
    Document,
    HealthReading,
    Medication,
    Patient,
)

PATIENT_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
METFORMIN_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
TELMISARTAN_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")
CONSULTATION_ID = uuid.UUID("44444444-4444-4444-8444-444444444444")
CLINICIAN = "Dr. Anika Shah"
# patients.preferred_language is one tag. The chart is English.
# hi and kn are valid tags for tests; they are not extra columns.
SEEDED_GLUCOSE_READINGS = 5
SEEDED_HEALTH_READINGS = 12

MEDICAL_HISTORY = (
    "Synthetic chart note: type 2 diabetes was recorded in 2019 after repeated fasting glucose results, "
    "and hypertension was recorded in 2021. This narrative is for the chart only and must not be read "
    "to the patient on a call."
)


def seed(session: Session) -> bool:
    existing = session.get(Patient, PATIENT_ID)
    if existing is not None:
        changed = False
        if existing.preferred_language != "en":
            existing.preferred_language = "en"
            changed = True
        if _ensure_participant_phone(session):
            changed = True
        if changed:
            session.commit()
        return False
    session.add(
        Patient(
            id=PATIENT_ID,
            preferred_name="Meera Iyer",
            date_of_birth=date(1978, 4, 12),
            preferred_language="en",
            contact_number="+919840011223",
            medical_history=MEDICAL_HISTORY,
            allergies=["Penicillin"],
            emergency_contact={
                "name": "Arjun Iyer",
                "relation": "Spouse",
                "phone": "+919840044556",
            },
        )
    )
    # The patient row must exist before child rows. SQLite enforces that foreign key.
    session.flush()
    session.add_all(
        [
            Condition(
                id=uuid.UUID("55555555-5555-4555-8555-555555555551"),
                patient_id=PATIENT_ID,
                condition_type="type_2_diabetes",
                diagnosis_date=date(2019, 6, 1),
                treating_clinician=CLINICIAN,
            ),
            Condition(
                id=uuid.UUID("55555555-5555-4555-8555-555555555552"),
                patient_id=PATIENT_ID,
                condition_type="hypertension",
                diagnosis_date=date(2021, 2, 14),
                treating_clinician=CLINICIAN,
            ),
            Medication(
                id=METFORMIN_ID,
                patient_id=PATIENT_ID,
                medication_name="Metformin",
                prescribed_dosage="500 mg",
                frequency="Twice daily",
                schedule={"times": ["08:00", "20:00"]},
                start_date=date(2019, 6, 15),
                end_date=None,
                prescribing_clinician=CLINICIAN,
                active=True,
            ),
            Medication(
                id=TELMISARTAN_ID,
                patient_id=PATIENT_ID,
                medication_name="Telmisartan",
                prescribed_dosage="40 mg",
                frequency="Once daily",
                schedule={"times": ["08:00"]},
                start_date=date(2021, 2, 20),
                end_date=None,
                prescribing_clinician=CLINICIAN,
                active=True,
            ),
            HealthReading(
                patient_id=PATIENT_ID,
                measurement_type="blood_glucose",
                value=118,
                secondary_value=None,
                unit="mg/dL",
                measurement_context="fasting",
                measured_at=_at("2026-11-08T07:05:00+05:30"),
                source="glucometer",
                device_id=None,
                data_quality="valid",
                support=None,
            ),
            HealthReading(
                patient_id=PATIENT_ID,
                measurement_type="blood_glucose",
                value=142,
                secondary_value=None,
                unit="mg/dL",
                measurement_context="fasting",
                measured_at=_at("2026-11-10T07:12:00+05:30"),
                source="manual",
                device_id=None,
                data_quality="valid",
                support=None,
            ),
            HealthReading(
                patient_id=PATIENT_ID,
                measurement_type="blood_glucose",
                value=164,
                secondary_value=None,
                unit="mg/dL",
                measurement_context="post_meal",
                measured_at=_at("2026-11-12T13:40:00+05:30"),
                source="cgm",
                device_id=None,
                data_quality="valid",
                support=None,
            ),
            HealthReading(
                patient_id=PATIENT_ID,
                measurement_type="blood_glucose",
                value=131,
                secondary_value=None,
                unit="mg/dL",
                measurement_context="fasting",
                measured_at=_at("2026-11-13T07:16:00+05:30"),
                source="glucometer",
                device_id=None,
                data_quality="valid",
                support=None,
            ),
            HealthReading(
                patient_id=PATIENT_ID,
                measurement_type="blood_glucose",
                value=125,
                secondary_value=None,
                unit="mg/dL",
                measurement_context="fasting",
                measured_at=_at("2026-11-15T07:20:00+05:30"),
                source="glucometer",
                device_id=None,
                data_quality="valid",
                support=None,
            ),
            HealthReading(
                patient_id=PATIENT_ID,
                measurement_type="systolic_blood_pressure",
                value=132,
                secondary_value=84,
                unit="mmHg",
                measurement_context="resting",
                measured_at=_at("2026-11-08T08:05:00+05:30"),
                source="home_monitor",
                device_id=None,
                data_quality="valid",
                support=None,
            ),
            HealthReading(
                patient_id=PATIENT_ID,
                measurement_type="diastolic_blood_pressure",
                value=84,
                secondary_value=None,
                unit="mmHg",
                measurement_context="resting",
                measured_at=_at("2026-11-08T08:05:00+05:30"),
                source="home_monitor",
                device_id=None,
                data_quality="valid",
                support=None,
            ),
            HealthReading(
                patient_id=PATIENT_ID,
                measurement_type="systolic_blood_pressure",
                value=140,
                secondary_value=88,
                unit="mmHg",
                measurement_context="resting",
                measured_at=_at("2026-11-11T11:05:00+05:30"),
                source="clinic",
                device_id=None,
                data_quality="valid",
                support=None,
            ),
            HealthReading(
                patient_id=PATIENT_ID,
                measurement_type="diastolic_blood_pressure",
                value=88,
                secondary_value=None,
                unit="mmHg",
                measurement_context="resting",
                measured_at=_at("2026-11-11T11:05:00+05:30"),
                source="clinic",
                device_id=None,
                data_quality="valid",
                support=None,
            ),
            HealthReading(
                patient_id=PATIENT_ID,
                measurement_type="systolic_blood_pressure",
                value=126,
                secondary_value=80,
                unit="mmHg",
                measurement_context=None,
                measured_at=_at("2026-11-15T08:10:00+05:30"),
                source="home_monitor",
                device_id=None,
                data_quality="valid",
                support=None,
            ),
            HealthReading(
                patient_id=PATIENT_ID,
                measurement_type="diastolic_blood_pressure",
                value=80,
                secondary_value=None,
                unit="mmHg",
                measurement_context=None,
                measured_at=_at("2026-11-15T08:10:00+05:30"),
                source="home_monitor",
                device_id=None,
                data_quality="valid",
                support=None,
            ),
            HealthReading(
                patient_id=PATIENT_ID,
                measurement_type="pulse",
                value=71,
                secondary_value=None,
                unit="bpm",
                measurement_context=None,
                measured_at=_at("2026-11-15T08:10:00+05:30"),
                source="home_monitor",
                device_id=None,
                data_quality="valid",
                support=None,
            ),
            Consultation(
                id=CONSULTATION_ID,
                patient_id=PATIENT_ID,
                clinician=CLINICIAN,
                appointment_date=_at("2026-11-20T09:30:00+05:30"),
                consultation_type="consultation",
                status="scheduled",
            ),
            CarePlan(
                patient_id=PATIENT_ID,
                condition="type_2_diabetes",
                monitoring_schedule={"blood_glucose": ["fasting"], "blood_pressure": ["morning"]},
                clinician=CLINICIAN,
                approved_rules=[],
                escalation_protocol={"handoff": "clinician_review"},
            ),
            Document(
                patient_id=PATIENT_ID,
                document_type="prescription",
                file_location="synthetic://chart/demo-prescription-2026-10-20.pdf",
                extraction_status="not_requested",
            ),
            Document(
                patient_id=PATIENT_ID,
                document_type="lab_report",
                file_location="synthetic://chart/demo-lab-report-2026-09-18.pdf",
                extraction_status="not_requested",
            ),
        ]
    )
    _ensure_participant_phone(session)
    session.commit()
    return True


def _ensure_participant_phone(session: Session) -> bool:
    """Link +919372501954 to Ravi when his chart exists.

    Meera's contact_number stays +919840011223. This does not create Ravi.
    """
    from app.demo.ravi import claim_participant_phone

    return claim_participant_phone(session)


def _at(text: str) -> datetime:
    return datetime.fromisoformat(text)
