"""Group existing findings into care-coordination tasks.

The repeated-gap number is a grouping count from the catalog. It is not a
clinical threshold. This module does not diagnose, prescribe, recommend taking
a medicine, or change a dose.
"""

from datetime import datetime

from intelligence.escalation import guard_description, new_model
from intelligence.models import Finding, PatientRecord

_MONITORING_KINDS = frozenset({"glucose_missing", "bp_missing"})
_PENDING_KINDS = frozenset({"consultation_overdue", "laboratory_pending"})
_ADHERENCE_KIND = "adherence_repeated_gap"
_RECURRING_TEXT = "Recurring reported adherence gap for care coordination review."
_REASON_KEYS = frozenset({"reported_reason", "reason"})
_REASON_LIST_KEYS = frozenset({"reported_reasons", "reasons"})
_MISSING = object()


def evaluate_care_gaps(
    findings: list[Finding],
    record: PatientRecord,
    as_of: datetime,
    catalog: dict,
) -> list[Finding]:
    """Return new coordination findings only.

    `as_of` is the evaluation clock already applied by the findings. This
    function does not add a clinical cutoff.
    """
    patient_id = str(_attr(record, "patient_id"))
    clock = _iso(as_of)
    created: list[Finding] = []
    created.extend(_monitoring_gap(findings, patient_id, clock, catalog))
    adherence = _adherence_concern(findings, patient_id, clock)
    if adherence is not None:
        created.append(adherence)
    created.extend(_pending_tasks(findings, patient_id, clock))
    return created


def _monitoring_gap(
    findings: list[Finding],
    patient_id: str,
    clock: str,
    catalog: dict,
) -> list[Finding]:
    grouping_count = _grouping_count(catalog)
    monitoring = [finding for finding in findings if _kind(finding) in _MONITORING_KINDS]
    if len(monitoring) < grouping_count:
        return []
    dedupe_keys = [_dedupe(finding) for finding in monitoring]
    return [
        _finding(
            patient_id=patient_id,
            kind="repeated_monitoring_gap",
            priority="medium",
            rule_id=None,
            dedupe_key=f"gap:monitoring:{patient_id}",
            description="Repeated monitoring gap grouped for care coordination review.",
            evidence={
                "dedupe_keys": dedupe_keys,
                "repeated_gap_count": grouping_count,
                "as_of": clock,
            },
        )
    ]


def _adherence_concern(
    findings: list[Finding],
    patient_id: str,
    clock: str,
) -> Finding | None:
    matches = [finding for finding in findings if _kind(finding) == _ADHERENCE_KIND]
    if not matches:
        return None
    primary = matches[0]
    evidence = {"as_of": clock}
    reasons: list[str] = []
    for finding in matches:
        source = _evidence(finding)
        if isinstance(source, dict):
            for key, value in source.items():
                evidence.setdefault(key, value)
        reasons.extend(_reasons(source))
    unique_reasons = _unique(reasons)
    if unique_reasons:
        evidence["reported_reasons"] = unique_reasons
    description = _RECURRING_TEXT
    if unique_reasons:
        candidate = f"{_RECURRING_TEXT} Reported reasons: {'; '.join(unique_reasons)}."
        if guard_description(candidate, kind="recurring_adherence_concern") == candidate:
            description = candidate
    return _finding(
        patient_id=patient_id,
        kind="recurring_adherence_concern",
        priority=_attr(primary, "priority"),
        rule_id=_rule_id(primary),
        dedupe_key=f"gap:adherence:{patient_id}",
        description=description,
        evidence=evidence,
    )


def _pending_tasks(findings: list[Finding], patient_id: str, clock: str) -> list[Finding]:
    tasks: list[Finding] = []
    for finding in findings:
        kind = _kind(finding)
        if kind not in _PENDING_KINDS:
            continue
        underlying = _dedupe(finding)
        if kind == "consultation_overdue":
            description = f"Pending care task open after overdue consultation {underlying}."
        else:
            description = f"Pending care task open for pending laboratory {underlying}."
        tasks.append(
            _finding(
                patient_id=patient_id,
                kind="pending_care_task",
                priority=_attr(finding, "priority"),
                rule_id=None,
                dedupe_key=f"gap:{underlying}",
                description=description,
                evidence={
                    "underlying_dedupe_key": underlying,
                    "underlying_kind": kind,
                    "as_of": clock,
                },
            )
        )
    return tasks


def _grouping_count(catalog: dict) -> int:
    defaults = {}
    if isinstance(catalog, dict):
        raw_defaults = catalog.get("coordination_defaults") or {}
        if isinstance(raw_defaults, dict):
            defaults = raw_defaults
    raw = defaults.get("repeated_gap_count", 2)
    try:
        count = int(raw)
    except (TypeError, ValueError):
        return 2
    if count < 1:
        return 2
    return count


def _reasons(value: object) -> list[str]:
    found: list[str] = []
    _collect_reasons(value, found)
    return found


def _collect_reasons(value: object, found: list[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _REASON_KEYS and isinstance(item, str) and item.strip():
                found.append(item.strip())
            elif key in _REASON_LIST_KEYS and isinstance(item, list):
                for entry in item:
                    if isinstance(entry, str) and entry.strip():
                        found.append(entry.strip())
                    else:
                        _collect_reasons(entry, found)
            else:
                _collect_reasons(item, found)
    elif isinstance(value, list):
        for item in value:
            _collect_reasons(item, found)


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _finding(
    *,
    patient_id: str,
    kind: str,
    priority: object,
    rule_id: str | None,
    dedupe_key: str,
    description: str,
    evidence: dict,
) -> Finding:
    safe = guard_description(description, kind=kind)
    return new_model(
        Finding,
        id=f"{kind}:{dedupe_key}",
        patient_id=patient_id,
        kind=kind,
        priority=priority,
        rule_id=rule_id,
        dedupe_key=dedupe_key,
        description=safe,
        event_description=safe,
        evidence=evidence,
    )


def _kind(finding: Finding) -> str:
    value = _attr(finding, "kind", "finding_kind", "finding_type")
    if value is _MISSING or value is None:
        return ""
    return str(value)


def _dedupe(finding: Finding) -> str:
    value = _attr(finding, "dedupe_key")
    if value is _MISSING or value is None:
        return ""
    return str(value)


def _rule_id(finding: Finding) -> str | None:
    value = _attr(finding, "rule_id")
    if value is _MISSING or value is None:
        return None
    text = str(value).strip()
    return text or None


def _evidence(finding: Finding) -> object:
    value = _attr(finding, "evidence")
    if value is _MISSING:
        return {}
    return value


def _iso(value: datetime) -> str:
    return value.isoformat()


def _attr(obj: object, *names: str):
    for name in names:
        if isinstance(obj, dict):
            if name in obj:
                return obj[name]
            continue
        if hasattr(obj, name):
            return getattr(obj, name)
    return _MISSING
