"""Orchestrate care coordination for one patient record.

Domain modules produce findings. This module does not interpret
measurements, medicines, or doses. A finding with a rule id is kept
only when that rule is approved for the patient. A finding with no
rule id is a coordination finding and stays.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from intelligence.adherence import evaluate_adherence
from intelligence.blood_pressure import evaluate_blood_pressure
from intelligence.care_gaps import evaluate_care_gaps
from intelligence.consultations import evaluate_consultations
from intelligence.escalation import build_events
from intelligence.glucose import evaluate_glucose
from intelligence.models import (
    CareCoordinationEvent,
    EscalationRecord,
    Finding,
    IntelligenceResult,
    PatientRecord,
    PatientSummary,
    require_aware,
)
from intelligence.rules import rule_is_approved_for, validate_catalog
from intelligence.summary import build_summary


def evaluate(
    record: PatientRecord,
    as_of: datetime,
    catalog: dict[str, Any],
    existing_open_keys: set[str] | None = None,
) -> IntelligenceResult:
    """Evaluate one patient record as of a timezone-aware instant.

    Call order is adherence, glucose, blood pressure, consultations,
    then the approval gate, care gaps, the approval gate again,
    escalation, and summary. ``existing_open_keys`` is forwarded
    unchanged. The record and the catalog are left unchanged.
    """
    require_aware(as_of, "as_of")
    if not isinstance(record, PatientRecord):
        raise TypeError("record must be a PatientRecord")
    validate_catalog(catalog)
    _check_open_keys(existing_open_keys)

    domain = _with_approved_rules(
        _join_findings(
            ("adherence", evaluate_adherence(record, as_of, catalog)),
            ("glucose", evaluate_glucose(record, as_of, catalog)),
            ("blood_pressure", evaluate_blood_pressure(record, as_of, catalog)),
            ("consultations", evaluate_consultations(record, as_of, catalog)),
        ),
        record,
        catalog,
    )
    gaps = _with_approved_rules(
        _findings(evaluate_care_gaps(domain, record, as_of, catalog), "care_gaps"),
        record,
        catalog,
    )
    findings = [*domain, *gaps]
    events, history = _coordination_pair(
        build_events(findings, record, as_of, catalog, existing_open_keys)
    )
    events = _filter_ruled(events, record, catalog, CareCoordinationEvent, "events")
    history = _filter_ruled(
        history, record, catalog, EscalationRecord, "escalation_history"
    )
    summary = build_summary(record, events, as_of)
    if not isinstance(summary, PatientSummary):
        raise TypeError("build_summary must return a PatientSummary")
    return IntelligenceResult(
        findings=findings,
        events=events,
        summary=summary,
        escalation_history=history,
    )


def _check_open_keys(keys: set[str] | None) -> None:
    if keys is None:
        return
    if not isinstance(keys, set):
        raise TypeError("existing_open_keys must be a set or None")
    for key in keys:
        if not isinstance(key, str):
            raise TypeError("existing_open_keys must contain strings")


def _join_findings(*parts: tuple[str, object]) -> list[Finding]:
    findings: list[Finding] = []
    for name, values in parts:
        findings.extend(_findings(values, name))
    return findings


def _findings(values: object, source: str) -> list[Finding]:
    if values is None:
        raise TypeError(f"{source} must return findings")
    try:
        items = list(values)  # type: ignore[arg-type]
    except TypeError as exc:
        raise TypeError(f"{source} must return an iterable of Finding") from exc
    for item in items:
        if not isinstance(item, Finding):
            raise TypeError(f"{source} must return Finding values")
    return items


def _rule_allowed(rule_id: str | None, record: PatientRecord, catalog: dict[str, Any]) -> bool:
    if rule_id is None:
        return True
    return rule_is_approved_for(record, catalog, rule_id)


def _with_approved_rules(
    findings: list[Finding], record: PatientRecord, catalog: dict[str, Any]
) -> list[Finding]:
    return [
        finding
        for finding in findings
        if _rule_allowed(finding.rule_id, record, catalog)
    ]


def _coordination_pair(value: object) -> tuple[object, object]:
    if not isinstance(value, tuple):
        raise TypeError("build_events must return (events, escalation_history)")
    try:
        events, history = value
    except ValueError as exc:
        raise TypeError(
            "build_events must return (events, escalation_history)"
        ) from exc
    return events, history


def _filter_ruled(
    values: object,
    record: PatientRecord,
    catalog: dict[str, Any],
    kind: type,
    label: str,
) -> list[Any]:
    try:
        items = list(values)  # type: ignore[arg-type]
    except TypeError as exc:
        raise TypeError(f"{label} must be a list") from exc
    selected: list[Any] = []
    for item in items:
        if not isinstance(item, kind):
            raise TypeError(f"{label} must contain {kind.__name__} values")
        if _rule_allowed(item.rule_id, record, catalog):
            selected.append(item)
    return selected


__all__ = ["evaluate"]
