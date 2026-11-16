-- One E.164 number belongs to one chart.
-- patient_phone_links.phone_e164 is the number inbound and outbound calls
-- resolve. patients.contact_number stays the chart contact and is not replaced.
-- The CareLoop line +14235838428 cannot be stored here.
-- Row level security matches 0001: no policy, so anon and authenticated are
-- denied. service_role is granted DML when that role exists.

CREATE TABLE IF NOT EXISTS patient_phone_links (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id uuid NOT NULL REFERENCES patients (id),
  phone_e164 text NOT NULL,
  label text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT patient_phone_links_phone_e164_key UNIQUE (phone_e164),
  CONSTRAINT patient_phone_links_phone_e164_e164_check CHECK (
    phone_e164 ~ '^\+[1-9][0-9]{1,14}$'
  ),
  CONSTRAINT patient_phone_links_not_careloop_line_check CHECK (
    phone_e164 <> '+14235838428'
  )
);

CREATE INDEX IF NOT EXISTS patient_phone_links_patient_id_idx
  ON patient_phone_links (patient_id);

-- +919372501954 belongs to Ravi Sharma when that chart exists.
-- Meera Iyer keeps chart contact +919840011223 and does not receive this row.
-- +14235838428 stays rejected by the check above.
INSERT INTO patient_phone_links (id, patient_id, phone_e164, label)
SELECT
  'a52a0000-0000-4000-8000-0000000000f1'::uuid,
  'a52a0000-0000-4000-8000-000000000052'::uuid,
  '+919372501954',
  'mobile'
WHERE EXISTS (
  SELECT 1
  FROM patients
  WHERE id = 'a52a0000-0000-4000-8000-000000000052'
)
ON CONFLICT (phone_e164) DO UPDATE
SET
  patient_id = EXCLUDED.patient_id,
  label = EXCLUDED.label;

DO $$
DECLARE
  table_name text;
  phone_tables text[] := ARRAY['patient_phone_links'];
BEGIN
  FOREACH table_name IN ARRAY phone_tables
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
