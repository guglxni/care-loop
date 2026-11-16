"""Care-coordination records.

Construct every record with keyword arguments. The engine stores chart
facts and coordination results. It does not diagnose, prescribe, or
choose a dose.

``reading_origin`` maps a reading source onto the summary label:

- manual -> patient_reported
- cgm, glucometer, home_monitor -> device_recorded
- clinic -> staff_recorded
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import date, datetime
from types import MappingProxyType
from typing import Any, Mapping
from uuid import UUID

PRIORITIES = frozenset({"low", "medium", "high"})
REPORTED_STATUSES = frozenset({"taken", "missed", "unknown"})
REPORT_SOURCES = frozenset({"app", "call_self_report", "inferred"})
MEASUREMENT_TYPES = frozenset(
    {
        "blood_glucose",
        "systolic_blood_pressure",
        "diastolic_blood_pressure",
        "pulse",
        "weight",
    }
)
MEASUREMENT_CONTEXTS = frozenset({"fasting", "post_meal", "other", "resting"})
READING_SOURCES = frozenset({"manual", "cgm", "glucometer", "home_monitor", "clinic"})
DATA_QUALITIES = frozenset({"valid", "questionable", "rejected"})
CONSULTATION_TYPES = frozenset({"consultation", "laboratory", "follow_up"})
CONSULTATION_STATUSES = frozenset(
    {"scheduled", "completed", "cancelled", "rescheduled"}
)
READING_ORIGINS = frozenset(
    {"patient_reported", "device_recorded", "staff_recorded"}
)
SOURCE_TO_ORIGIN: Mapping[str, str] = MappingProxyType(
    {
        "manual": "patient_reported",
        "cgm": "device_recorded",
        "glucometer": "device_recorded",
        "home_monitor": "device_recorded",
        "clinic": "staff_recorded",
    }
)
_SUMMARY_KEYS = ("recent_readings", "adherence", "outstanding_tasks")


def require_aware(value: datetime, field_name: str) -> datetime:
    """Return ``value`` when it is a timezone-aware datetime."""
    if not isinstance(value, datetime):
        raise TypeError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


def reading_origin(source: str) -> str:
    """Map a reading source to the summary origin label.

    manual -> patient_reported
    cgm, glucometer, and home_monitor -> device_recorded
    clinic -> staff_recorded

    ``source`` is the reading source string. A non-string raises TypeError.
    """
    if not isinstance(source, str):
        raise TypeError("source must be a string")
    try:
        return SOURCE_TO_ORIGIN[source]
    except KeyError as exc:
        raise ValueError(f"unknown reading source: {source}") from exc


def to_jsonable(value: Any) -> Any:
    """Return a JSON-serializable copy. Aware datetimes become ISO strings."""
    if value is None or isinstance(value, str) or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("evidence numbers must be finite")
        return value
    if isinstance(value, datetime):
        return require_aware(value, "evidence datetime").isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        ready: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("evidence object keys must be strings")
            ready[key] = to_jsonable(item)
        return ready
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    raise TypeError(f"{type(value).__name__} is not JSON-serializable")


def _text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError(f"{field_name} must be a non-empty string")


def _choice(value: object, allowed: frozenset[str], field_name: str) -> None:
    if not isinstance(value, str) or value not in allowed:
        names = ", ".join(sorted(allowed))
        raise ValueError(f"{field_name} must be one of: {names}")


def _optional_choice(
    value: object, allowed: frozenset[str], field_name: str
) -> None:
    if value is None:
        return
    _choice(value, allowed, field_name)


def _finite(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite")
    return number


def _object_dict(value: object, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{field_name} must be a dict")
    return dict(value)


def _instances(values: object, kind: type, field_name: str) -> list[Any]:
    if not isinstance(values, list):
        raise TypeError(f"{field_name} must be a list")
    for item in values:
        if not isinstance(item, kind):
            raise TypeError(f"{field_name} must contain {kind.__name__} values")
    return list(values)


def _iso_timestamp(value: datetime | str, field_name: str) -> str:
    if isinstance(value, datetime):
        return require_aware(value, field_name).isoformat()
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be an ISO timestamp") from exc
        return require_aware(parsed, field_name).isoformat()
    raise TypeError(f"{field_name} must be a timezone-aware datetime or ISO string")


def _set(record: object, name: str, value: object) -> None:
    object.__setattr__(record, name, value)


@dataclass(frozen=True, slots=True, kw_only=True)
class DoseEvent:
    """One scheduled dose and any report collected for that slot.

    ``reported_status`` is None when the slot is still unconfirmed.
    ``taken``, ``missed``, and ``unknown`` are reports, not dose instructions.
    """

    medication_id: str
    medication_name: str
    prescribed_dosage: str
    schedule_time: datetime
    reported_status: str | None = None
    reported_reason: str | None = None
    report_source: str | None = None

    def __post_init__(self) -> None:
        _text(self.medication_id, "medication_id")
        _text(self.medication_name, "medication_name")
        _text(self.prescribed_dosage, "prescribed_dosage")
        require_aware(self.schedule_time, "schedule_time")
        _optional_choice(self.reported_status, REPORTED_STATUSES, "reported_status")
        if self.reported_reason is not None:
            _text(self.reported_reason, "reported_reason")
        _optional_choice(self.report_source, REPORT_SOURCES, "report_source")


@dataclass(frozen=True, slots=True, kw_only=True)
class Reading:
    """One recorded measurement. The value is stored as reported."""

    measurement_type: str
    value: float
    secondary_value: float | None = None
    unit: str
    measurement_context: str | None = None
    measured_at: datetime
    source: str
    data_quality: str

    def __post_init__(self) -> None:
        _choice(self.measurement_type, MEASUREMENT_TYPES, "measurement_type")
        _set(self, "value", _finite(self.value, "value"))
        if self.secondary_value is not None:
            _set(self, "secondary_value", _finite(self.secondary_value, "secondary_value"))
        _text(self.unit, "unit")
        _optional_choice(
            self.measurement_context, MEASUREMENT_CONTEXTS, "measurement_context"
        )
        require_aware(self.measured_at, "measured_at")
        _choice(self.source, READING_SOURCES, "source")
        _choice(self.data_quality, DATA_QUALITIES, "data_quality")


@dataclass(frozen=True, slots=True, kw_only=True)
class Consultation:
    """A scheduled, completed, cancelled, or rescheduled care appointment."""

    id: str
    clinician: str
    appointment_date: datetime
    consultation_type: str
    status: str

    def __post_init__(self) -> None:
        _text(self.id, "id")
        _text(self.clinician, "clinician")
        require_aware(self.appointment_date, "appointment_date")
        _choice(self.consultation_type, CONSULTATION_TYPES, "consultation_type")
        _choice(self.status, CONSULTATION_STATUSES, "status")


@dataclass(frozen=True, slots=True, kw_only=True)
class CarePlan:
    """A clinician-authored plan and the rule ids it allows for this patient."""

    id: str
    condition: str
    monitoring_schedule: dict[str, Any]
    approved_rule_ids: list[str]
    escalation_protocol: dict[str, Any]

    def __post_init__(self) -> None:
        _text(self.id, "id")
        _text(self.condition, "condition")
        _set(self, "monitoring_schedule", _object_dict(self.monitoring_schedule, "monitoring_schedule"))
        _set(self, "escalation_protocol", _object_dict(self.escalation_protocol, "escalation_protocol"))
        if not isinstance(self.approved_rule_ids, list):
            raise TypeError("approved_rule_ids must be a list")
        rule_ids: list[str] = []
        for rule_id in self.approved_rule_ids:
            _text(rule_id, "approved_rule_ids entry")
            rule_ids.append(rule_id)
        _set(self, "approved_rule_ids", rule_ids)


@dataclass(frozen=True, slots=True, kw_only=True)
class PatientRecord:
    """Chart facts the coordination engine is allowed to read."""

    patient_id: str
    preferred_name: str
    doses: list[DoseEvent] = field(default_factory=list)
    readings: list[Reading] = field(default_factory=list)
    consultations: list[Consultation] = field(default_factory=list)
    care_plans: list[CarePlan] = field(default_factory=list)

    def __post_init__(self) -> None:
        _text(self.patient_id, "patient_id")
        _text(self.preferred_name, "preferred_name")
        _set(self, "doses", _instances(self.doses, DoseEvent, "doses"))
        _set(self, "readings", _instances(self.readings, Reading, "readings"))
        _set(
            self,
            "consultations",
            _instances(self.consultations, Consultation, "consultations"),
        )
        _set(self, "care_plans", _instances(self.care_plans, CarePlan, "care_plans"))

    def listed_rule_ids(self) -> set[str]:
        """Rule ids present on any care plan for this patient."""
        selected: set[str] = set()
        for plan in self.care_plans:
            selected.update(plan.approved_rule_ids)
        return selected


@dataclass(frozen=True, slots=True, kw_only=True)
class Finding:
    """A coordination fact. ``rule_id`` is None for a coordination finding.

    ``evidence`` is stored JSON-serializable. Datetimes are ISO strings.
    """

    kind: str
    description: str
    priority: str
    dedupe_key: str
    rule_id: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _text(self.kind, "kind")
        _text(self.description, "description")
        _choice(self.priority, PRIORITIES, "priority")
        _text(self.dedupe_key, "dedupe_key")
        if self.rule_id is not None:
            _text(self.rule_id, "rule_id")
        if not isinstance(self.evidence, dict):
            raise TypeError("evidence must be a dict")
        ready = to_jsonable(self.evidence)
        json.dumps(ready, allow_nan=False)
        _set(self, "evidence", ready)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "description": self.description,
            "priority": self.priority,
            "dedupe_key": self.dedupe_key,
            "rule_id": self.rule_id,
            "evidence": self.evidence,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class CareCoordinationEvent:
    """An open item for a care team. Review by a person is required."""

    event_type: str
    event_description: str
    priority: str
    dedupe_key: str
    rule_id: str | None = None
    team: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    status: str = "open"
    requires_human_review: bool = True

    def __post_init__(self) -> None:
        _text(self.event_type, "event_type")
        _text(self.event_description, "event_description")
        _choice(self.priority, PRIORITIES, "priority")
        _text(self.dedupe_key, "dedupe_key")
        if self.rule_id is not None:
            _text(self.rule_id, "rule_id")
        if self.team is not None:
            _text(self.team, "team")
        if not isinstance(self.evidence, dict):
            raise TypeError("evidence must be a dict")
        if self.status != "open":
            raise ValueError("care coordination events start open")
        if self.requires_human_review is not True:
            raise ValueError("care coordination events require human review")
        ready = to_jsonable(self.evidence)
        json.dumps(ready, allow_nan=False)
        _set(self, "evidence", ready)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "event_description": self.event_description,
            "priority": self.priority,
            "status": self.status,
            "dedupe_key": self.dedupe_key,
            "rule_id": self.rule_id,
            "team": self.team,
            "evidence": self.evidence,
            "requires_human_review": self.requires_human_review,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class EscalationRecord:
    """One escalation row opened for a care team."""

    dedupe_key: str
    rule_id: str | None
    team: str
    priority: str
    opened_at: datetime
    status: str

    def __post_init__(self) -> None:
        _text(self.dedupe_key, "dedupe_key")
        if self.rule_id is not None:
            _text(self.rule_id, "rule_id")
        _text(self.team, "team")
        _choice(self.priority, PRIORITIES, "priority")
        require_aware(self.opened_at, "opened_at")
        _text(self.status, "status")

    def to_dict(self) -> dict[str, Any]:
        return {
            "dedupe_key": self.dedupe_key,
            "rule_id": self.rule_id,
            "team": self.team,
            "priority": self.priority,
            "opened_at": self.opened_at.isoformat(),
            "status": self.status,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class SummaryReading:
    """One summary row. ``measured_at`` is an ISO timestamp."""

    measurement_type: str
    value: float
    secondary_value: float | None
    unit: str
    context: str | None
    measured_at: str
    source: str
    origin: str

    def __post_init__(self) -> None:
        _choice(self.measurement_type, MEASUREMENT_TYPES, "measurement_type")
        _set(self, "value", _finite(self.value, "value"))
        if self.secondary_value is not None:
            _set(self, "secondary_value", _finite(self.secondary_value, "secondary_value"))
        _text(self.unit, "unit")
        _optional_choice(self.context, MEASUREMENT_CONTEXTS, "context")
        _set(self, "measured_at", _iso_timestamp(self.measured_at, "measured_at"))
        _choice(self.source, READING_SOURCES, "source")
        _choice(self.origin, READING_ORIGINS, "origin")
        expected = reading_origin(self.source)
        if self.origin != expected:
            raise ValueError(
                f"origin {self.origin!r} does not match source {self.source!r}"
            )

    @classmethod
    def from_reading(cls, reading: Reading) -> SummaryReading:
        """Build a summary row from a chart reading."""
        return cls(
            measurement_type=reading.measurement_type,
            value=reading.value,
            secondary_value=reading.secondary_value,
            unit=reading.unit,
            context=reading.measurement_context,
            measured_at=reading.measured_at,
            source=reading.source,
            origin=reading_origin(reading.source),
        )

    def __getitem__(self, key: str) -> Any:
        if key == "measurement_context":
            return self.context
        if key not in {
            "measurement_type",
            "value",
            "secondary_value",
            "unit",
            "context",
            "measured_at",
            "source",
            "origin",
        }:
            raise KeyError(key)
        return getattr(self, key)

    def to_dict(self) -> dict[str, Any]:
        return {
            "measurement_type": self.measurement_type,
            "value": self.value,
            "secondary_value": self.secondary_value,
            "unit": self.unit,
            "context": self.context,
            "measured_at": self.measured_at,
            "source": self.source,
            "origin": self.origin,
        }


def _summary_reading(value: object) -> SummaryReading:
    if isinstance(value, SummaryReading):
        return value
    if isinstance(value, dict):
        try:
            if "context" in value:
                context = value.get("context")
            else:
                context = value.get("measurement_context")
            return SummaryReading(
                measurement_type=value["measurement_type"],
                value=value["value"],
                secondary_value=value.get("secondary_value"),
                unit=value["unit"],
                context=context,
                measured_at=value["measured_at"],
                source=value["source"],
                origin=value["origin"],
            )
        except KeyError as exc:
            raise TypeError("recent_readings entries are missing a field") from exc
    raise TypeError("recent_readings must contain SummaryReading values")


@dataclass(frozen=True, slots=True, kw_only=True)
class PatientSummary:
    """Dict-like summary with recent readings, adherence, and open tasks.

    ``summary["recent_readings"]`` returns the same list as the attribute.
    ``to_dict`` serializes each reading, including its origin and ISO time.
    ``adherence`` and ``outstanding_tasks`` are JSON-serializable.
    """

    recent_readings: list[SummaryReading]
    adherence: dict[str, Any]
    outstanding_tasks: list[Any]

    def __post_init__(self) -> None:
        if not isinstance(self.recent_readings, list):
            raise TypeError("recent_readings must be a list")
        if not isinstance(self.adherence, dict):
            raise TypeError("adherence must be a dict")
        if not isinstance(self.outstanding_tasks, list):
            raise TypeError("outstanding_tasks must be a list")
        readings = [_summary_reading(item) for item in self.recent_readings]
        adherence = to_jsonable(self.adherence)
        tasks = to_jsonable(self.outstanding_tasks)
        json.dumps(
            {"adherence": adherence, "outstanding_tasks": tasks},
            allow_nan=False,
        )
        _set(self, "recent_readings", readings)
        _set(self, "adherence", adherence)
        _set(self, "outstanding_tasks", tasks)

    def __getitem__(self, key: str) -> Any:
        if key not in _SUMMARY_KEYS:
            raise KeyError(key)
        return getattr(self, key)

    def __iter__(self):
        return iter(_SUMMARY_KEYS)

    def __len__(self) -> int:
        return len(_SUMMARY_KEYS)

    def keys(self):
        return _SUMMARY_KEYS

    def to_dict(self) -> dict[str, Any]:
        return {
            "recent_readings": [reading.to_dict() for reading in self.recent_readings],
            "adherence": self.adherence,
            "outstanding_tasks": self.outstanding_tasks,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class IntelligenceResult:
    """Findings, care-coordination events, summary, and escalation history."""

    findings: list[Finding]
    events: list[CareCoordinationEvent]
    summary: PatientSummary
    escalation_history: list[EscalationRecord]

    def __post_init__(self) -> None:
        _set(self, "findings", _instances(self.findings, Finding, "findings"))
        _set(self, "events", _instances(self.events, CareCoordinationEvent, "events"))
        if not isinstance(self.summary, PatientSummary):
            raise TypeError("summary must be a PatientSummary")
        _set(
            self,
            "escalation_history",
            _instances(self.escalation_history, EscalationRecord, "escalation_history"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "findings": [finding.to_dict() for finding in self.findings],
            "events": [event.to_dict() for event in self.events],
            "summary": self.summary.to_dict(),
            "escalation_history": [row.to_dict() for row in self.escalation_history],
        }


__all__ = [
    "PRIORITIES",
    "REPORTED_STATUSES",
    "REPORT_SOURCES",
    "MEASUREMENT_TYPES",
    "MEASUREMENT_CONTEXTS",
    "READING_SOURCES",
    "DATA_QUALITIES",
    "CONSULTATION_TYPES",
    "CONSULTATION_STATUSES",
    "READING_ORIGINS",
    "SOURCE_TO_ORIGIN",
    "require_aware",
    "reading_origin",
    "to_jsonable",
    "DoseEvent",
    "Reading",
    "Consultation",
    "CarePlan",
    "PatientRecord",
    "Finding",
    "CareCoordinationEvent",
    "EscalationRecord",
    "SummaryReading",
    "PatientSummary",
    "IntelligenceResult",
]
