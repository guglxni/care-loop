"""Coordination findings for blood pressure monitoring gaps and approved review rules."""

from datetime import date, datetime, time, timedelta

from intelligence.models import CarePlan, DoseEvent, Finding, PatientRecord, Reading
from intelligence.rules import (
    coordination_priority,
    matches_rule,
    matching_rules,
    rule_is_approved_for,
)

_MODELS = (CarePlan, DoseEvent, Finding, PatientRecord, Reading)
_LOOKBACK_DAYS = 7
_SYSTOLIC = "systolic_blood_pressure"
_DIASTOLIC = "diastolic_blood_pressure"
_BP_CONTEXTS = frozenset({"resting", "other"})
_SCHEDULE_KEYS = ("blood_pressure", "bp")


def evaluate_blood_pressure(
    record: PatientRecord,
    as_of: datetime,
    catalog: dict,
) -> list[Finding]:
    """Return missing blood-pressure slots and approved review-rule matches."""
    _require_aware(as_of)
    findings: list[Finding] = []
    seen: set[str] = set()
    for finding in _missing_slots(record, as_of, catalog):
        _add(findings, seen, finding)
    for finding in _rule_matches(record, as_of, catalog):
        _add(findings, seen, finding)
    return findings


def _missing_slots(record: PatientRecord, as_of: datetime, catalog: dict) -> list[Finding]:
    readings = list(record.readings or [])
    due = _due_slots(_schedule_entries(record), as_of, require_context=False)
    if not due:
        return []
    priority = coordination_priority(catalog, "missing_measurement_priority")
    findings: list[Finding] = []
    for context, day in sorted(due, key=lambda item: (item[1], str(item[0]))):
        if _has_pair(readings, context, day, as_of):
            continue
        day_text = day.isoformat()
        token = context or "unspecified"
        if context:
            description = f"No {context} blood pressure reading for {day_text}"
        else:
            description = f"No blood pressure reading for {day_text}"
        findings.append(
            Finding(
                kind="bp_missing",
                description=description,
                priority=priority,
                dedupe_key=f"bp-missing:{token}:{day_text}",
                rule_id=None,
                evidence={"context": context, "date": day_text},
            )
        )
    return findings


def _rule_matches(record: PatientRecord, as_of: datetime, catalog: dict) -> list[Finding]:
    readings = list(record.readings or [])
    by_type = {
        _SYSTOLIC: _valid_index(readings, _SYSTOLIC, as_of),
        _DIASTOLIC: _valid_index(readings, _DIASTOLIC, as_of),
    }
    any_by_type = {
        _SYSTOLIC: _any_index(readings, _SYSTOLIC, as_of),
        _DIASTOLIC: _any_index(readings, _DIASTOLIC, as_of),
    }
    findings: list[Finding] = []
    moments = sorted(set(by_type[_SYSTOLIC]) | set(by_type[_DIASTOLIC]))
    for moment in moments:
        systolic = by_type[_SYSTOLIC].get(moment) or any_by_type[_SYSTOLIC].get(moment)
        diastolic = by_type[_DIASTOLIC].get(moment) or any_by_type[_DIASTOLIC].get(moment)
        for metric, primary in (
            (_SYSTOLIC, by_type[_SYSTOLIC].get(moment)),
            (_DIASTOLIC, by_type[_DIASTOLIC].get(moment)),
        ):
            if primary is None:
                continue
            for rule in _rules_for(catalog, metric, primary.measurement_context):
                if not _value_matches(rule, primary.value, primary.unit):
                    continue
                rule_id = str(_field(rule, "id"))
                if not rule_is_approved_for(record, catalog, rule_id):
                    continue
                when = primary.measured_at.isoformat()
                evidence = {
                    "team": _field(rule, "team"),
                    "measured_at": when,
                    "metric": metric,
                    "value": primary.value,
                    "unit": primary.unit,
                    "measurement_context": primary.measurement_context,
                    "systolic": None if systolic is None else systolic.value,
                    "diastolic": None if diastolic is None else diastolic.value,
                    "rule_id": rule_id,
                }
                findings.append(
                    Finding(
                        kind="bp_rule_match",
                        description=f"Blood pressure reading met configured review rule {rule_id}",
                        priority=_field(rule, "priority"),
                        dedupe_key=f"bp-rule:{rule_id}:{when}",
                        rule_id=rule_id,
                        evidence=evidence,
                    )
                )
    return findings


def _has_pair(
    readings: list[Reading],
    context: str | None,
    day: date,
    as_of: datetime,
) -> bool:
    systolic_times: set[datetime] = set()
    diastolic_times: set[datetime] = set()
    for reading in readings:
        if reading.measurement_type not in (_SYSTOLIC, _DIASTOLIC):
            continue
        if context is not None and reading.measurement_context != context:
            continue
        _require_aware_moment(reading.measured_at, "measured_at")
        if _wall_date(reading.measured_at, as_of) != day:
            continue
        if reading.measurement_type == _SYSTOLIC:
            systolic_times.add(reading.measured_at)
        else:
            diastolic_times.add(reading.measured_at)
    return any(moment in systolic_times for moment in diastolic_times)


