"""Chart tables. Column names match supabase/migrations/0001_init.sql."""

import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, Date, ForeignKey, Numeric, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UTCDateTime
from app.timeutil import json_number, to_iso, utcnow

JSONDocument = JSON().with_variant(JSONB(), "postgresql")


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _uuid_fk(target: str) -> Mapped[uuid.UUID]:
    return mapped_column(Uuid(as_uuid=True), ForeignKey(target), nullable=False, index=True)


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = _uuid_pk()
    preferred_name: Mapped[str] = mapped_column(Text, nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    preferred_language: Mapped[str] = mapped_column(Text, nullable=False)
    contact_number: Mapped[str] = mapped_column(Text, nullable=False)
    medical_history: Mapped[str] = mapped_column(Text, nullable=False, default="")
    allergies: Mapped[list] = mapped_column(JSONDocument, nullable=False, default=list)
    emergency_contact: Mapped[dict] = mapped_column(JSONDocument, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    def to_profile(self) -> dict:
        return {
            "id": str(self.id),
            "preferred_name": self.preferred_name,
            "date_of_birth": self.date_of_birth.isoformat(),
            "preferred_language": self.preferred_language,
            "contact_number": self.contact_number,
            "medical_history": self.medical_history,
            "allergies": self.allergies,
            "emergency_contact": self.emergency_contact,
            "created_at": to_iso(self.created_at),
            "updated_at": to_iso(self.updated_at),
        }


class Condition(Base):
    __tablename__ = "conditions"
    __table_args__ = (
        CheckConstraint(
            "condition_type IN ('type_2_diabetes', 'hypertension')",
            name="ck_conditions_condition_type",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = _uuid_fk("patients.id")
    condition_type: Mapped[str] = mapped_column(Text, nullable=False)
    diagnosis_date: Mapped[date] = mapped_column(Date, nullable=False)
    treating_clinician: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "patient_id": str(self.patient_id),
            "condition_type": self.condition_type,
            "diagnosis_date": self.diagnosis_date.isoformat(),
            "treating_clinician": self.treating_clinician,
            "created_at": to_iso(self.created_at),
        }


class Medication(Base):
    __tablename__ = "medications"

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = _uuid_fk("patients.id")
    medication_name: Mapped[str] = mapped_column(Text, nullable=False)
    prescribed_dosage: Mapped[str] = mapped_column(Text, nullable=False)
    frequency: Mapped[str] = mapped_column(Text, nullable=False)
    schedule: Mapped[dict] = mapped_column(JSONDocument, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    prescribing_clinician: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "patient_id": str(self.patient_id),
            "medication_name": self.medication_name,
            "prescribed_dosage": self.prescribed_dosage,
            "frequency": self.frequency,
            "schedule": self.schedule,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "prescribing_clinician": self.prescribing_clinician,
            "active": self.active,
            "created_at": to_iso(self.created_at),
        }


class HealthReading(Base):
    __tablename__ = "health_readings"
    __table_args__ = (
        CheckConstraint(
            "measurement_type IN ("
            "'blood_glucose', 'systolic_blood_pressure', 'diastolic_blood_pressure', 'pulse', 'weight'"
            ")",
            name="ck_health_readings_measurement_type",
        ),
        CheckConstraint(
            "measurement_context IS NULL OR measurement_context IN "
            "('fasting', 'post_meal', 'other', 'resting')",
            name="ck_health_readings_measurement_context",
        ),
        CheckConstraint(
            "data_quality IN ('valid', 'questionable', 'rejected')",
            name="ck_health_readings_data_quality",
        ),
        CheckConstraint(
            "source IN ('manual', 'cgm', 'glucometer', 'home_monitor', 'clinic')",
            name="ck_health_readings_source",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = _uuid_fk("patients.id")
    measurement_type: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[float] = mapped_column(Numeric(), nullable=False)
    secondary_value: Mapped[float | None] = mapped_column(Numeric(), nullable=True)
    unit: Mapped[str] = mapped_column(Text, nullable=False)
    measurement_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    measured_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    device_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_quality: Mapped[str] = mapped_column(Text, nullable=False, default="valid")
    support: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "patient_id": str(self.patient_id),
            "measurement_type": self.measurement_type,
            "value": json_number(self.value),
            "secondary_value": json_number(self.secondary_value),
            "unit": self.unit,
            "measurement_context": self.measurement_context,
            "measured_at": to_iso(self.measured_at),
            "source": self.source,
            "device_id": self.device_id,
            "data_quality": self.data_quality,
            "support": self.support,
            "created_at": to_iso(self.created_at),
        }


class Consultation(Base):
    __tablename__ = "consultations"
    __table_args__ = (
        CheckConstraint(
            "consultation_type IN ('consultation', 'laboratory', 'follow_up')",
            name="ck_consultations_consultation_type",
        ),
        CheckConstraint(
            "status IN ('scheduled', 'completed', 'cancelled', 'rescheduled')",
            name="ck_consultations_status",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = _uuid_fk("patients.id")
    clinician: Mapped[str] = mapped_column(Text, nullable=False)
    appointment_date: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    consultation_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "patient_id": str(self.patient_id),
            "clinician": self.clinician,
            "appointment_date": to_iso(self.appointment_date),
            "consultation_type": self.consultation_type,
            "status": self.status,
            "created_at": to_iso(self.created_at),
            "updated_at": to_iso(self.updated_at),
        }


class CarePlan(Base):
    __tablename__ = "care_plans"

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = _uuid_fk("patients.id")
    condition: Mapped[str] = mapped_column(Text, nullable=False)
    monitoring_schedule: Mapped[dict] = mapped_column(JSONDocument, nullable=False, default=dict)
    clinician: Mapped[str] = mapped_column(Text, nullable=False)
    approved_rules: Mapped[list] = mapped_column(JSONDocument, nullable=False, default=list)
    escalation_protocol: Mapped[dict] = mapped_column(JSONDocument, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)

    def to_summary(self) -> dict:
        return {
            "id": str(self.id),
            "patient_id": str(self.patient_id),
            "condition": self.condition,
            "monitoring_schedule": self.monitoring_schedule,
            "clinician": self.clinician,
            "created_at": to_iso(self.created_at),
        }


class AdherenceLog(Base):
    __tablename__ = "adherence_logs"
    __table_args__ = (
        CheckConstraint(
            "reported_status IN ('taken', 'missed', 'unknown')",
            name="ck_adherence_logs_reported_status",
        ),
        CheckConstraint(
            "source IN ('app', 'call_self_report', 'inferred')",
            name="ck_adherence_logs_source",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = _uuid_fk("patients.id")
    medication_id: Mapped[uuid.UUID] = _uuid_fk("medications.id")
    schedule_time: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    reported_status: Mapped[str] = mapped_column(Text, nullable=False)
    reported_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    source: Mapped[str] = mapped_column(Text, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "patient_id": str(self.patient_id),
            "medication_id": str(self.medication_id),
            "schedule_time": to_iso(self.schedule_time),
            "reported_status": self.reported_status,
            "reported_reason": self.reported_reason,
            "recorded_at": to_iso(self.recorded_at),
            "source": self.source,
        }


class CareEvent(Base):
    __tablename__ = "care_events"
    __table_args__ = (
        CheckConstraint(
            "priority IN ('low', 'medium', 'high')",
            name="ck_care_events_priority",
        ),
        CheckConstraint(
            "status IN ('open', 'acknowledged', 'resolved')",
            name="ck_care_events_status",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = _uuid_fk("patients.id")
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    event_description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "patient_id": str(self.patient_id),
            "event_type": self.event_type,
            "event_description": self.event_description,
            "priority": self.priority,
            "status": self.status,
            "created_at": to_iso(self.created_at),
            "resolved_at": to_iso(self.resolved_at),
        }


class VoiceCall(Base):
    __tablename__ = "voice_calls"
    __table_args__ = (
        CheckConstraint(
            "call_type IN ('outbound', 'inbound')",
            name="ck_voice_calls_call_type",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = _uuid_fk("patients.id")
    bolna_call_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    call_type: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False)
    call_status: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_data: Mapped[dict] = mapped_column(JSONDocument, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "patient_id": str(self.patient_id),
            "bolna_call_id": self.bolna_call_id,
            "call_type": self.call_type,
            "language": self.language,
            "call_status": self.call_status,
            "summary": self.summary,
            "extracted_data": self.extracted_data,
            "created_at": to_iso(self.created_at),
        }


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id: Mapped[uuid.UUID] = _uuid_pk()
    bolna_call_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    delivery_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    payload: Mapped[dict] = mapped_column(JSONDocument, nullable=False)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)


class PatientKnowledgeLink(Base):
    """One scrape path per chart. bolna_knowledgebase_id is filled elsewhere."""

    __tablename__ = "patient_knowledge_links"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id"), primary_key=True
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    bolna_knowledgebase_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_built_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    def to_dict(self) -> dict:
        return {
            "patient_id": str(self.patient_id),
            "source_url": self.source_url,
            "bolna_knowledgebase_id": self.bolna_knowledgebase_id,
            "last_built_at": to_iso(self.last_built_at),
        }


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "document_type IN ('prescription', 'lab_report')",
            name="ck_documents_document_type",
        ),
        CheckConstraint(
            "extraction_status IN ('pending', 'extracted', 'failed', 'not_requested')",
            name="ck_documents_extraction_status",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = _uuid_fk("patients.id")
    document_type: Mapped[str] = mapped_column(Text, nullable=False)
    file_location: Mapped[str] = mapped_column(Text, nullable=False)
    extraction_status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "patient_id": str(self.patient_id),
            "document_type": self.document_type,
            "file_location": self.file_location,
            "extraction_status": self.extraction_status,
            "created_at": to_iso(self.created_at),
        }
