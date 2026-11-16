# Phase 1 audit — CareLoop call loop

Audit only. No app rewrite, no commit, no outbound call, and no Bolna write. Probes below are from 15 Nov 2026, after the API process restarted at 16:11 IST. Another agent (`a2beda54`) was already changing the remind route, the tunnel, `backend/.env`, `DEMO.md`, and the live graph agent while this was read. Treat the Bolna snapshot as time-sensitive.

Meera Iyer (`11111111-1111-4111-8111-111111111111`, chart contact `+919840011223`) is synthetic and must never be dialed. The number typed into "Call me" in the screenshot is the wrong product and was not dialed. Ravi Sharma was not created.

## What already works

### Frontend routes (read from `web/src/App.tsx`)

These routes are registered. This audit did not click through them.

| Path | Page |
| --- | --- |
| `/` | Dashboard |
| `/profile` | Profile |
| `/glucose` | Glucose |
| `/blood-pressure` | Blood pressure |
| `/ingest` | Ingest |
| `/medications` | Medications |
| `/calendar` | Calendar |
| `/reports` | Reports |
| `/companion` | Companion ("Call me") |
| `/showcase` | Showcase |
| any other path | Redirects to `/` |

The dashboard "Today's follow-through" rows are links to `/companion?purpose=medication_check|glucose_check|bp_check|appointment_reminder` (`web/src/pages/dashboard/DashboardPage.tsx`). The companion page can POST a check-in (`web/src/pages/companion/remindApi.ts`).

### Backend voice path (tests executed)

Ran with the backend virtualenv, in-memory SQLite, and the Bolna call function mocked:

`backend/.venv/bin/pytest tests/test_remind.py tests/test_voice.py tests/test_patients.py::test_routes_are_registered -q`

**22 passed** in 0.33s. Pytest did not dial.

`tests/test_remind.py` covers:

- `+919840011223` is rejected, including the spaced form `+91 98400 11223`
- the CareLoop line `+14235838428` is rejected
- a default body queues `medication_check` for Meera, language `en`, status `queued`, and stores a `voice_calls` row
- an explicit `glucose_check` is passed through
- an empty body with no `USER_PHONE_NUMBER` is a validation error

`tests/test_voice.py` covers the allow-listed context packet, call-outcome upsert, idempotent webhook storage, patient resolution from `context_details.recipient_data`, a 202 when the patient cannot be resolved, and the webhook secret when one is configured. `test_webhook_is_idempotent_and_does_not_write_the_chart` shows a webhook stores a voice-call row and does not insert a glucose reading.

Importing the app in this worktree registers:

- `GET /api/v1/patients/<patient_id>/bolna/context`
- `POST /api/v1/patients/<patient_id>/bolna/remind`
- `POST /api/v1/patients/<patient_id>/bolna/call-outcomes`
- `POST /api/v1/bolna/webhook`

`test_routes_are_registered` still passes without listing `bolna/remind`. It checks a subset, so it does not prove the remind route exists. The import above does.

### Agent and number

Verified with Bolna `get_agent` and `get_graph_agent` for `8ad7201e-2fe5-4595-8a45-35ed60fb1fcd`:

- Name: CareLoop AI Health Companion
- Status: `processed`
- Type: graph agent, model `gpt-4.1-mini`, transcriber Deepgram `nova-3`, voice ElevenLabs "Nila"
- `inbound_phone_number`: `8820ada7-a2c5-44c5-b658-ea3109b6b702`
- `updated_at`: `2026-11-15T10:38:44Z`
- Graph `validation.valid` is true. One warning: four purpose edges on `start` share priority 0 (`duplicate_transition_priorities`)
- Nodes: `start`, `medication`, `glucose`, `blood_pressure`, `consultation`, `concern`, `escalation`, `close`
- Expression routes on `recipient_data.purpose`: `medication_check`, `glucose_check`, `bp_check`, `appointment_reminder`
- Nine `api_tools` are set: `get_context`, `get_medications`, `get_history`, `post_glucose`, `post_blood_pressure`, `post_adherence`, `get_upcoming_consultation`, `post_follow_up_task`, `post_clinical_escalation`
- Five disposition ids are attached. Their question text was not read
- `get_user_info`: wallet balance 1000, concurrency 0 of 2. No call was in progress

