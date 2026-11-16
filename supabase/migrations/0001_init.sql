-- Care Loop chart schema.
-- Timestamps are timestamptz and stored in UTC.
-- measured_at is the clinical time of a reading and is distinct from created_at.
-- Row level security is on for every table. There is no policy for anon or
-- authenticated, and those roles receive no table grants. The table owner and
-- the Supabase service_role bypass row level security. Do not add a policy
-- that lets the public read patients.

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'extensions') THEN
    EXECUTE 'CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA extensions';
  ELSE
    EXECUTE 'CREATE EXTENSION IF NOT EXISTS pgcrypto';
  END IF;
END $$;

-- gen_random_uuid() is supplied by pgcrypto. Postgres 13 and later also
-- provide the same function from core.

CREATE TABLE IF NOT EXISTS patients (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  preferred_name text NOT NULL,
  date_of_birth date NOT NULL,
  preferred_language text NOT NULL,
  contact_number text NOT NULL,
  medical_history text NOT NULL DEFAULT '',
  allergies jsonb NOT NULL DEFAULT '[]',
  emergency_contact jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS conditions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id uuid NOT NULL REFERENCES patients (id),
  condition_type text NOT NULL,
  diagnosis_date date NOT NULL,
  treating_clinician text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT conditions_condition_type_check CHECK (
    condition_type IN ('type_2_diabetes', 'hypertension')
  )
);

CREATE TABLE IF NOT EXISTS medications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id uuid NOT NULL REFERENCES patients (id),
  medication_name text NOT NULL,
  prescribed_dosage text NOT NULL,
  frequency text NOT NULL,
  schedule jsonb NOT NULL,
  start_date date NOT NULL,
  end_date date,
  prescribing_clinician text NOT NULL,
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT medications_end_date_check CHECK (
    end_date IS NULL OR end_date >= start_date
  )
);

CREATE TABLE IF NOT EXISTS health_readings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id uuid NOT NULL REFERENCES patients (id),
  measurement_type text NOT NULL,
  value numeric NOT NULL,
  secondary_value numeric,
  unit text NOT NULL,
  measurement_context text,
  measured_at timestamptz NOT NULL,
  source text NOT NULL,
  device_id text,
  data_quality text NOT NULL DEFAULT 'valid',
  support text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT health_readings_measurement_type_check CHECK (
    measurement_type IN (
      'blood_glucose',
      'systolic_blood_pressure',
      'diastolic_blood_pressure',
      'pulse',
      'weight'
    )
  ),
  CONSTRAINT health_readings_data_quality_check CHECK (
    data_quality IN ('valid', 'questionable', 'rejected')
  ),
  CONSTRAINT health_readings_measurement_context_check CHECK (
    measurement_context IS NULL
    OR measurement_context IN ('fasting', 'post_meal', 'other', 'resting')
  ),
  CONSTRAINT health_readings_source_check CHECK (
    (
      measurement_type = 'blood_glucose'
      AND source IN ('manual', 'cgm', 'glucometer')
    )
    OR (
      measurement_type IN (
        'systolic_blood_pressure',
        'diastolic_blood_pressure'
      )
      AND source IN ('manual', 'home_monitor', 'clinic')
    )
    OR (
      measurement_type IN ('pulse', 'weight')
      AND source IN ('manual', 'home_monitor', 'clinic')
    )
  )
);

CREATE TABLE IF NOT EXISTS consultations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id uuid NOT NULL REFERENCES patients (id),
  clinician text NOT NULL,
  appointment_date timestamptz NOT NULL,
  consultation_type text NOT NULL,
  status text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT consultations_consultation_type_check CHECK (
    consultation_type IN ('consultation', 'laboratory', 'follow_up')
  ),
  CONSTRAINT consultations_status_check CHECK (
    status IN ('scheduled', 'completed', 'cancelled', 'rescheduled')
  )
);

