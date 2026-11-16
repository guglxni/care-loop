-- External ingest columns and sync bookkeeping.
-- ingest_origin is synthetic for fixtures, manual for a confirmed person-entered
-- value, or device for a live Nightscout SGV feed. Null means the row was
-- written before this column existed, including the original chart routes.
-- Do not store the Nightscout fixture with source cgm. The glucose source
-- check already allows manual, cgm, and glucometer. The fixture uses glucometer.
-- A physical CGM transmitter is not paired here.

ALTER TABLE health_readings
  ADD COLUMN IF NOT EXISTS ingest_origin text;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'health_readings_ingest_origin_check'
  ) THEN
    ALTER TABLE health_readings
      ADD CONSTRAINT health_readings_ingest_origin_check
      CHECK (
        ingest_origin IS NULL
        OR ingest_origin IN ('synthetic', 'manual', 'device')
      );
  END IF;
END $$;

-- Same patient, type, time, source, device, and value is one reading.
-- Null device_id matches an empty device_id.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_index i
    JOIN pg_class t ON t.oid = i.indrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE n.nspname = 'public'
      AND t.relname = 'health_readings'
      AND i.indisunique
      AND pg_get_indexdef(i.indexrelid) ILIKE '%coalesce(device_id%'
  ) THEN
    CREATE UNIQUE INDEX health_readings_dedupe_uidx
      ON health_readings (
        patient_id,
        measurement_type,
        measured_at,
        source,
        coalesce(device_id, ''),
        value
      );
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS ingest_sync_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id uuid NOT NULL REFERENCES patients (id),
  connector text NOT NULL,
  status text NOT NULL,
  started_at timestamptz NOT NULL,
  finished_at timestamptz,
  inserted_count integer NOT NULL DEFAULT 0,
  duplicate_count integer NOT NULL DEFAULT 0,
  skipped_count integer NOT NULL DEFAULT 0,
  message text,
  CONSTRAINT ingest_sync_runs_status_check CHECK (
    status IN ('ok', 'unavailable', 'partial')
  )
);

CREATE INDEX IF NOT EXISTS ingest_sync_runs_patient_id_started_at_idx
  ON ingest_sync_runs (patient_id, started_at DESC);

CREATE TABLE IF NOT EXISTS document_extractions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id uuid NOT NULL REFERENCES patients (id),
  document_id uuid REFERENCES documents (id),
  document_type text NOT NULL,
  extracted jsonb NOT NULL DEFAULT '{}'::jsonb,
  confirmed boolean NOT NULL DEFAULT false,
  confirmed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS document_extractions_patient_id_idx
  ON document_extractions (patient_id);

-- Same posture as 0001: no policy, so anon and authenticated cannot read
-- these tables. service_role is granted DML when that role exists.
DO $$
DECLARE
  table_name text;
  ingest_tables text[] := ARRAY[
    'ingest_sync_runs',
    'document_extractions'
  ];
BEGIN
  FOREACH table_name IN ARRAY ingest_tables
  LOOP
    EXECUTE format(
      'ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',
      table_name
    );
    EXECUTE format('REVOKE ALL ON TABLE public.%I FROM PUBLIC', table_name);

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
      EXECUTE format('REVOKE ALL ON TABLE public.%I FROM anon', table_name);
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
      EXECUTE format(
        'REVOKE ALL ON TABLE public.%I FROM authenticated',
        table_name
      );
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
      EXECUTE format(
        'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.%I TO service_role',
        table_name
      );
    END IF;
  END LOOP;
END $$;
