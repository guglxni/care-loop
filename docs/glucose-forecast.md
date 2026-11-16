# Glucose forecast

CareLoop can show a short numeric glucose estimate next to stored readings. The estimate is for care-coordination display. It is not a glucose measurement, not a diagnosis, not dose advice, and not a sensor.

The routes are `GET /api/v1/patients/<patient_id>/ingest/glucose/forecast` and `GET /api/v1/patients/<patient_id>/ingest/glucose/representation`. The Flask blueprint is `glucose_forecast` in `backend/app/ingest/forecast_routes.py`, with `url_prefix` `/api/v1`. Nothing in this path writes `health_readings`. A forecast or embedding is never labeled `ingest_origin: device`.

## What was found

### GlucoFM

GlucoFM is a real research project. The paper is [GlucoFM: A Dual-Stream Foundation Model for Continuous Glucose Monitoring](https://arxiv.org/abs/2605.30865) (Zechen Li and co-authors, Google Research and UNSW; submitted 29 May 2026, revised 25 August 2026, [v2 HTML](https://arxiv.org/html/2605.30865v2)).

It learns frozen representations from continuous glucose monitoring (CGM) traces. Those representations are evaluated on phenotype classification (diabetes risk, insulin resistance, beta-cell dysfunction, and related tasks). Combined with recent CGM, meal nutrition, and subject context, the same frozen encoder is also evaluated on two-hour postprandial glycemic response: trajectory, incremental area under the curve, peak rise, and peak timing. The 29 May 2026 version says the work does not target short-term glucose forecasting ([v1 HTML](https://arxiv.org/html/2605.30865v1)). The August revision adds the postprandial evaluation and still limits the claims to retrospective tasks.

The paper says GlucoFM is a research prototype, has not been cleared or approved by any regulatory authority, and is not intended to diagnose, treat, cure, or prevent any disease or to replace professional medical advice. It does not output clinical advice.

The August revision says: "We will release the code and reproducibility scripts to support transparent evaluation and future CGM foundation-model research." That sentence has no URL. Checked again on 15 November 2026, there is still no official installable package or Google checkpoint. The forecast route does not emit official GlucoFM glucose numbers. An unofficial encoder can be attached as an embedding companion. That companion is not a measurement.

Places checked:

- Paper: [abs](https://arxiv.org/abs/2605.30865) and [v2 HTML](https://arxiv.org/html/2605.30865v2). Code is promised, not linked. Inputs for the only numeric glucose-trajectory task are recent CGM plus meal nutrition and subject context (fasting glucose, BMI, and diabetes status). CareLoop's forecast route has stored glucose only and must not invent the missing context.
- Google Research blog: [GlucoFM: Foundation model for continuous glucose monitoring](https://research.google/blog/glucofm-foundation-model-for-continuous-glucose-monitoring) (26 August 2026). The quick link is the paper. No code or weight link.
- Author page: [zechenli03.github.io](https://zechenli03.github.io). The GlucoFM entry links the paper, the Google blog, LinkedIn, and X. It does not link code, unlike the author's other papers. [github.com/zechenli03](https://github.com/zechenli03?tab=repositories) has no GlucoFM repository.
- Google Research GitHub: [repository search for GlucoFM](https://github.com/google-research?q=GlucoFM&type=repositories) returned no repositories. [CRUISE Research Group search](https://github.com/search?q=org%3Acruiseresearchgroup+GlucoFM&type=repositories) returned no repositories.
- GitHub name search: [GlucoFM repositories](https://github.com/search?q=GlucoFM&type=repositories) and [topic glucofm](https://github.com/topics/glucofm). The four public hits are unofficial: [sfourdrinier/opencgm](https://github.com/sfourdrinier/opencgm) ("not Google's implementation or checkpoint"), [ViSaReVe/glucofm-replication](https://github.com/ViSaReVe/glucofm-replication), [eugenehp/glucofm-rs](https://github.com/eugenehp/glucofm-rs), and [oliviashen953/glucofm-bench-replication](https://github.com/oliviashen953/glucofm-bench-replication) (a benchmark replication, not this model).
- Hugging Face: [paper page](https://huggingface.co/papers/2605.30865) and [model search](https://huggingface.co/api/models?search=glucofm). The only model hit is [eugenehp/glucofm-encoder](https://huggingface.co/eugenehp/glucofm-encoder), a community conversion of OpenCGM that says official Google weights are not public and is a feature-extraction encoder, not a glucose forecast. [sfourdrinier/opencgm-stateevent](https://huggingface.co/sfourdrinier/opencgm-stateevent) is the same reconstruction. [glucofmbench/GlucoFM-Bench](https://huggingface.co/datasets/glucofmbench/GlucoFM-Bench) is a dataset.
- Package indexes: [pypi.org/pypi/glucofm/json](https://pypi.org/pypi/glucofm/json) returned 404. [docs.rs/glucofm](https://docs.rs/glucofm/latest/glucofm) is the unofficial Rust port and states that official Google weights are not public.

A separate benchmark paper, [GlucoFM-Bench](https://arxiv.org/abs/2606.06881), evaluates generic time-series models on glucose forecasting. That paper is not the GlucoFM model. PyPI still has no `glucofm` package (`https://pypi.org/pypi/glucofm/json` returned 404). The unofficial artifacts below were checked from their READMEs on 15 November 2026.

## What was added

The smallest artifact that can run without a multi-GB download is [eugenehp/glucofm-encoder](https://huggingface.co/eugenehp/glucofm-encoder). It is a community ONNX conversion of [sfourdrinier/opencgm-stateevent](https://huggingface.co/sfourdrinier/opencgm-stateevent), which is itself the [sfourdrinier/opencgm](https://github.com/sfourdrinier/opencgm) reconstruction. The model card says official Google weights are not public. The file `glucofm_encoder.onnx` is about 2 MB (`size_bytes` 1991782 in `glucofm_encoder.onnx.meta.json`). The Hub repo stores about 14 MB across every format. The card lists 435,505 encoder parameters, MIT weights, and a feature-extraction output of shape `[B, 128]`. Inputs are `values` `[B, 288]`, `mask` `[B, 288]` (`0` unobserved, `1` observed), and `circadian_start` `[B]`. The ONNX metadata says never interpolate before the mask. The OpenCGM README says the same.

`backend/app/ingest/glucofm.py` loads that ONNX file only when `onnxruntime` imports and a local file is already present. The local file is `GLUCOFM_ENCODER_PATH`, or the Hugging Face cache entry from `try_to_load_from_cache` with `HF_HUB_OFFLINE=1`. The adapter does not call `hf_hub_download` or `snapshot_download`. Tests do not download it. When the encoder is not installed the companion is `available: false` with reason `unofficial GlucoFM encoder not installed`.

Stored glucose is placed on the 288-slot, 5-minute day that ends at the latest reading. Empty slots stay empty. They are not filled, averaged, or returned as mg/dL. When the ONNX session returns a finite 128-d vector, the response exposes embedding metadata only: `dimension` and `source_repo`. The vector is not copied into `estimates` and is not converted to mg/dL.

The forecast response keeps TimesFM at `model: "timesfm"` and adds a `glucofm` object. The representation response lists `timesfm`, `glucofm`, and the repository URLs. Every GlucoFM `model` field is `unofficial reconstruction: eugenehp/glucofm-encoder`. The disclaimer is:

`Unofficial reconstruction. Not Google's GlucoFM checkpoint. Not a glucose measurement and not medical advice.`

Install, when an operator chooses to, with:

```bash
pip install onnxruntime
# Download once, outside pytest. The ONNX file is about 2 MB.
huggingface-cli download eugenehp/glucofm-encoder glucofm_encoder.onnx --local-dir /path/to/glucofm
export GLUCOFM_ENCODER_PATH=/path/to/glucofm/glucofm_encoder.onnx
```

## What was refused

These public artifacts were not wired in as runtimes:

- [sfourdrinier/opencgm](https://github.com/sfourdrinier/opencgm). Code is Apache-2.0. The README says dataset and weight licenses are separate (`NOTICE`, `LICENSE-WEIGHTS`) and that this is not Google's implementation or checkpoint. Install is the `just` recipes in the README (`just status`, `just gate`), not a small library import. `Analyser.load` needs a local torch checkpoint. `analyse_day` also returns glucose summary statistics and phenotype probabilities. Those are not returned here.
- [ViSaReVe/glucofm-replication](https://github.com/ViSaReVe/glucofm-replication). MIT code. README install is `python -m pip install -e '.[dev]'` then `pytest -q`. The encoder mean-pools to a 128-d vector. The repo ships no checkpoint. Running the architecture from random initialization would not be this reconstruction. The README says v2 post-meal experiments are out of scope.
- [eugenehp/glucofm-rs](https://github.com/eugenehp/glucofm-rs). MIT or Apache-2.0. README install is the crate `glucofm = "0.1"` on Rust 1.89+. `encode_embedding_day` returns 128 floats. The quick start constructs a new CPU model from a random seed. Weights are the separate Hugging Face repo above. This Python service uses that ONNX file instead of the Rust crate.
- [glucofmbench/GlucoFM-Bench](https://huggingface.co/datasets/glucofmbench/GlucoFM-Bench). CC BY-NC-SA 4.0 dataset, about 46 MB. It is a forecasting benchmark of other models, not the GlucoFM encoder. Its README says short gaps are linearly interpolated. It is not downloaded.
- The paper's two-hour postprandial trajectory. That task needs recent glucose plus meal nutrition and subject context (fasting glucose, BMI, and diabetes status). CareLoop has no meal-nutrition table and no BMI field. The companion's `trajectory_forecast` stays `available: false` with the required field names, and the demo does not invent a meal. Embeddings are not turned into an mg/dL forecast.
- Official Google GlucoFM. Still no checkpoint, package, or repo URL in the paper or the [Google Research blog](https://research.google/blog/glucofm-foundation-model-for-continuous-glucose-monitoring).
- Writing any of these outputs into `health_readings`, or setting `ingest_origin` to `device`.

Exact repository URLs:

- https://github.com/sfourdrinier/opencgm
- https://github.com/ViSaReVe/glucofm-replication
- https://github.com/eugenehp/glucofm-rs
- https://huggingface.co/eugenehp/glucofm-encoder
- https://huggingface.co/datasets/glucofmbench/GlucoFM-Bench
- https://arxiv.org/abs/2605.30865
- https://research.google/blog/glucofm-foundation-model-for-continuous-glucose-monitoring

## TimesFM

TimesFM (Time Series Foundation Model) is Google Research's pretrained model for numeric time-series forecasting. It forecasts future values of a series. It does not output clinical advice, doses, or diagnoses.

- Repository: [google-research/timesfm](https://github.com/google-research/timesfm)
- Paper: [A decoder-only foundation model for time-series forecasting](https://arxiv.org/abs/2310.10688), ICML 2024
- Current package: [`timesfm` on PyPI](https://pypi.org/project/timesfm/) (3.0.2 as of this note)
- Checkpoints: [TimesFM on Hugging Face](https://huggingface.co/collections/google/timesfm-release), including [timesfm-2.5-200m-pytorch](https://huggingface.co/google/timesfm-2.5-200m-pytorch) and [timesfm-3.0-pytorch](https://huggingface.co/google/timesfm-3.0-pytorch)

Install, when an operator chooses to, with:

```bash
pip install timesfm[torch]
```

Weights are a separate download. TimesFM 2.5 is about 200M parameters. TimesFM 3.0 is larger. The open-source README states that TimesFM 3.0 self-hosted weights use a non-commercial, non-production license, while weights through 2.5 remain Apache-2.0. This adapter does not download checkpoints. It runs only when `timesfm` imports and a checkpoint is already on disk (`google/timesfm-2.5-200m-pytorch`, then `google/timesfm-1.0-200m-pytorch`, then `google/timesfm-3.0-pytorch`). The call is capped at 15 seconds. If import fails, or a run would need a large download, the response stays `available: false`, `origin: "unavailable"`, `model: "timesfm"`, and `estimates: []`. It does not invent TimesFM numbers. When the library is missing, the disclaimer adds: "The timesfm model library is not installed."

## Where a forecast is safe to show

Show it on a care-coordination screen that already lists stored glucose, with the disclaimer visible and the points labeled as estimates. The history is the latest 36 stored `blood_glucose` rows for that patient, oldest first. mmol/L rows are converted to mg/dL. Fewer than 6 stored glucose points returns an empty estimate list. The screen must not draw those points as CGM, a device ingest, or a confirmed reading.

Do not show it as a live sensor, a replacement for a meter, a diagnosis, or insulin or medication advice. Do not store the points in `health_readings`.

The fixed TimesFM disclaimer is:

`Forecast only. Not a glucose measurement and not medical advice.`

The GlucoFM companion is metadata for a 128-d embedding. Show its own disclaimer with that metadata. Do not draw the embedding as a glucose series.
