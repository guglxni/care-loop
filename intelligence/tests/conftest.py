"""Shared clock and rule catalog for care-coordination tests."""

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

AS_OF = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
CATALOG_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "rule_catalog.json"

EMBEDDED_CATALOG = {
    "rules": [
        {
            "id": "glucose-fasting-review",
            "metric": "blood_glucose",
            "context": "fasting",
            "unit": "mg/dL",
            "comparator": "gte",
            "value": 180,
            "priority": "high",
            "team": "endocrinology-review",
            "approved": True,
            "min_occurrences": None,
            "window_hours": None,
        },
        {
            "id": "glucose-draft-unapproved",
            "metric": "blood_glucose",
            "context": None,
            "unit": "mg/dL",
            "comparator": "gte",
            "value": 140,
            "priority": "low",
            "team": "endocrinology-review",
            "approved": False,
            "min_occurrences": None,
            "window_hours": None,
        },
        {
            "id": "bp-systolic-review",
            "metric": "systolic_blood_pressure",
            "context": None,
            "unit": "mmHg",
            "comparator": "gte",
            "value": 160,
            "priority": "high",
            "team": "hypertension-review",
            "approved": True,
            "min_occurrences": None,
            "window_hours": None,
        },
        {
            "id": "adherence-repeat-gap",
            "metric": "adherence_missed",
            "context": None,
            "unit": "count",
            "comparator": "gte",
            "value": 3,
            "priority": "medium",
            "team": "care-coordination",
            "approved": True,
            "min_occurrences": 3,
            "window_hours": 168,
        },
    ],
    "coordination_defaults": {
        "missing_measurement_priority": "low",
        "unconfirmed_dose_priority": "low",
        "missed_dose_priority": "medium",
        "overdue_consultation_priority": "medium",
        "pending_laboratory_priority": "medium",
        "repeated_gap_count": 2,
    },
}


def load_catalog() -> dict:
    if CATALOG_PATH.is_file():
        return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return copy.deepcopy(EMBEDDED_CATALOG)


@pytest.fixture
def as_of() -> datetime:
    return AS_OF


@pytest.fixture
def catalog() -> dict:
    return load_catalog()
