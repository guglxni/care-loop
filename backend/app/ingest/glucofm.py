"""Optional unofficial GlucoFM encoder for care-coordination display.

The wired artifact is the community ONNX conversion at
https://huggingface.co/eugenehp/glucofm-encoder. It returns a 128-d embedding.
It is not Google's checkpoint, not a glucose forecast, and not a measurement.
Nothing here is written to health_readings.
"""

from __future__ import annotations

import math
import os
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.services.patient_service import get_patient

MODEL_NAME = "unofficial reconstruction: eugenehp/glucofm-encoder"
SOURCE_URL = "https://huggingface.co/eugenehp/glucofm-encoder"
DISCLAIMER = (
    "Unofficial reconstruction. Not Google's GlucoFM checkpoint. "
    "Not a glucose measurement and not medical advice."
)
NOT_INSTALLED = "unofficial GlucoFM encoder not installed"
NO_POINTS = "No stored glucose points to encode."
FAILED_NOTE = "Unofficial GlucoFM encoder did not return an embedding."
MISSING_CONTEXT = (
    "Meal and subject context are required for a glucose trajectory, "
    "and this demo does not have them."
)
REPO_ID = "eugenehp/glucofm-encoder"
ONNX_FILE = "glucofm_encoder.onnx"
EMBEDDING_DIM = 128
GRID_POINTS = 288
STEP = timedelta(minutes=5)
CONTEXT_FIELDS = ("meal_nutrition", "fasting_glucose", "bmi", "diabetes_status")

_SESSIONS: dict[str, object] = {}
_REPOSITORIES = (
    {
        "url": "https://huggingface.co/eugenehp/glucofm-encoder",
        "integrated": True,
        "note": (
            "Small ONNX encoder. Embeddings only. Loaded from a local file "
            "when onnxruntime is installed. Not downloaded by tests."
        ),
    },
    {
        "url": "https://github.com/sfourdrinier/opencgm",
        "integrated": False,
        "note": (
            "Upstream reconstruction. Needs a local torch checkpoint. "
            "Its day report includes phenotype scores, which this API does not return."
        ),
    },
    {
        "url": "https://github.com/ViSaReVe/glucofm-replication",
        "integrated": False,
        "note": (
            "PyTorch implementation with no shipped checkpoint. "
            "An uninitialized encoder is not this reconstruction."
        ),
    },
    {
        "url": "https://github.com/eugenehp/glucofm-rs",
        "integrated": False,
        "note": "Rust port of the same encoder. The Python service uses the ONNX conversion instead.",
    },
    {
        "url": "https://huggingface.co/datasets/glucofmbench/GlucoFM-Bench",
        "integrated": False,
        "note": "Benchmark dataset, not the GlucoFM encoder. Not downloaded.",
    },
    {
        "url": "https://arxiv.org/abs/2605.30865",
        "integrated": False,
        "note": "Paper. Authors said they will release code. No official checkpoint is wired in.",
    },
    {
        "url": "https://research.google/blog/glucofm-foundation-model-for-continuous-glucose-monitoring",
        "integrated": False,
        "note": "Google Research blog. No code or weight link.",
    },
)


def glucofm_for_patient(session: Session, patient_id: str) -> dict:
    """Companion signal for one patient. Reads stored glucose and writes nothing."""
    patient = get_patient(session, patient_id)
    payload = _base_payload()
    payload["trajectory_forecast"] = _trajectory_unavailable()
    if not _encoder_installed():
        payload["available"] = False
        payload["reason"] = NOT_INSTALLED
        payload["embedding_metadata"] = _metadata(computed=False)
        payload["observed_points"] = None
        return payload
    from app.ingest.forecast import load_glucose_series

    window = _build_window(load_glucose_series(session, patient.id))
    if window is None:
        payload["available"] = False
        payload["reason"] = NO_POINTS
        payload["embedding_metadata"] = _metadata(computed=False)
        payload["observed_points"] = 0
        return payload
    values, mask, circadian = window
    observed = _observed_count(mask)
    try:
        dimension = _embedding_dimension(values, mask, circadian)
    except Exception:
        payload["available"] = False
        payload["reason"] = FAILED_NOTE
        payload["embedding_metadata"] = _metadata(computed=False)
        payload["observed_points"] = observed
        return payload
    payload["available"] = True
    payload["reason"] = None
    payload["embedding_metadata"] = _metadata(computed=True, dimension=dimension)
    payload["observed_points"] = observed
    return payload


def repositories() -> list[dict]:
    """Public artifacts considered for this adapter. Callers get their own dicts."""
    return [dict(item) for item in _REPOSITORIES]


def _base_payload() -> dict:
    return {
        "model": MODEL_NAME,
        "available": False,
        "kind": "embedding",
        "source_url": SOURCE_URL,
        "disclaimer": DISCLAIMER,
        "estimates": [],
    }


