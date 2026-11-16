"""Turn findings into open care-coordination events and escalation rows.

Event descriptions stay factual. They do not diagnose, prescribe, recommend
taking a medicine, or change a dose.
"""

import inspect
import uuid
from datetime import datetime

from intelligence.models import CareCoordinationEvent, EscalationRecord, PatientRecord
from intelligence.rules import rule_is_approved_for

BANNED_PHRASES = (
    "diagnos",
    "prescri",
    "recommend taking",
    "recommend you take",
    "recommend a medicine",
    "recommend the medicine",
    "take your medicine",
    "take the medicine",
    "take this medicine",
    "take your medication",
    "take the medication",
    "take this medication",
    "you should take",
    "please take",
    "change a dose",
    "change the dose",
    "change your dose",
    "change dose",
    "dose change",
    "increase the dose",
    "increase your dose",
    "decrease the dose",
    "decrease your dose",
    "adjust the dose",
    "adjust your dose",
    "adjust a dose",
    "new dose",
    "higher dose",
    "lower dose",
)

_MISSING = object()
_RULE_BUCKETS = ("rules", "threshold_rules")


def guard_description(description: str, *, kind: str) -> str:
    """Return description when it is safe, otherwise a coordination sentence."""
    text = description or ""
    lowered = text.lower()
    if text and not any(phrase in lowered for phrase in BANNED_PHRASES):
        return text
    return f"Care coordination item ({kind}) is open for human review."


def build_events(
    findings: list,
    record: PatientRecord,
    as_of: datetime,
    catalog: dict,
    existing_open_keys: set[str] | None = None,
) -> tuple[list[CareCoordinationEvent], list[EscalationRecord]]:
    """Create one open event and one escalation row per remaining finding."""
    open_keys = {str(key) for key in (existing_open_keys or set())}
    seen: set[str] = set()
    events: list[CareCoordinationEvent] = []
    escalations: list[EscalationRecord] = []
    patient_id = str(_attr(record, "patient_id"))
    for finding in findings:
        rule_id = _rule_id(finding)
        if rule_id and not _is_approved(catalog, rule_id, record):
            continue
        dedupe_key = _dedupe(finding)
        if dedupe_key in open_keys or dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        kind = _kind(finding)
        description = guard_description(_description(finding), kind=kind)
        priority = _attr(finding, "priority")
        if priority is _MISSING:
            priority = "low"
        team = _team(finding, catalog, rule_id)
        evidence = _copy_evidence(finding)
        events.append(
            new_model(
                CareCoordinationEvent,
                id=str(uuid.uuid4()),
                patient_id=patient_id,
                event_type=kind,
                kind=kind,
                description=description,
                event_description=description,
                priority=priority,
                status="open",
                requires_human_review=True,
                dedupe_key=dedupe_key,
                rule_id=rule_id,
                team=team,
                evidence=evidence,
                opened_at=as_of,
                created_at=as_of,
            )
        )
        escalations.append(
            new_model(
                EscalationRecord,
                id=str(uuid.uuid4()),
                patient_id=patient_id,
                dedupe_key=dedupe_key,
                event_dedupe_key=dedupe_key,
                rule_id=rule_id,
                priority=priority,
                team=team,
                opened_at=as_of,
                created_at=as_of,
                status="open",
                requires_human_review=True,
                event_type=kind,
                kind=kind,
                description=description,
                event_description=description,
                evidence=evidence,
            )
        )
    return events, escalations


def new_model(cls, **kwargs):
    """Construct a model, ignoring keyword arguments it does not accept."""
    model_fields = getattr(cls, "model_fields", None)
    if isinstance(model_fields, dict) and model_fields:
        payload = {}
        missing = []
        for name, field in model_fields.items():
            if name in kwargs:
                payload[name] = kwargs[name]
            elif field.is_required():
                if name == "id":
                    payload[name] = str(uuid.uuid4())
                else:
                    missing.append(name)
        if missing:
            raise TypeError(f"{cls.__name__} requires {missing}. Provided {sorted(kwargs)}.")
        return cls(**payload)

    signature = inspect.signature(cls)
    has_var_keyword = any(
        param.kind is inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()
    )
    payload = {}
    missing = []
    accepted: set[str] = set()
    for name, param in signature.parameters.items():
        if name == "self":
            continue
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        accepted.add(name)
        if name in kwargs:
            payload[name] = kwargs[name]
        elif param.default is inspect.Parameter.empty:
            if name == "id":
                payload[name] = str(uuid.uuid4())
            else:
                missing.append(name)
    if has_var_keyword:
        for name, value in kwargs.items():
            if name not in payload:
                payload[name] = value
    elif missing:
        raise TypeError(f"{cls.__name__} requires {missing}. Provided {sorted(kwargs)}.")
    if not has_var_keyword:
        payload = {name: value for name, value in payload.items() if name in accepted or name == "id"}
    return cls(**payload)


