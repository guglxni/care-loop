# Database

The chart schema is `supabase/migrations/0001_init.sql`. One fictional patient lives in `supabase/seed/0001_synthetic.sql`. That seed is a synthetic demo. It is not a real person and it is not medical advice.

The synthetic patient id is `11111111-1111-4111-8111-111111111111`.

## Apply

From the repository root, point `DATABASE_URL` at Postgres and apply both files with `psql`:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/0001_init.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/seed/0001_synthetic.sql
```

`DATABASE_URL` is the database connection string. The database password and the Supabase service role key stay outside this repository. Do not commit them, paste them into a tracked file, or add them to git history.

Both files can be applied again. The migration uses `IF NOT EXISTS`. The seed uses `INSERT ... ON CONFLICT DO NOTHING`.

## Access

Row level security is enabled on every table. `anon` and `authenticated` have no policies and no table grants. Flask connects as the database owner, or as the Supabase `service_role` when that role exists. Those connections bypass row level security. The browser does not receive that credential.

Keep `patients` closed to the public. Add no policy that grants a public read.

Timestamps are `timestamptz` and stored in UTC. On `health_readings`, `measured_at` is when the measurement was taken. `created_at` is when the row was saved.
