"""Coordination findings from reported schedule status."""

from datetime import datetime

from intelligence.models import CarePlan, DoseEvent, Finding, PatientRecord, Reading
from intelligence.rules import (
    coordination_priority,
    in_window,
    matching_rules,
    rule_is_approved_for,
    rule_min_occurrences,
)

# Names the record and catalog speak. Referenced so the import stays intact.
_MODELS = (CarePlan, DoseEvent, Finding, PatientRecord, Reading)


def evaluate_adherence(
    record: PatientRecord,
    as_of: datetime,
    catalog: dict,
) -> list[Finding]:
    """Return missed, unconfirmed, and repeated-gap findings at as_of."""
    _require_aware(as_of)
    findings: list[Finding] = []
    seen: set[str] = set()
    doses = sorted(
        list(record.doses or []),
        key=lambda dose: (dose.schedule_time, str(dose.medication_id)),
    )
    for dose in doses:
        _require_aware_moment(dose.schedule_time, "schedule_time")
        if dose.schedule_time > as_of:
            continue
        finding = _status_finding(dose, catalog)
        if finding is not None:
            _add(findings, seen, finding)
    for finding in _repeated_gaps(doses, record, as_of, catalog):
        _add(findings, seen, finding)
    return findings


def _status_finding(dose: DoseEvent, catalog: dict) -> Finding | None:
    status = dose.reported_status
    when = dose.schedule_time.isoformat()
    name = _medicine_name(dose)
    if status == "taken":
        return None
    if status == "missed":
        description = f"{name} was reported missed at {when}."
        if dose.reported_reason:
            description = f"{description} Reported reason: {dose.reported_reason}."
        return Finding(
            kind="adherence_missed",
            description=description,
            priority=coordination_priority(catalog, "missed_dose_priority"),
            dedupe_key=f"adherence:{dose.medication_id}:{when}",
            rule_id=None,
            evidence=_status_evidence(dose, when),
        )
    if status in (None, "unknown"):
        return Finding(
            kind="adherence_unconfirmed",
            description=f"{name} has no confirmation at {when}.",
            priority=coordination_priority(catalog, "unconfirmed_dose_priority"),
            dedupe_key=f"adherence-unconfirmed:{dose.medication_id}:{when}",
            rule_id=None,
            evidence=_status_evidence(dose, when),
        )
    return None


def _repeated_gaps(
    doses: list[DoseEvent],
    record: PatientRecord,
    as_of: datetime,
    catalog: dict,
) -> list[Finding]:
    findings: list[Finding] = []
    for rule in _adherence_rules(catalog):
        rule_id = str(_field(rule, "id"))
        minimum = rule_min_occurrences(rule)
        if minimum is None or not rule_is_approved_for(record, catalog, rule_id):
            continue
        grouped: dict[object, list[DoseEvent]] = {}
        for dose in doses:
            if dose.reported_status != "missed":
                continue
            if not in_window(dose.schedule_time, as_of, rule):
                continue
            grouped.setdefault(dose.medication_id, []).append(dose)
        priority = _field(rule, "priority")
        for medication_id, missed in sorted(grouped.items(), key=lambda item: str(item[0])):
            if len(missed) < minimum:
                continue
            missed.sort(key=lambda dose: dose.schedule_time)
            times = [dose.schedule_time.isoformat() for dose in missed]
            reasons = [dose.reported_reason for dose in missed]
            name = _medicine_name(missed[0])
            evidence: dict = {
                "medication_id": str(medication_id),
                "medication_name": name,
                "rule_id": rule_id,
                "count": len(missed),
                "window_hours": _field(rule, "window_hours"),
                "missed_schedule_times": times,
                "reported_reasons": reasons,
            }
            team = _field(rule, "team")
            if team:
                evidence["team"] = team
            findings.append(
                Finding(
                    kind="adherence_repeated_gap",
                    description=(
                        f"{name} has {len(missed)} missed reports in the review "
                        f"window for rule {rule_id}."
                    ),
                    priority=priority,
                    dedupe_key=f"adherence-gap:{medication_id}:{rule_id}",
                    rule_id=rule_id,
                    evidence=evidence,
                )
            )
    return findings


def _adherence_rules(catalog: dict) -> list:
    selected = []
    seen: set[str] = set()
    for rule in matching_rules(catalog, "adherence_missed"):
        rule_id = _field(rule, "id")
        if not rule_id or str(rule_id) in seen:
            continue
        if _field(rule, "approved") is False:
            continue
        metric = _field(rule, "metric")
        if metric not in (None, "adherence_missed"):
            continue
        seen.add(str(rule_id))
        selected.append(rule)
    return selected


def _status_evidence(dose: DoseEvent, when: str) -> dict:
    return {
        "medication_id": str(dose.medication_id),
        "medication_name": _medicine_name(dose),
        "schedule_time": when,
        "reported_status": dose.reported_status,
        "reported_reason": dose.reported_reason,
        "report_source": dose.report_source,
    }


def _medicine_name(dose: DoseEvent) -> str:
    if dose.medication_name:
        return str(dose.medication_name)
    return str(dose.medication_id)


def _add(findings: list[Finding], seen: set[str], finding: Finding) -> None:
    if finding.dedupe_key in seen:
        return
    seen.add(finding.dedupe_key)
    findings.append(finding)


def _field(rule: object, key: str):
    if isinstance(rule, dict):
        return rule.get(key)
    return getattr(rule, key, None)


def _require_aware(as_of: datetime) -> None:
    _require_aware_moment(as_of, "as_of")


def _require_aware_moment(moment: datetime, label: str) -> None:
    if not isinstance(moment, datetime) or moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
