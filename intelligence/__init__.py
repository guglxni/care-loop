"""Care-coordination entry points.

Import chart types from ``intelligence.models`` and catalog helpers from
``intelligence.rules``. ``evaluate`` loads the domain modules when called.
This package coordinates care. It does not diagnose, prescribe, or recommend
a medicine, and it does not tell a patient to take, skip, or change a dose.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from intelligence.models import IntelligenceResult, PatientRecord

__all__ = ["IntelligenceResult", "PatientRecord", "evaluate"]


def evaluate(
    record: PatientRecord,
    as_of: datetime,
    catalog: dict[str, Any],
    existing_open_keys: set[str] | None = None,
) -> IntelligenceResult:
    """Coordinate care for one patient record.

    Signature matches ``intelligence.engine.evaluate``. ``as_of`` must be
    timezone-aware. Domain modules are imported when this is called.
    """
    from intelligence.engine import evaluate as evaluate_record

    return evaluate_record(record, as_of, catalog, existing_open_keys)