The code's from-number is `+14235838428` (`backend/app/services/bolna_outbound.py`). `list_phone_numbers` failed again with `GET /phone-numbers/all returned object with keys [bolna, user] instead of a list`. This session did not read the E.164 from that inventory. The id on the agent matches the known inbound phone id. The E.164 mapping is the known fact plus the hardcoded from-number, not a fresh inventory read.

### Local API and tunnel (probed, not dialed)

- Flask is listening on `127.0.0.1:5055` (pid 95692, started 16:11:31 IST, `flask --app wsgi run --host 127.0.0.1 --port 5055`). An earlier pid, 94479, was on that port at the start of this audit and was replaced.
- `GET http://127.0.0.1:5055/api/v1/patients/11111111-1111-4111-8111-111111111111/bolna/context?purpose=medication_check` returned **200**. Preferred name Meera Iyer, language `en`, next clinician Dr. Anika Shah.
- Port **5000** is AirPlay (`ControlCenter`), not Flask. The same context URL returned **403** with an empty body.
- Vite is listening on `127.0.0.1:5173` and `[::1]:5173`. `GET` of the same context path through both origins returned **200**. The dev server proxies `/api` to 5055, then 5000 (`web/vite.config.ts`).
- `cloudflared tunnel --url http://127.0.0.1:5055` is running (since 15:59 IST).
- The agent `webhook_url` is `https://echo-criterion-revolutionary-months.trycloudflare.com/api/v1/bolna/webhook`. The nine tool URLs use that same host.
- `GET` of Meera's context through that host returned **200** with the same identity as localhost.
- `GET` of the webhook URL returned **405** method not allowed. The route is present and is POST-only. This audit did not POST a webhook and did not POST `/bolna/remind`.

`DEMO.md`, `docs/bolna-demo-link.md`, `docs/hackathon.md`, and the showcase page still say `webhook_url` is unset and `api_tools` is null. That was true in those docs. It was false on the live agent at the time of `get_agent`.

## What is incomplete

- The dashboard never asks the API to call. Follow-through is a navigation link into the companion form.
- The companion form is a free-typed "Call me" destination. That is the wrong product. The language dropdown on that page is not sent. The POST body is only `{ to, purpose }` for Meera's patient id.
- The browser cannot call `127.0.0.1:5055` directly. An `OPTIONS` preflight from origin `http://127.0.0.1:5173` returned 200 with `Allow: OPTIONS, POST` and no `Access-Control-Allow-Origin`. `remindApi.ts` then tries port 5000, which is AirPlay, then the Vite origin.
- The running process has no `BOLNA_API_KEY` and no `USER_PHONE_NUMBER`. `backend/.env` does not exist. `BOLNA_WEBHOOK_SECRET` is empty. `FLASK_ENV` is `development`. `DATABASE_URL` is a SQLite URL, not the Postgres URL in `backend/.env.example`.
- `start_outbound_call` raises `BOLNA_API_KEY is required to place a call` before it contacts Bolna. The route turns that into HTTP 502, "The outbound reminder was not placed".
- There is no `GET` for `voice_calls`. The dashboard and the companion's recent-call list render `web/src/data/demo.ts`. A webhook cannot change those screens.
- The webhook stores a voice-call row. It does not copy readings, adherence, or care events onto the chart. Those writes are the agent's separate tool calls.
- Tool `api_token` values are null, and the agent `webhook_headers` are null. Context and chart routes do not check `X-Care-Loop-Secret`. That header is checked only on `POST /api/v1/bolna/webhook`, and the running secret is empty, so development accepts an unsigned webhook.
- `call_summary_enabled` is false on the agent.
- The public host is a Cloudflare quick tunnel. It dies when that `cloudflared` process exits. The agent would keep the dead URL until someone updates it.
- The UI chart says Meera's preferred language is Hindi (`web/src/data/demo.ts`). The live context packet and the seed chart say `en`.
- Ingest still targets `http://127.0.0.1:5000` (`web/src/pages/ingest/ingestApi.ts`). That port is AirPlay.
- The graph has no onboarding purpose and no weekly-check-in purpose.
- Ravi Sharma does not exist in the seed.

## The break

Requested loop: dashboard button → backend → Bolna `start_outbound_call` → phone rings → webhook → dashboard update.