def _valid_index(readings: list[Reading], measurement_type: str, as_of: datetime) -> dict:
    chosen: dict[datetime, Reading] = {}
    for reading in readings:
        if reading.measurement_type != measurement_type or reading.data_quality != "valid":
            continue
        _require_aware_moment(reading.measured_at, "measured_at")
        if reading.measured_at <= as_of and reading.measured_at not in chosen:
            chosen[reading.measured_at] = reading
    return chosen


def _any_index(readings: list[Reading], measurement_type: str, as_of: datetime) -> dict:
    chosen: dict[datetime, Reading] = {}
    for reading in readings:
        if reading.measurement_type != measurement_type:
            continue
        _require_aware_moment(reading.measured_at, "measured_at")
        if reading.measured_at <= as_of and reading.measured_at not in chosen:
            chosen[reading.measured_at] = reading
    return chosen


def _schedule_entries(record: PatientRecord) -> list[dict]:
    entries: list[dict] = []
    for plan in record.care_plans or []:
        schedule = _plan_schedule(plan)
        for key in _SCHEDULE_KEYS:
            entries.extend(_normalize_entries(schedule.get(key), _BP_CONTEXTS))
    return entries


def _plan_schedule(plan: CarePlan | dict) -> dict:
    if isinstance(plan, dict):
        return plan.get("monitoring_schedule") or {}
    schedule = getattr(plan, "monitoring_schedule", None)
    return schedule or {}


def _normalize_entries(raw: object, known_contexts: frozenset[str]) -> list[dict]:
    if isinstance(raw, str):
        return _normalize_entries([raw], known_contexts)
    if isinstance(raw, dict):
        if "times" in raw or "time" in raw or "context" in raw:
            return [_as_entry(raw)]
        return [
            _as_entry({"context": context, "times": times, "days": "daily"})
            for context, times in raw.items()
        ]
    if isinstance(raw, list):
        entries = []
        for item in raw:
            if isinstance(item, dict):
                entries.append(_as_entry(item))
            elif isinstance(item, str):
                entries.append(_string_entry(item, known_contexts))
        return entries
    return []


def _string_entry(item: str, known_contexts: frozenset[str]) -> dict:
    if _parse_clock(item):
        return _as_entry({"times": [item], "days": "daily"})
    if item in known_contexts:
        return _as_entry({"context": item, "times": ["00:00"], "days": "daily"})
    return _as_entry({"times": ["00:00"], "days": "daily"})


def _as_entry(item: dict) -> dict:
    context = item.get("context", item.get("measurement_context"))
    times = item.get("times", item.get("time", []))
    if isinstance(times, str):
        times = [times]
    elif times is None:
        times = []
    return {"context": context, "times": list(times), "days": item.get("days", "daily")}


def _due_slots(
    entries: list[dict],
    as_of: datetime,
    require_context: bool,
) -> dict[tuple[str | None, date], list[datetime]]:
    end = as_of.date()
    start = end - timedelta(days=_LOOKBACK_DAYS - 1)
    due: dict[tuple[str | None, date], list[datetime]] = {}
    for entry in entries:
        days = entry.get("days", "daily")
        if not isinstance(days, str) or days.lower() != "daily":
            continue
        context = entry.get("context")
        if require_context and not context:
            continue
        day = start
        while day <= end:
            for clock in entry.get("times") or []:
                moment = _at_clock(day, clock, as_of.tzinfo)
                if moment is not None and moment <= as_of:
                    due.setdefault((context, day), []).append(moment)
            day += timedelta(days=1)
    return due


def _rules_for(catalog: dict, metric: str, reading_context: str | None) -> list:
    found: dict[str, object] = {}
    for rule in matching_rules(catalog, metric, context=reading_context):
        rule_id = _field(rule, "id")
        if not rule_id or str(rule_id) in found:
            continue
        if _field(rule, "approved") is False:
            continue
        rule_metric = _field(rule, "metric")
        if rule_metric not in (None, metric):
            continue
        rule_context = _field(rule, "context")
        if rule_context not in (None, "", reading_context):
            continue
        found[str(rule_id)] = rule
    return [found[key] for key in sorted(found)]


def _value_matches(rule: object, value: float, unit: str) -> bool:
    if not isinstance(rule, dict) or rule.get("unit") != unit:
        return False
    return matches_rule(rule, value)


def _wall_date(moment: datetime, as_of: datetime) -> date:
    return moment.astimezone(as_of.tzinfo).date()


def _at_clock(day: date, clock: object, tzinfo: datetime.tzinfo) -> datetime | None:
    parsed = _parse_clock(clock)
    if parsed is None:
        return None
    hour, minute, second = parsed
    return datetime.combine(day, time(hour, minute, second), tzinfo=tzinfo)


def _parse_clock(clock: object) -> tuple[int, int, int] | None:
    if not isinstance(clock, str):
        return None
    parts = clock.split(":")
    if len(parts) not in (2, 3):
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2]) if len(parts) == 3 else 0
    except ValueError:
        return None
    if hour > 23 or minute > 59 or second > 59 or hour < 0 or minute < 0 or second < 0:
        return None
    return hour, minute, second


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
