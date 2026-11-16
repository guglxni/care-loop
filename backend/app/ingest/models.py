"""Ingest tables. health_readings.ingest_origin is attached here, not on the chart model."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    Text,
    Uuid,
    func,
    literal_column,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UTCDateTime
from app.models import HealthReading, JSONDocument
from app.timeutil import to_iso, utcnow


def ensure_ingest_schema() -> None:
    """Add ingest_origin and the duplicate index to the existing health_readings table.

    The chart ORM model is left unchanged. Tests create tables from metadata, so the
    column has to be on that table before create_all. Inserts write ingest_origin
    explicitly.
    """
    table = HealthReading.__table__
    if "ingest_origin" not in table.c:
        table.append_column(Column("ingest_origin", Text(), nullable=True))
    if not any(
        constraint.name == "health_readings_ingest_origin_check" for constraint in table.constraints
    ):
        table.append_constraint(
            CheckConstraint(
                "ingest_origin IS NULL OR ingest_origin IN ('synthetic', 'manual', 'device')",
                name="health_readings_ingest_origin_check",
            )
        )
    if "health_readings_dedupe_uidx" not in table.indexes:
        Index(
            "health_readings_dedupe_uidx",
            table.c.patient_id,
            table.c.measurement_type,
            table.c.measured_at,
            table.c.source,
            func.coalesce(table.c.device_id, literal_column("''")),
            table.c.value,
            unique=True,
        )


class IngestSyncRun(Base):
    __tablename__ = "ingest_sync_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ok', 'unavailable', 'partial')",
            name="ingest_sync_runs_status_check",
        ),
        Index(
            "ingest_sync_runs_patient_id_started_at_idx",
            "patient_id",
            "started_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    connector: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    inserted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "patient_id": str(self.patient_id),
            "connector": self.connector,
            "status": self.status,
            "started_at": to_iso(self.started_at),
            "finished_at": to_iso(self.finished_at),
            "inserted_count": int(self.inserted_count),
            "duplicate_count": int(self.duplicate_count),
            "skipped_count": int(self.skipped_count),
            "message": self.message,
        }


class DocumentExtraction(Base):
    """Confirmed document extracts. The document route module owns the HTTP flow."""

    __tablename__ = "document_extractions"
    __table_args__ = (Index("document_extractions_patient_id_idx", "patient_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )
    document_type: Mapped[str] = mapped_column(Text, nullable=False)
    extracted: Mapped[dict] = mapped_column(JSONDocument, nullable=False, default=dict)
    confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "patient_id": str(self.patient_id),
            "document_id": str(self.document_id) if self.document_id else None,
            "document_type": self.document_type,
            "extracted": self.extracted,
            "confirmed": self.confirmed,
            "confirmed_at": to_iso(self.confirmed_at),
            "created_at": to_iso(self.created_at),
        }


ensure_ingest_schema()