1. **Dashboard button.** The follow-through control is `<Link to="/companion?purpose=...">`. It opens the companion page. It does not POST.
2. **Companion form.** "Call me" requires a typed E.164 number, then `requestCheckIn` POSTs `/api/v1/patients/11111111-1111-4111-8111-111111111111/bolna/remind`. The client blocks `+919840011223` and `+14235838428` before the network. A direct browser call to 5055 fails the CORS check. Port 5000 is AirPlay. The same-origin Vite proxy is the path that can reach Flask, and a context `GET` through it returned 200 during this audit. The "Could not reach the CareLoop API" string is what the proxy returns when both 5055 and 5000 fail, and it is also the client error when those fetches throw and the Vite origin fails too. Flask was down at the beginning of this session and was up on 5055 by 16:11. This audit did not submit the form, so it did not see the current on-screen string.
3. **Backend → Bolna.** If a POST arrives, `queue_reminder` builds `user_data` (`patient_id`, `preferred_language`, `purpose`, `reason`) and calls `start_outbound_call` with agent `8ad7201e-2fe5-4595-8a45-35ed60fb1fcd` and from-number `+14235838428`. The running process has no `BOLNA_API_KEY`, so the function stops before `POST https://api.bolna.ai/call`. The phone does not ring. This hop was read in code and confirmed by the process environment. It was not executed against the live route.
4. **Webhook.** The agent webhook URL and tool URLs point at the live tunnel. A context `GET` through the tunnel returned 200. The webhook route exists. Nothing in this audit produced a Bolna webhook, so delivery after a real call is not verified.
5. **Dashboard update.** There is no read API for `voice_calls`, and the dashboard renders demo fixtures plus the in-browser dose tracker. A stored webhook would leave the dashboard unchanged.

The loop stops at hop 3 for any request that actually reaches Flask: **no Bolna API key is loaded, so `start_outbound_call` never runs.** Hop 1 is why the product still depends on the typed "Call me" form.

## Credentials, public URL, from-number, tools

| Piece | State at probe time | How it was checked |
| --- | --- | --- |
| `BOLNA_API_KEY` | Absent from the 5055 process. `backend/.env` absent. Example file leaves it blank. | Process environment, names and lengths only. The value was not printed. |
| `USER_PHONE_NUMBER` | Absent. Remind then requires `to` in the body, which is the typed-number flow. | Same process environment. |
| `BOLNA_WEBHOOK_SECRET` | Present and empty. Development mode skips the check. | Same process environment. |
| `DATABASE_URL` | Set to SQLite on the process. `.env.example` shows local Postgres. Supabase URL and service-role key are absent. | Scheme only. |
| Public URL | Set on the agent, and the tunnel answered a context GET. Quick-tunnel lifetime is the `cloudflared` process. | `get_agent` plus HTTP GET. |
| From-number | Code sends `+14235838428`. Agent inbound slot holds phone id `8820ada7-a2c5-44c5-b658-ea3109b6b702`. Inventory tool could not list numbers. | Code read. Agent field verified. E.164 not re-listed from Bolna. |
| Agent tools | Nine tools, URLs on the tunnel, `api_token` null. | `get_graph_agent`. |
| Wallet | 1000 credits, 0 of 2 calls in flight. Enough for one short call. No call was placed. | `get_user_info`. |

## Files to change next, and files to leave alone

### Leave to agent `a2beda54`

Do not edit these while that work is in flight:

- `backend/app/routes/bolna.py` (remind route and the webhook in the same module)
- `backend/.env` (not on disk yet; that agent owns creating it)
- `DEMO.md`
- The live graph agent `8ad7201e-2fe5-4595-8a45-35ed60fb1fcd` (`webhook_url`, `api_tools`, node prompts)

Also stay out of the remind implementation and the tunnel process, which that work is already touching:

- `backend/app/services/reminder_service.py`
- `backend/app/services/bolna_outbound.py`
- the running `cloudflared` process

### Safe for the next editor

- `web/src/pages/dashboard/DashboardPage.tsx` — follow-through should request one reminder, not open a phone form
- `web/src/pages/companion/CompanionPage.tsx` and `web/src/pages/companion/remindApi.ts` — stop treating a typed number as the product; keep the block on Meera's number and the CareLoop line
- A new read route for the latest voice call, in a new module, after `bolna.py` is free
- `web/src/data/demo.ts` — only when a screen starts reading live call rows; the Hindi label disagrees with the API
- `docs/bolna-demo-link.md`, `docs/hackathon.md`, and `web/src/pages/showcase/ShowcasePage.tsx` — they still say the webhook and tools are unset. Update them after the tunnel work settles, not during it
- `backend/app/services/seed_service.py` — only in the Ravi phase, not now

