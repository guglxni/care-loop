"""Glucose and blood pressure rows. Out-of-range numbers are rejected, not labelled."""

from sqlalchemy.orm import Session

from app.models import HealthReading
from app.services.patient_service import get_patient
from app.validation import (
    optional_text,
    raise_if,
    reject_unknown_fields,
    require_choice,
    require_datetime,
    require_number,
    optional_number,
)

GLUCOSE_FIELDS = frozenset(
    {
        "value",
        "unit",
        "measurement_context",
        "measured_at",
        "source",
        "device_id",
        "support",
    }
)
GLUCOSE_UNITS = ("mg/dL", "mmol/L")
GLUCOSE_CONTEXTS = ("fasting", "post_meal", "other")
GLUCOSE_SOURCES = ("manual", "cgm", "glucometer")

BP_FIELDS = frozenset(
    {
        "systolic",
        "diastolic",
        "pulse",
        "unit",
        "measured_at",
        "source",
        "device_id",
    }
)
BP_SOURCES = ("manual", "home_monitor", "clinic")


def record_glucose(session: Session, patient_id: str, payload: dict) -> HealthReading:
    patient = get_patient(session, patient_id)
    details: list[str] = []
    reject_unknown_fields(payload, GLUCOSE_FIELDS, details)
    value = require_number(payload, "value", details)
    unit = require_choice(payload, "unit", GLUCOSE_UNITS, details)
    context = require_choice(payload, "measurement_context", GLUCOSE_CONTEXTS, details)
    measured_at = require_datetime(payload, "measured_at", details, reject_far_future=True)
    source = require_choice(payload, "source", GLUCOSE_SOURCES, details)
    device_id = optional_text(payload, "device_id", details, max_length=200)
    support = optional_text(payload, "support", details, max_length=500)
    if value is not None and unit == "mg/dL" and not (value > 20 and value < 600):
        details.append("value must be greater than 20 and less than 600 for mg/dL")
    if value is not None and unit == "mmol/L" and not (value > 1 and value < 33):
        details.append("value must be greater than 1 and less than 33 for mmol/L")
    raise_if(details)
    row = HealthReading(
        patient_id=patient.id,
        measurement_type="blood_glucose",
        value=value,
        secondary_value=None,
        unit=unit,
        measurement_context=context,
        measured_at=measured_at,
        source=source,
        device_id=device_id,
        data_quality="valid",
        support=support,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def record_blood_pressure(session: Session, patient_id: str, payload: dict) -> list[HealthReading]:
    patient = get_patient(session, patient_id)
    details: list[str] = []
    reject_unknown_fields(payload, BP_FIELDS, details)
    systolic = require_number(payload, "systolic", details)
    diastolic = require_number(payload, "diastolic", details)
    pulse = optional_number(payload, "pulse", details)
    unit = require_choice(payload, "unit", ("mmHg",), details)
    measured_at = require_datetime(payload, "measured_at", details, reject_far_future=True)
    source = require_choice(payload, "source", BP_SOURCES, details)
    device_id = optional_text(payload, "device_id", details, max_length=200)
    if systolic is not None and not (70 <= systolic <= 250):
        details.append("systolic must be between 70 and 250")
    if diastolic is not None and not (40 <= diastolic <= 150):
        details.append("diastolic must be between 40 and 150")
    if systolic is not None and diastolic is not None and not systolic > diastolic:
        details.append("systolic must be greater than diastolic")
    if pulse is not None and not (30 <= pulse <= 220):
        details.append("pulse must be between 30 and 220")
    raise_if(details)
    assert systolic is not None and diastolic is not None and measured_at is not None
    shared = {
        "patient_id": patient.id,
        "measured_at": measured_at,
        "source": source,
        "device_id": device_id,
        "data_quality": "valid",
        "measurement_context": None,
        "support": None,
    }
    rows = [
        HealthReading(
            measurement_type="systolic_blood_pressure",
            value=systolic,
            secondary_value=diastolic,
            unit=unit,
            **shared,
        ),
        HealthReading(
            measurement_type="diastolic_blood_pressure",
            value=diastolic,
            secondary_value=None,
            unit=unit,
            **shared,
        ),
    ]
    if pulse is not None:
        rows.append(
            HealthReading(
                measurement_type="pulse",
                value=pulse,
                secondary_value=None,
                unit="bpm",
                **shared,
            )
        )
    session.add_all(rows)
    session.commit()
    for row in rows:
        session.refresh(row)
    return rows
