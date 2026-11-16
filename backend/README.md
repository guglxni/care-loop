# Care Loop API

Flask is the only writer of the chart. The browser and Bolna do not connect to Postgres. This service does not call Bolna. It receives HTTP from the patient app and from Bolna webhooks.

SQLite is used by `pytest` only. The running API uses Postgres. Do not point `DATABASE_URL` at a SQLite file.

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set `DATABASE_URL` to your Supabase Postgres URI. The example value is the local Supabase default:

`postgresql://postgres:postgres@127.0.0.1:54322/postgres`

For hosted Supabase, copy the connection string from the project settings and put it in `.env`. The app reads `DATABASE_URL` and rewrites a `postgresql://` URL to the psycopg 3 driver. It does not embed a password.

`SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are reserved for later storage work. These endpoints talk to Postgres through `DATABASE_URL` only. Leave the service role out of the browser.

`BOLNA_WEBHOOK_SECRET` may be empty in development. When it is set, `POST /api/v1/bolna/webhook` requires the same value in the `X-Care-Loop-Secret` header. Production (`FLASK_ENV=production`) refuses webhooks until the secret is set. The process never places a Bolna call.

## Schema and seed

Apply the SQL migration yourself. This app does not create tables on startup.

From the repository root, with `DATABASE_URL` exported:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/0001_init.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/seed/0001_synthetic.sql
```

Or, if the Supabase CLI is linked to this project, `supabase db push` applies the migration. Load the seed with the `psql` command above. The seed is fictional: Meera Iyer, `11111111-1111-4111-8111-111111111111`, with both conditions, metformin `22222222-2222-4222-8222-222222222222`, telmisartan `33333333-3333-4333-8333-333333333333`, readings, and consultation `44444444-4444-4444-8444-444444444444` on 2026-11-20.

`flask --app wsgi seed`, run from `backend/`, inserts that same patient when the row is absent. It does not duplicate a chart the SQL seed already loaded. It does not create tables.

## Run

From `backend/`, with the virtualenv active and `.env` in place:

```bash
flask --app wsgi run
```

The API is served at `http://127.0.0.1:5000`. Routes live under `/api/v1`.

## Tests

```bash
cd backend
pytest
```

`tests/conftest.py` overrides `DATABASE_URL` with an in-memory SQLite database, creates the tables, and seeds the same fictional patient. That database is discarded after the tests. It is not a substitute for Postgres.

## Endpoints

| Method | Path | Success |
| --- | --- | --- |
| GET | `/api/v1/patients/<patient_id>` | 200 profile |
| PATCH | `/api/v1/patients/<patient_id>` | 200. Only `preferred_name`, `preferred_language`, `contact_number`, `medical_history`, `allergies`, and `emergency_contact`. A diagnosis, prescription, or dose field is 400 and is not saved. |
| GET | `/api/v1/patients/<patient_id>/history` | 200 chart: conditions, medications, recent readings, consultations, care plan summary, document metadata |
| POST | `/api/v1/patients/<patient_id>/readings/glucose` | 201 one glucose row |
| POST | `/api/v1/patients/<patient_id>/readings/blood-pressure` | 201 `{"readings": [...]}`. Systolic `secondary_value` is the diastolic. A pulse, when sent, is a third row. |
| GET | `/api/v1/patients/<patient_id>/medications` | 200 active medication schedules |
| POST | `/api/v1/patients/<patient_id>/adherence` | 201 one adherence row for an existing medication. A dose change is 400. |
| GET | `/api/v1/patients/<patient_id>/consultations/upcoming` | 200 `{"consultation": ...}` or `{"consultation": null}` |
| POST | `/api/v1/consultations/<consultation_id>` | 200 updated status and/or `appointment_date` |
| GET | `/api/v1/patients/<patient_id>/care-events` | 200 |
| POST | `/api/v1/patients/<patient_id>/care-events` | 201. `event_description` is stored as submitted. |
| GET | `/api/v1/patients/<patient_id>/bolna/context?purpose=glucose_check\|bp_check\|medication_check\|appointment_reminder\|general` | 200 allow-listed call packet |
| POST | `/api/v1/patients/<patient_id>/bolna/call-outcomes` | 201 insert or 200 update, keyed by `bolna_call_id` |
| POST | `/api/v1/bolna/webhook` | 200. The same delivery key returns `{"duplicate": true}` and does not insert another voice call. If no patient can be resolved, 202 `{"ignored": true}` and no voice call is stored. |

Timestamps must include a timezone offset. The API stores UTC and returns ISO 8601 with a `Z` suffix. `measured_at` more than five minutes in the future is rejected. Glucose outside `20 < mg/dL < 600` or `1 < mmol/L < 33` is a validation error. The response does not label a reading high or low.

Unknown patients and consultations return `404` with `{"error": {"code": "not_found", "message", "details"}}`. Validation failures return `400` with code `validation_error` and a `details` list.

The voice packet contains only the patient id, preferred name, language, purpose, due medicine names and today's times, the latest glucose and blood pressure when they exist, the next consultation when it exists, and this instruction:

`Record what the patient reports. Do not diagnose, prescribe, or change medicines. Ask a clinician to review urgent concerns.`