CREATE TABLE IF NOT EXISTS care_plans (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id uuid NOT NULL REFERENCES patients (id),
  condition text NOT NULL,
  monitoring_schedule jsonb NOT NULL,
  clinician text NOT NULL,
  approved_rules jsonb NOT NULL DEFAULT '[]',
  escalation_protocol jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS adherence_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id uuid NOT NULL REFERENCES patients (id),
  medication_id uuid NOT NULL REFERENCES medications (id),
  schedule_time timestamptz NOT NULL,
  reported_status text NOT NULL,
  reported_reason text,
  recorded_at timestamptz NOT NULL DEFAULT now(),
  source text NOT NULL,
  CONSTRAINT adherence_logs_reported_status_check CHECK (
    reported_status IN ('taken', 'missed', 'unknown')
  ),
  CONSTRAINT adherence_logs_source_check CHECK (
    source IN ('app', 'call_self_report', 'inferred')
  )
);

CREATE TABLE IF NOT EXISTS care_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id uuid NOT NULL REFERENCES patients (id),
  event_type text NOT NULL,
  event_description text NOT NULL,
  priority text NOT NULL,
  status text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  resolved_at timestamptz,
  CONSTRAINT care_events_priority_check CHECK (
    priority IN ('low', 'medium', 'high')
  ),
  CONSTRAINT care_events_status_check CHECK (
    status IN ('open', 'acknowledged', 'resolved')
  )
);

CREATE TABLE IF NOT EXISTS voice_calls (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id uuid NOT NULL REFERENCES patients (id),
  bolna_call_id text NOT NULL UNIQUE,
  call_type text NOT NULL,
  language text NOT NULL,
  call_status text NOT NULL,
  summary text,
  extracted_data jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT voice_calls_call_type_check CHECK (
    call_type IN ('outbound', 'inbound')
  )
);

CREATE TABLE IF NOT EXISTS webhook_deliveries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  bolna_call_id text NOT NULL,
  delivery_key text NOT NULL UNIQUE,
  payload jsonb NOT NULL,
  received_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id uuid NOT NULL REFERENCES patients (id),
  document_type text NOT NULL,
  file_location text NOT NULL,
  extraction_status text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT documents_document_type_check CHECK (
    document_type IN ('prescription', 'lab_report')
  ),
  CONSTRAINT documents_extraction_status_check CHECK (
    extraction_status IN ('pending', 'extracted', 'failed', 'not_requested')
  )
);

-- Leading patient_id supports chart lookups. The composite indexes also
-- cover equality on patient_id alone.
CREATE INDEX IF NOT EXISTS conditions_patient_id_idx
  ON conditions (patient_id);

CREATE INDEX IF NOT EXISTS medications_patient_id_idx
  ON medications (patient_id);

CREATE INDEX IF NOT EXISTS health_readings_patient_id_measured_at_idx
  ON health_readings (patient_id, measured_at DESC);

CREATE INDEX IF NOT EXISTS consultations_patient_id_appointment_date_idx
  ON consultations (patient_id, appointment_date);

CREATE INDEX IF NOT EXISTS care_plans_patient_id_idx
  ON care_plans (patient_id);

CREATE INDEX IF NOT EXISTS adherence_logs_patient_id_idx
  ON adherence_logs (patient_id);

CREATE INDEX IF NOT EXISTS adherence_logs_medication_id_idx
  ON adherence_logs (medication_id);

CREATE INDEX IF NOT EXISTS care_events_patient_id_idx
  ON care_events (patient_id);

CREATE INDEX IF NOT EXISTS voice_calls_patient_id_idx
  ON voice_calls (patient_id);

CREATE INDEX IF NOT EXISTS documents_patient_id_idx
  ON documents (patient_id);

-- No CREATE POLICY. With row level security enabled and no permissive
-- policy, anon and authenticated are denied. service_role is granted DML
-- when that role exists; on Supabase it bypasses row level security.
DO $$
DECLARE
  table_name text;
  chart_tables text[] := ARRAY[
    'patients',
    'conditions',
    'medications',
    'health_readings',
    'consultations',
    'care_plans',
    'adherence_logs',
    'care_events',
    'voice_calls',
    'webhook_deliveries',
    'documents'
  ];
BEGIN
  FOREACH table_name IN ARRAY chart_tables
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
