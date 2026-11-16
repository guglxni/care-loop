"""Optional glucose forecast for care-coordination display.

Estimates are computed from stored blood glucose readings. They are not
measurements, diagnoses, or dose advice, and they are never written back
to health_readings.
"""

from __future__ import annotations

import math
import os
import threading
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import HealthReading
from app.services.patient_service import get_patient
from app.timeutil import json_number, to_iso

# TimesFM stays in this module. The unofficial GlucoFM encoder is app.ingest.glucofm,
# attached by the forecast routes. It is an embedding companion, not a glucose forecast.
MODEL_NAME = "timesfm"
DISCLAIMER = "Forecast only. Not a glucose measurement and not medical advice."
LIBRARY_NOTE = "The timesfm model library is not installed."
WEIGHTS_NOTE = "TimesFM weights are not available locally and were not downloaded."
FAILED_NOTE = "TimesFM did not return a forecast."
HISTORY_LIMIT = 36
MIN_POINTS = 6
HORIZON = 6
FORECAST_TIMEOUT_SECONDS = 15
MGDL_PER_MMOL = 18.0182
DISPLAY_STEP = timedelta(minutes=15)
CHECKPOINT_2_5 = "google/timesfm-2.5-200m-pytorch"
CHECKPOINT_1 = "google/timesfm-1.0-200m-pytorch"
CHECKPOINT_3 = "google/timesfm-3.0-pytorch"


class ForecastUnavailable(Exception):
    def __init__(self, note: str) -> None:
        super().__init__(note)
        self.note = note


def forecast_for_patient(session: Session, patient_id: str) -> dict:
    patient = get_patient(session, patient_id)
    series = load_glucose_series(session, patient.id)
    if len(series) < MIN_POINTS:
        return _unavailable(DISCLAIMER)
    try:
        points = forecast_mgdl([value for _moment, value in series])
    except ForecastUnavailable as exc:
        return _unavailable(f"{DISCLAIMER} {exc.note}")
    last_at = series[-1][0]
    step = _display_step([moment for moment, _value in series])
    estimates = []
    for index, value in enumerate(points, start=1):
        estimates.append(
            {
                "measured_at": to_iso(last_at + step * index),
                "value": json_number(round(value, 1)),
                "unit": "mg/dL",
            }
        )
    return {
        "model": MODEL_NAME,
        "available": True,
        "origin": "model",
        "estimates": estimates,
        "disclaimer": DISCLAIMER,
    }


def load_glucose_series(session: Session, patient_id) -> list[tuple[datetime, float]]:
    """Latest stored glucose points, oldest first. No points are invented."""
    rows = session.scalars(
        select(HealthReading)
        .where(
            HealthReading.patient_id == patient_id,
            HealthReading.measurement_type == "blood_glucose",
        )
        .order_by(HealthReading.measured_at.desc(), HealthReading.id.desc())
        .limit(HISTORY_LIMIT)
    ).all()
    series: list[tuple[datetime, float]] = []
    for row in reversed(rows):
        value = _as_mgdl(row.unit, row.value)
        if value is None:
            continue
        series.append((row.measured_at, value))
    return series


def forecast_mgdl(values: list[float]) -> list[float]:
    """Point forecast in mg/dL. Raises ForecastUnavailable instead of inventing points."""
    if len(values) < MIN_POINTS:
        raise ForecastUnavailable(FAILED_NOTE)
    if _import_timesfm() is None:
        raise ForecastUnavailable(LIBRARY_NOTE)
    backend = _selected_backend()
    if backend is None:
        raise ForecastUnavailable(WEIGHTS_NOTE)
    return _forecast_with_cap(backend, values)


def runtime_status() -> str:
    """missing, weights, or ready. Does not download checkpoints."""
    if _import_timesfm() is None:
        return "missing"
    if _selected_backend() is None:
        return "weights"
    return "ready"


def _unavailable(disclaimer: str) -> dict:
    return {
        "model": MODEL_NAME,
        "available": False,
        "origin": "unavailable",
        "estimates": [],
        "disclaimer": disclaimer,
    }


def _as_mgdl(unit: str, value) -> float | None:
    number = float(value)
    if not math.isfinite(number):
        return None
    if unit == "mg/dL":
        return number
    if unit == "mmol/L":
        return number * MGDL_PER_MMOL
    return None