def _trajectory_unavailable() -> dict:
    return {
        "model": MODEL_NAME,
        "available": False,
        "kind": "trajectory",
        "source_url": SOURCE_URL,
        "disclaimer": DISCLAIMER,
        "requires": list(CONTEXT_FIELDS),
        "reason": MISSING_CONTEXT,
        "estimates": [],
    }


def _metadata(*, computed: bool, dimension: int = EMBEDDING_DIM) -> dict:
    return {
        "dimension": dimension,
        "source_repo": SOURCE_URL,
        "computed": computed,
    }


def _encoder_installed() -> bool:
    return _import_onnxruntime() is not None and _encoder_file() is not None


def _import_onnxruntime():
    try:
        import onnxruntime
    except ImportError:
        return None
    return onnxruntime


def _encoder_file() -> str | None:
    """Local ONNX path only. Does not download weights."""
    configured = os.environ.get("GLUCOFM_ENCODER_PATH", "").strip()
    if configured and os.path.isfile(configured):
        return configured
    return _cached_onnx()


def _cached_onnx() -> str | None:
    try:
        from huggingface_hub import try_to_load_from_cache
    except ImportError:
        return None
    previous = os.environ.get("HF_HUB_OFFLINE")
    os.environ["HF_HUB_OFFLINE"] = "1"
    try:
        found = try_to_load_from_cache(REPO_ID, ONNX_FILE)
    except Exception:
        return None
    finally:
        if previous is None:
            os.environ.pop("HF_HUB_OFFLINE", None)
        else:
            os.environ["HF_HUB_OFFLINE"] = previous
    if isinstance(found, str) and os.path.isfile(found):
        return found
    return None


def _build_window(
    series: list[tuple[datetime, float]],
) -> tuple[list[float], list[float], int] | None:
    """Place real readings on a 24-hour 5-minute grid. Gaps stay empty.

    Unobserved slots are 0 in the model input and are not glucose values.
    Two readings in one slot keep the closer stored value. An equal distance
    keeps the later reading. Slots are not averaged, and missing slots are not
    interpolated.
    """
    if not series:
        return None
    last_at = series[-1][0]
    start = last_at - timedelta(hours=24) + STEP
    chosen: dict[int, tuple[float, float]] = {}
    for moment, value in series:
        index = _slot(moment, start)
        if index is None:
            continue
        center = start + STEP * index
        distance = abs((moment - center).total_seconds())
        previous = chosen.get(index)
        if previous is None or distance <= previous[0]:
            chosen[index] = (distance, value)
    if not chosen:
        return None
    values = [0.0] * GRID_POINTS
    mask = [0.0] * GRID_POINTS
    for index, (_distance, value) in chosen.items():
        values[index] = value
        mask[index] = 1.0
    return values, mask, _circadian_index(start)


def _slot(moment: datetime, start: datetime) -> int | None:
    delta = (moment - start).total_seconds()
    index = int(round(delta / STEP.total_seconds()))
    if index < 0 or index >= GRID_POINTS:
        return None
    return index


def _circadian_index(moment: datetime) -> int:
    minutes = moment.hour * 60 + moment.minute + moment.second / 60.0
    return int(round(minutes / 5.0)) % GRID_POINTS


def _observed_count(mask: list[float]) -> int:
    return sum(1 for flag in mask if flag)


def _embedding_dimension(values: list[float], mask: list[float], circadian: int) -> int:
    vector = _run_onnx(values, mask, circadian)
    if len(vector) != EMBEDDING_DIM or any(not math.isfinite(item) for item in vector):
        raise RuntimeError(FAILED_NOTE)
    return len(vector)


def _run_onnx(values: list[float], mask: list[float], circadian: int) -> list[float]:
    onnxruntime = _import_onnxruntime()
    path = _encoder_file()
    if onnxruntime is None or path is None:
        raise RuntimeError(NOT_INSTALLED)
    import numpy as np

    session = _session(path, onnxruntime)
    output = session.run(
        None,
        {
            "values": np.asarray([values], dtype=np.float32),
            "mask": np.asarray([mask], dtype=np.float32),
            "circadian_start": np.asarray([circadian], dtype=np.int64),
        },
    )
    flat = np.asarray(output[0], dtype=np.float64).reshape(-1)
    return [float(item) for item in flat]


def _session(path: str, onnxruntime):
    cached = _SESSIONS.get(path)
    if cached is not None:
        return cached
    session = onnxruntime.InferenceSession(path, providers=["CPUExecutionProvider"])
    names = {item.name for item in session.get_inputs()}
    if not {"values", "mask", "circadian_start"} <= names:
        raise RuntimeError(FAILED_NOTE)
    _SESSIONS[path] = session
    return session
