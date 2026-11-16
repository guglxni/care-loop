"""Load the care-coordination catalog and decide which rules apply.

A rule applies only when ``rule["approved"]`` is true and its id is listed
in ``approved_rule_ids`` on a care plan for that patient. Comparators and
numeric bounds are read from the catalog. This module does not diagnose
or recommend a medicine.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from intelligence.models import PRIORITIES, PatientRecord, require_aware

CATALOG_PATH = Path(__file__).resolve().parent / "fixtures" / "rule_catalog.json"
COMPARATORS = frozenset({"gt", "gte", "lt", "lte", "eq"})
COORDINATION_DEFAULT_KEYS = (
    "missing_measurement_priority",
    "unconfirmed_dose_priority",
    "missed_dose_priority",
    "overdue_consultation_priority",
    "pending_laboratory_priority",
)
_RULE_KEYS = (
    "id",
    "metric",
    "context",
    "unit",
    "comparator",
    "value",
    "priority",
    "team",
    "approved",
    "min_occurrences",
    "window_hours",
)


def load_catalog(path: str | Path | None = None) -> dict[str, Any]:
    """Load and validate a rule catalog. The default path is the fixture."""
    catalog_path = CATALOG_PATH if path is None else Path(path)
    with catalog_path.open(encoding="utf-8") as handle:
        catalog = json.load(handle)
    validate_catalog(catalog)
    return catalog


def validate_catalog(catalog: dict[str, Any]) -> None:
    """Raise ``ValueError`` when the catalog shape is incomplete."""
    if not isinstance(catalog, dict):
        raise TypeError("catalog must be a dict")
    rules = catalog.get("rules")
    if not isinstance(rules, list):
        raise ValueError("catalog must include a rules list")
    seen: set[str] = set()
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise ValueError(f"rules[{index}] must be an object")
        _validate_rule(rule, index)
        rule_id = rule["id"]
        if rule_id in seen:
            raise ValueError(f"duplicate rule id: {rule_id}")
        seen.add(rule_id)
    defaults = catalog.get("coordination_defaults")
    if not isinstance(defaults, dict):
        raise ValueError("catalog must include coordination_defaults")
    for key in defaults:
        if not isinstance(key, str):
            raise ValueError("coordination_defaults keys must be strings")
    for key in COORDINATION_DEFAULT_KEYS:
        if key not in defaults:
            raise ValueError(f"coordination_defaults missing {key}")
        if defaults[key] not in PRIORITIES:
            raise ValueError(f"{key} must be a coordination priority")


def iter_rules(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the catalog's rule objects."""
    if not isinstance(catalog, dict):
        raise TypeError("catalog must be a dict")
    rules = catalog.get("rules")
    if not isinstance(rules, list):
        raise ValueError("catalog must include a rules list")
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise ValueError(f"rules[{index}] must be an object")
    return rules


def get_rule(catalog: dict[str, Any], rule_id: str) -> dict[str, Any] | None:
    """Return the first rule with this id, or None when it is absent."""
    for rule in iter_rules(catalog):
        if rule.get("id") == rule_id:
            return rule
    return None


def rule_is_approved_for(
    record: PatientRecord, catalog: dict[str, Any], rule_id: str
) -> bool:
    """True when the catalog approves the rule and a care plan lists it.

    A care plan is relevant when its ``approved_rule_ids`` contains the id.
    An unapproved catalog rule stays inactive even if a plan lists it.
    A catalog-approved rule stays inactive until a plan lists it.
    """
    if not isinstance(rule_id, str) or rule_id.strip() == "":
        return False
    rule = get_rule(catalog, rule_id)
    if rule is None or rule.get("approved") is not True:
        return False
    return rule_id in record.listed_rule_ids()


def matching_rules(
    catalog: dict[str, Any],
    metric: str,
    context: str | None = None,
) -> list[dict[str, Any]]:
    """Catalog-approved rules for one metric.

    Care-plan membership is not applied here. Use ``rule_is_approved_for``
    for that gate. A null ``context`` does not filter by context. A set
    context keeps rules whose context is null or equal to it.
    """
    if not isinstance(catalog, dict):
        return []
    source = catalog.get("rules")
    if not isinstance(source, list):
        return []
    selected: list[dict[str, Any]] = []
    for rule in source:
        if not isinstance(rule, dict) or rule.get("approved") is not True:
            continue
        if rule.get("metric") != metric:
            continue
        if context is not None:
            rule_context = rule.get("context")
            if rule_context not in (None, context):
                continue
        selected.append(rule)
    return selected


def applicable_rules(
    record: PatientRecord, catalog: dict[str, Any], metric: str
) -> list[dict[str, Any]]:
    """Rules approved for this patient whose catalog metric matches."""
    if not isinstance(metric, str) or metric.strip() == "":
        raise ValueError("metric must be a non-empty string")
    selected: list[dict[str, Any]] = []
    for rule in iter_rules(catalog):
        if rule.get("metric") != metric:
            continue
        rule_id = rule.get("id")
        if isinstance(rule_id, str) and rule_is_approved_for(record, catalog, rule_id):
            selected.append(rule)
    return selected


