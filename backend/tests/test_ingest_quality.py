"""Timestamp, unit, and duplicate-key rules for ingest."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.errors import ValidationError
from app.ingest.quality import (
    glucose_to_mg_dl,
    is_duplicate,
    normalize_bp_unit,
    normalize_glucose,
    reading_key,
    require_aware_timestamp,
)

PATIENT = "11111111-1111-4111-8111-111111111111"


def test_naive_timestamp_is_rejected():
    with pytest.raises(ValidationError) as caught:
        require_aware_timestamp(datetime(2026, 11, 14, 8, 0))
    assert any("timezone" in item for item in caught.value.details)

    with pytest.raises(ValidationError) as caught_text:
        require_aware_timestamp("2026-11-14T08:00:00")
    assert any("timezone" in item for item in caught_text.value.details)

    with pytest.raises(ValidationError):
        reading_key(PATIENT, "blood_glucose", datetime(2026, 11, 14, 8, 0), "glucometer", None, 142)


def test_future_timestamp_limit():
    accepted = require_aware_timestamp(datetime.now(timezone.utc) + timedelta(minutes=4))
    assert accepted.utcoffset() == timedelta(0)

    with pytest.raises(ValidationError) as caught:
        require_aware_timestamp(datetime.now(timezone.utc) + timedelta(minutes=6))
    assert any("5 minutes" in item for item in caught.value.details)


def test_aware_timestamp_converts_to_utc():
    local = datetime(2026, 11, 14, 13, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    parsed = require_aware_timestamp(local)
    assert parsed == datetime(2026, 11, 14, 8, 0, tzinfo=timezone.utc)
    zulu = require_aware_timestamp("2026-11-14T08:00:00Z")
    assert zulu == parsed


def test_glucose_unit_is_not_converted():
    assert normalize_glucose(142, "mg/dL") == (142.0, "mg/dL")
    assert normalize_glucose(7.4, "mmol/L") == (7.4, "mmol/L")
    assert normalize_glucose(142, "mg/dl") == (142.0, "mg/dL")
    with pytest.raises(ValidationError) as caught:
        normalize_glucose(142, "mmol")
    assert any("mg/dL" in item and "mmol/L" in item for item in caught.value.details)
    with pytest.raises(ValidationError):
        normalize_glucose(True, "mg/dL")


def test_glucose_to_mg_dl_is_comparison_only():
    assert glucose_to_mg_dl(142, "mg/dL") == 142
    assert glucose_to_mg_dl(7.4, "mmol/L") == pytest.approx(7.4 * 18.0182)


def test_bp_unit_accepts_mmhg_only():
    assert normalize_bp_unit(" mmHg ") == "mmHg"
    with pytest.raises(ValidationError) as caught:
        normalize_bp_unit("kPa")
    assert any("mmHg" in item for item in caught.value.details)


def test_duplicate_key_ignores_device_null_and_numeric_spelling():
    ist = datetime(2026, 11, 14, 13, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    utc = datetime(2026, 11, 14, 8, 0, tzinfo=timezone.utc)
    left = reading_key(PATIENT, "blood_glucose", ist, "glucometer", None, 120)
    right = reading_key(PATIENT, "blood_glucose", utc, "glucometer", "", Decimal("120.00"))
    assert left == right
    assert is_duplicate({left}, right)
    assert not is_duplicate(set(), left)
    other = reading_key(PATIENT, "blood_glucose", utc, "cgm", None, 120)
    assert not is_duplicate({left}, other)