def _display_step(times: list[datetime]) -> timedelta:
    gaps = []
    for earlier, later in zip(times, times[1:]):
        gap = later - earlier
        if gap.total_seconds() > 0:
            gaps.append(gap)
    if not gaps:
        return DISPLAY_STEP
    gaps.sort()
    return gaps[len(gaps) // 2]


def _import_timesfm():
    try:
        import timesfm
    except ImportError:
        return None
    return timesfm


def _selected_backend() -> str | None:
    timesfm = _import_timesfm()
    if timesfm is None:
        return None
    if hasattr(timesfm, "TimesFM_2p5_200M_torch") and _checkpoint_cached(CHECKPOINT_2_5):
        return "2.5"
    if hasattr(timesfm, "TimesFm") and _checkpoint_cached(CHECKPOINT_1):
        return "1.0"
    if _timesfm3_api(timesfm) is not None and _checkpoint_cached(CHECKPOINT_3):
        return "3.0"
    return None


def _timesfm3_api(timesfm):
    evaluator = getattr(timesfm, "TimesFM3Evaluator", None)
    config = getattr(timesfm, "ModelConfig", None)
    if evaluator is not None and config is not None:
        return evaluator, config
    try:
        from timesfm3 import ModelConfig, TimesFM3Evaluator
    except ImportError:
        return None
    return TimesFM3Evaluator, ModelConfig


def _checkpoint_cached(repo_id: str) -> bool:
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        return False
    previous = os.environ.get("HF_HUB_OFFLINE")
    os.environ["HF_HUB_OFFLINE"] = "1"
    try:
        snapshot_download(repo_id, local_files_only=True)
    except Exception:
        return False
    finally:
        if previous is None:
            os.environ.pop("HF_HUB_OFFLINE", None)
        else:
            os.environ["HF_HUB_OFFLINE"] = previous
    return True


def _forecast_with_cap(backend: str, values: list[float]) -> list[float]:
    box: dict = {}

    def run() -> None:
        previous = os.environ.get("HF_HUB_OFFLINE")
        os.environ["HF_HUB_OFFLINE"] = "1"
        try:
            box["points"] = _run_backend(backend, values)
        except Exception as exc:
            box["error"] = exc
        finally:
            if previous is None:
                os.environ.pop("HF_HUB_OFFLINE", None)
            else:
                os.environ["HF_HUB_OFFLINE"] = previous

    thread = threading.Thread(target=run, name="timesfm-forecast", daemon=True)
    thread.start()
    thread.join(FORECAST_TIMEOUT_SECONDS)
    if thread.is_alive() or "points" not in box:
        raise ForecastUnavailable(FAILED_NOTE)
    return box["points"]


def _run_backend(backend: str, values: list[float]) -> list[float]:
    import numpy as np

    timesfm = _import_timesfm()
    series = np.asarray(values, dtype=np.float32)
    if backend == "2.5":
        output = _forecast_2_5(timesfm, series)
    elif backend == "1.0":
        output = _forecast_1(timesfm, values)
    elif backend == "3.0":
        output = _forecast_3(timesfm, series)
    else:
        raise ForecastUnavailable(WEIGHTS_NOTE)
    return _finite_points(output)


def _forecast_2_5(timesfm, series) -> object:
    model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(
        CHECKPOINT_2_5,
        torch_compile=False,
    )
    model.compile(
        timesfm.ForecastConfig(
            max_context=512,
            max_horizon=HORIZON,
            normalize_inputs=True,
            use_continuous_quantile_head=True,
            force_flip_invariance=True,
            infer_is_positive=True,
            fix_quantile_crossing=True,
        )
    )
    point_forecast, _quantile_forecast = model.forecast(horizon=HORIZON, inputs=[series])
    return point_forecast


def _forecast_1(timesfm, values: list[float]) -> object:
    context_len = max(32, len(values))
    model = timesfm.TimesFm(
        hparams=timesfm.TimesFmHparams(
            backend="cpu",
            per_core_batch_size=1,
            horizon_len=HORIZON,
            context_len=context_len,
        ),
        checkpoint=timesfm.TimesFmCheckpoint(huggingface_repo_id=CHECKPOINT_1),
    )
    point_forecast, _quantile_forecast = model.forecast([values], freq=[0])
    return point_forecast


def _forecast_3(timesfm, series) -> object:
    api = _timesfm3_api(timesfm)
    if api is None:
        raise ForecastUnavailable(WEIGHTS_NOTE)
    evaluator_cls, config_cls = api
    forecaster = evaluator_cls(
        config_cls(
            checkpoint_path=CHECKPOINT_3,
            per_core_batch_size=1,
            device="cpu",
        )
    )
    return list(
        forecaster.predict_batch(
            [series],
            horizon=HORIZON,
            return_quantiles=False,
        )
    )


def _finite_points(output) -> list[float]:
    values = _flatten_forecast(output)
    points = []
    for item in values[:HORIZON]:
        number = float(item)
        if not math.isfinite(number):
            raise ForecastUnavailable(FAILED_NOTE)
        points.append(number)
    if not points:
        raise ForecastUnavailable(FAILED_NOTE)
    return points


def _flatten_forecast(output):
    if isinstance(output, (list, tuple)) and output and hasattr(output[0], "forecast"):
        output = output[0].forecast
    elif hasattr(output, "forecast"):
        output = output.forecast
    elif isinstance(output, tuple):
        output = output[0]
    if hasattr(output, "detach"):
        output = output.detach().cpu().numpy()
    if hasattr(output, "tolist"):
        output = output.tolist()
    if output and isinstance(output[0], (list, tuple)):
        output = output[0]
    return list(output)