def rules_for_reading(
    record: PatientRecord,
    catalog: dict[str, Any],
    *,
    metric: str,
    unit: str,
    context: str | None,
) -> list[dict[str, Any]]:
    """Approved measurement rules for one metric, unit, and context.

    Unit match is exact. A null rule context matches any reading context.
    A rule context matches only that reading context.
    """
    selected: list[dict[str, Any]] = []
    for rule in applicable_rules(record, catalog, metric):
        if rule.get("unit") != unit:
            continue
        rule_context = rule.get("context")
        if rule_context is not None and rule_context != context:
            continue
        selected.append(rule)
    return selected


def compare(comparator: str, observed: float, bound: float) -> bool:
    """Apply a catalog comparator. ``bound`` comes from the catalog."""
    left = _number(observed, "observed")
    right = _number(bound, "bound")
    if comparator == "gt":
        return left > right
    if comparator == "gte":
        return left >= right
    if comparator == "lt":
        return left < right
    if comparator == "lte":
        return left <= right
    if comparator == "eq":
        return left == right
    raise ValueError(f"unsupported comparator: {comparator}")


def matches_rule(rule: dict[str, Any], observed: float) -> bool:
    """Whether ``observed`` meets the rule's catalog comparator and value."""
    return compare(rule["comparator"], observed, rule["value"])


def rule_min_occurrences(rule: dict[str, Any]) -> int | None:
    """Return the catalog occurrence count, or None when the rule has none."""
    value = rule.get("min_occurrences")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("min_occurrences must be an integer or null")
    return value


def in_window(moment: datetime, as_of: datetime, rule: dict[str, Any]) -> bool:
    """Whether ``moment`` is inside the rule lookback that ends at ``as_of``.

    A null ``window_hours`` adds no time limit. A moment after ``as_of``
    is outside the window. The width is the catalog's ``window_hours``.
    """
    require_aware(moment, "moment")
    require_aware(as_of, "as_of")
    if moment > as_of:
        return False
    hours = rule.get("window_hours")
    if hours is None:
        return True
    width = _positive_hours(hours)
    return (as_of - moment) <= timedelta(hours=width)


def coordination_priority(catalog: dict[str, Any], key: str) -> str:
    """Return one coordination priority label from the catalog.

    The labels prioritize care-team follow-up. They are not diagnoses.
    """
    if key not in COORDINATION_DEFAULT_KEYS:
        raise KeyError(key)
    defaults = catalog.get("coordination_defaults")
    if not isinstance(defaults, dict) or key not in defaults:
        raise ValueError(f"catalog coordination_defaults missing {key}")
    priority = defaults[key]
    if priority not in PRIORITIES:
        raise ValueError(f"{key} must be a coordination priority")
    return str(priority)


def _validate_rule(rule: dict[str, Any], index: int) -> None:
    missing = [key for key in _RULE_KEYS if key not in rule]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"rules[{index}] missing {joined}")
    rule_id = rule["id"]
    if not isinstance(rule_id, str) or rule_id.strip() == "":
        raise ValueError(f"rules[{index}].id must be a non-empty string")
    for key in ("metric", "unit", "team"):
        value = rule[key]
        if not isinstance(value, str) or value.strip() == "":
            raise ValueError(f"{rule_id}.{key} must be a non-empty string")
    context = rule["context"]
    if context is not None and (not isinstance(context, str) or context.strip() == ""):
        raise ValueError(f"{rule_id}.context must be a string or null")
    if rule["comparator"] not in COMPARATORS:
        raise ValueError(f"{rule_id}.comparator is not supported")
    _number(rule["value"], f"{rule_id}.value")
    if rule["priority"] not in PRIORITIES:
        raise ValueError(f"{rule_id}.priority must be a coordination priority")
    if not isinstance(rule["approved"], bool):
        raise ValueError(f"{rule_id}.approved must be a boolean")
    occurrences = rule["min_occurrences"]
    if occurrences is not None and (
        isinstance(occurrences, bool) or not isinstance(occurrences, int) or occurrences < 0
    ):
        raise ValueError(f"{rule_id}.min_occurrences must be an integer or null")
    hours = rule["window_hours"]
    if hours is not None:
        _positive_hours(hours, label=f"{rule_id}.window_hours")


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


def _positive_hours(value: object, label: str = "window_hours") -> float:
    number = _number(value, label)
    if number <= 0:
        raise ValueError(f"{label} must be greater than zero")
    return number


__all__ = [
    "CATALOG_PATH",
    "COMPARATORS",
    "COORDINATION_DEFAULT_KEYS",
    "load_catalog",
    "validate_catalog",
    "iter_rules",
    "get_rule",
    "rule_is_approved_for",
    "matching_rules",
    "applicable_rules",
    "rules_for_reading",
    "compare",
    "matches_rule",
    "rule_min_occurrences",
    "in_window",
    "coordination_priority",
]