def _is_approved(catalog: dict, rule_id: str, record: PatientRecord) -> bool:
    signature = inspect.signature(rule_is_approved_for)
    pool = {
        "catalog": catalog,
        "rule_catalog": catalog,
        "rules": catalog,
        "rule_id": rule_id,
        "rule": rule_id,
        "record": record,
        "patient_record": record,
        "patient": record,
    }
    names = [
        name
        for name, param in signature.parameters.items()
        if param.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
    ]
    if names and all(name in pool for name in names):
        return bool(rule_is_approved_for(**{name: pool[name] for name in names}))
    return bool(rule_is_approved_for(catalog, rule_id, record))


def _team(finding: object, catalog: dict, rule_id: str | None) -> str:
    evidence = _attr(finding, "evidence")
    if isinstance(evidence, dict):
        team = evidence.get("team")
        if isinstance(team, str) and team.strip():
            return team.strip()
    if not rule_id:
        return "care-coordination"
    for rule in _rules(catalog):
        if _rule_identifier(rule) == rule_id:
            team = _rule_team(rule)
            if team:
                return team
    return "care-coordination"


def _rules(catalog: dict) -> list[dict]:
    if not isinstance(catalog, dict):
        return []
    collected: list[dict] = []
    seen: set[str] = set()
    for bucket_name in _RULE_BUCKETS:
        bucket = catalog.get(bucket_name)
        if isinstance(bucket, list):
            for rule in bucket:
                _add_rule(collected, seen, rule)
        elif isinstance(bucket, dict):
            if any(key in bucket for key in ("id", "rule_id", "comparator", "measurement_type", "metric")):
                _add_rule(collected, seen, bucket)
            else:
                for key, rule in bucket.items():
                    _add_rule(collected, seen, rule, key)
    return collected


def _add_rule(collected: list[dict], seen: set[str], rule: object, key: object = None) -> None:
    if not isinstance(rule, dict):
        return
    row = dict(rule)
    if key is not None and not row.get("id") and not row.get("rule_id"):
        row["id"] = key
    marker = _rule_identifier(row) or str(id(rule))
    if marker in seen:
        return
    seen.add(marker)
    collected.append(row)


def _rule_identifier(rule: dict) -> str:
    value = rule.get("id", rule.get("rule_id"))
    if value is None:
        return ""
    return str(value)


def _rule_team(rule: dict) -> str | None:
    for key in ("team", "owner_team", "escalation_team", "queue"):
        value = rule.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for key in ("escalation", "routing", "assignment"):
        nested = rule.get(key)
        if isinstance(nested, dict):
            value = nested.get("team")
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _rule_id(finding: object) -> str | None:
    value = _attr(finding, "rule_id")
    if value is _MISSING or value is None:
        return None
    text = str(value).strip()
    return text or None


def _kind(finding: object) -> str:
    value = _attr(finding, "kind", "event_type", "finding_kind", "finding_type")
    if value is _MISSING or value is None:
        return ""
    return str(value)


def _dedupe(finding: object) -> str:
    value = _attr(finding, "dedupe_key")
    if value is _MISSING or value is None:
        return ""
    return str(value)


def _description(finding: object) -> str:
    value = _attr(finding, "description", "event_description")
    if value is _MISSING or value is None:
        return ""
    return str(value)


def _copy_evidence(finding: object) -> dict:
    value = _attr(finding, "evidence")
    if isinstance(value, dict):
        return dict(value)
    if value is _MISSING or value is None:
        return {}
    return {"details": value}


def _attr(obj: object, *names: str):
    for name in names:
        if isinstance(obj, dict):
            if name in obj:
                return obj[name]
            continue
        if hasattr(obj, name):
            return getattr(obj, name)
    return _MISSING
