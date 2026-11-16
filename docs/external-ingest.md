# External ingest

CareLoop can store glucose that was read from a Nightscout site, or replay a local fixture. It does not pair a physical CGM transmitter, and it does not connect a Bluetooth blood-pressure cuff.

`health_readings.ingest_origin` is nullable:

| Value | Meaning |
| --- | --- |
| `synthetic` | Fixture or other generated demo data. The Nightscout mock route writes this. |
| `manual` | Reserved for a person-entered value after it is confirmed. The original glucose and blood-pressure routes leave the column null. |
| `device` | A live Nightscout SGV entry fetched with the configured site URL. |

Null means the row was stored before this column, or by a chart route that does not set it.

## Nightscout environment

Set these in `backend/.env`. Leave them empty when no site is configured. Do not commit a real token.

- `NIGHTSCOUT_URL` is the site base, such as `https://example.nightscout.example`. Include a path prefix only when the site is hosted under one. Do not append `/api/v1`, and do not put a username, password, or token in the URL.
- `NIGHTSCOUT_API_TOKEN` is sent as the `api-secret` header on every Nightscout request. Nightscout documents that header as the hash of the site `API_SECRET`. CareLoop copies the environment value into the header and does not hash it again.

Live sync calls:

- `GET {NIGHTSCOUT_URL}/api/v1/entries.json?count=288`
- `GET {NIGHTSCOUT_URL}/api/v1/status.json` for `settings.units` only

Only entries with `type` `sgv` are stored. `sgv` becomes the blood glucose value. `dateString` is preferred when it carries a timezone; otherwise `date` is read as epoch milliseconds. `device` becomes `device_id`. `direction`, when present, is stored in `support`.

Units are not converted on write. An entry `units` value of `mmol`, `mmol/L`, or `mg/dl` is stored as `mmol/L` or `mg/dL`. If the entry does not name units, the site status is used the same way. If neither says mmol, the value is stored as `mg/dL`. `glucose_to_mg_dl` (factor 18.0182) exists for comparisons and is not used when saving these rows.

A row is stored only when `sgv` and a usable timestamp are both present. The timestamp must include a timezone and must not be more than five minutes in the future. Incomplete entries, non-`sgv` types, unknown units, and unusable timestamps are skipped and counted. Stored live rows use `source` `cgm`, `ingest_origin` `device`, and `data_quality` `valid`. `measurement_context` is left null because the entry does not say fasting or post-meal.

If the entries request fails, or the URL or token is missing, the sync run status is `unavailable` and the HTTP response is 503 with the usual `{"error": {"code", "message", "details"}}` body. The response is not a stack trace. A failure of the status request does not drop entries that were already fetched; unlabeled values are then stored as `mg/dL`.

## Mock and live

| | Mock | Live |
| --- | --- | --- |
| Route | `POST /api/v1/patients/<patient_id>/ingest/nightscout/mock` | `POST /api/v1/patients/<patient_id>/ingest/nightscout/sync` |
| Data | `backend/app/ingest/fixtures/nightscout_entries.json` | The configured Nightscout site |
| `connector` on the sync run | `nightscout_mock` | `nightscout` |
| `ingest_origin` | `synthetic` | `device` |
| `source` | `glucometer` | `cgm` |
| `support` | `synthetic_nightscout_fixture` on every stored row | the entry `direction`, when it has one |

The fixture is a JSON array of obvious demo entries. Replaying it does not contact Nightscout and does not mean a sensor is connected. `source` `cgm` is only the chart's label for a live Nightscout SGV feed. It is not a claim that a transmitter was paired.

Both success responses are HTTP 201. The body is the `ingest_sync_runs` row plus `ingest_origin` and `source`. The mock body also includes `support`. Run `status` is `ok` when nothing was skipped, and `partial` when at least one entry was skipped. Duplicates are not skips.

`GET /api/v1/patients/<patient_id>/ingest/status` returns the latest `ingest_sync_runs` row for that patient (the table columns only). If that patient has no sync run, the response is 404.

## Duplicates

A reading is a duplicate when this identity already exists:

`patient_id`, `measurement_type`, `measured_at`, `source`, `device_id` (an empty string when null), `value`

The same identity inside one payload is stored once. A later sync of the same identity increments `duplicate_count` and does not insert another row. `health_readings_dedupe_uidx` enforces that identity in Postgres. `support` and `ingest_origin` are not part of the identity, so a second copy with a different note is still a duplicate.

## Sibling routes

These modules own their own HTTP bodies. They are registered on the app when the files exist, under the `/api/v1` prefix:

- `document_routes` confirms document extractions. Rows live in `document_extractions` and stay `confirmed = false` until that module confirms them.
- `bp_routes` owns CSV blood-pressure ingest.
- `forecast_routes` owns the glucose forecast route.

Bluetooth blood-pressure monitors and a physical CGM are not connected.