## Phases 2–6

Do not create Ravi in phase 1. Do not dial Meera. Do not dial the screenshot number. The first real ring goes to a number the operator confirms, stored as `USER_PHONE_NUMBER`, while the chart contact stays blocked.

### Phase 2 — one real outbound call

1. Let the in-flight tunnel, webhook, and remind edits land.
2. Put `BOLNA_API_KEY` in `backend/.env` and restart the 5055 process. Do not commit the key.
3. Set `USER_PHONE_NUMBER` to the operator's own phone only after they confirm it. Leave it empty until then.
4. Change dashboard follow-through so "Medicine check" POSTs `purpose=medication_check` and sends no typed `to`. The server uses `USER_PHONE_NUMBER`. Patient id for this single call can stay Meera's chart id so the existing seed answers `get_context`. The dialed number is the operator number, never `+919840011223`.
5. Success looks like one execution id, one ring, one `voice_calls` row updated by the webhook, and no second call. The dashboard will still show fixtures until phase 6.

### Phase 3 — onboarding, Ravi Sharma

Add a new synthetic patient: Ravi Sharma, age 52, type 2 diabetes and hypertension, CityCare Clinic, Dr. Mehta, English. New id. New chart phone that is not Meera's and is not the operator's live number. Keep that chart phone on the do-not-dial list.

The graph has no onboarding purpose. Add one only after agent `a2beda54` is finished with the graph, or place the first Ravi call as `appointment_reminder` against a CityCare visit with Dr. Mehta. `user_data.patient_id` is Ravi's id. The dialed number stays the operator number.

### Phase 4 — missed medication

Use the existing `medication_check` purpose. The spoken outcome is a missed dose. The agent should call `post_adherence` with `reported_status=missed` and must not change the dose. `tests/test_medications.py::test_record_adherence_does_not_change_dosage` already locks that rule; re-run it when the scenario is wired. Confirm one adherence row for Ravi.

### Phase 5 — weekly check-in

The graph has no weekly purpose. Define one English call that covers medicine, a glucose reading, and a blood pressure reading, using the tools already on the agent. Record only numbers he speaks. One reading is not a diagnosis. Do this after phases 2–4 have each completed once.

### Phase 6 — dashboard shows the call

Add a read of the latest voice call and any care event from that call. Point the dashboard and the companion history at that read. Retire the fixture call list for those slots. Align the on-screen language with the chart (`en` for both Meera's seed chart and Ravi). The webhook secret should be set before this is shown on a public tunnel, and tool calls should send it, once `bolna.py` is free to take that change.

## Verified vs read

**Verified in this session**

- Bolna `get_agent`, `get_graph_agent`, and `get_user_info` for the agent id above
- `list_phone_numbers` fails with the `[bolna, user]` shape error
- Process environment on pid 95692: no API key, no user phone, empty webhook secret, development, SQLite
- `backend/.env` is absent
- Listeners: Flask on 5055, AirPlay on 5000, Vite on 5173, `cloudflared` to 5055
- Context GET 200 on localhost, through both Vite origins, and through the tunnel host. Identity: Meera Iyer, `en`, Dr. Anika Shah
- Webhook URL GET returns 405
- OPTIONS to the remind path has no CORS allow-origin header
- Pytest: 22 passed in `test_remind.py`, `test_voice.py`, and `test_routes_are_registered`
- App import lists the four Bolna routes, including remind

**Read, not executed**

- Dashboard, companion, demo fixtures, and Vite proxy source
- `reminder_service.py`, `bolna_outbound.py`, `voice_service.py`, seed chart, and `.env.example`
- `DEMO.md`, `docs/bolna-demo-link.md`, `docs/hackathon.md` (stale relative to the live agent)
- Frontend routes were not opened in a browser
- `POST /bolna/remind` was not sent to the live server
- No Bolna call, no webhook delivery, no tool POST, no phone ring
- Disposition definitions were not fetched
- The from-number E.164 was not returned by `list_phone_numbers` in this session
