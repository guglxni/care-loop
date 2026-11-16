-- Synthetic Ravi Sharma chart. Not a real person. This file does not place a call.
-- Apply supabase/migrations/0001_init.sql and 0002_ingest.sql before this seed.
--
-- Stored contact +15555501052 is synthetic and is not a real person.
-- Outbound tests must use the operator-entered participant number, never this
-- stored contact.
--
-- The evening metformin 500 mg dose at 20:00 is scheduled and unconfirmed.
-- This seed inserts no adherence log for it. Do not mark that dose missed
-- until a call result says so. POST /api/v1/demo/ravi/reset restores this state.
-- Onboarding stays not onboarded: there is no voice_calls row, and voice calls
-- are allowed only after a call records consent.

INSERT INTO patients (
  id,
  preferred_name,
  date_of_birth,
  preferred_language,
  contact_number,
  medical_history,
  allergies,
  emergency_contact
)
VALUES (
  'a52a0000-0000-4000-8000-000000000052',
  'Ravi Sharma',
  '1974-03-18',
  'en',
  '+15555501052',
  'Synthetic chart for CityCare Clinic. Not a real patient. Type 2 diabetes and hypertension are followed by Dr. Mehta. Voice calls are allowed only after consent. Onboarding stays not onboarded until a call records consent. The stored contact +15555501052 is synthetic and is not a real person. Outbound tests must use the operator-entered participant number, never this stored contact.',
  '[]'::jsonb,
  '{
    "name": "CityCare Clinic desk",
    "relation": "Clinic",
    "note": "Synthetic chart contact. No outbound number is stored here."
  }'::jsonb
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO conditions (
  id,
  patient_id,
  condition_type,
  diagnosis_date,
  treating_clinician
)
VALUES
  (
    'a52a0000-0000-4000-8000-0000000000d1',
    'a52a0000-0000-4000-8000-000000000052',
    'type_2_diabetes',
    '2019-03-18',
    'Dr. Mehta'
  ),
  (
    'a52a0000-0000-4000-8000-0000000000d2',
    'a52a0000-0000-4000-8000-000000000052',
    'hypertension',
    '2021-11-02',
    'Dr. Mehta'
  )
ON CONFLICT (id) DO NOTHING;

INSERT INTO medications (
  id,
  patient_id,
  medication_name,
  prescribed_dosage,
  frequency,
  schedule,
  start_date,
  prescribing_clinician,
  active
)
VALUES (
  'a52a0000-0000-4000-8000-0000000000e1',
  'a52a0000-0000-4000-8000-000000000052',
  'Metformin',
  '500 mg',
  'Once daily',
  '{"times":["20:00"]}'::jsonb,
  '2024-06-01',
  'Dr. Mehta',
  true
)
ON CONFLICT (id) DO NOTHING;

-- Glucose on 9, 10, 12, 13, and 15 Nov 2026. 11 Nov and 14 Nov have no reading.
-- Times are clinic local (+05:30). ingest_origin synthetic is fixture data.
INSERT INTO health_readings (
  id,
  patient_id,
  measurement_type,
  value,
  secondary_value,
  unit,
  measurement_context,
  measured_at,
  source,
  device_id,
  data_quality,
  ingest_origin
)
VALUES
  (
    'a52a0000-0000-4000-8000-000000000101',
    'a52a0000-0000-4000-8000-000000000052',
    'blood_glucose',
    128,
    NULL,
    'mg/dL',
    'fasting',
    '2026-11-09 07:10:00+05:30',
    'glucometer',
    'synthetic-ravi-glucometer',
    'valid',
    'synthetic'
  ),
  (
    'a52a0000-0000-4000-8000-000000000102',
    'a52a0000-0000-4000-8000-000000000052',
    'blood_glucose',
    134,
    NULL,
    'mg/dL',
    'fasting',
    '2026-11-10 07:05:00+05:30',
    'glucometer',
    'synthetic-ravi-glucometer',
    'valid',
    'synthetic'
  ),
  (
    'a52a0000-0000-4000-8000-000000000103',
    'a52a0000-0000-4000-8000-000000000052',
    'blood_glucose',
    141,
    NULL,
    'mg/dL',
    'fasting',
    '2026-11-12 07:15:00+05:30',
    'glucometer',
    'synthetic-ravi-glucometer',
    'valid',
    'synthetic'
  ),
  (
    'a52a0000-0000-4000-8000-000000000104',
    'a52a0000-0000-4000-8000-000000000052',
    'blood_glucose',
    136,
    NULL,
    'mg/dL',
    'fasting',
    '2026-11-13 07:08:00+05:30',
    'glucometer',
    'synthetic-ravi-glucometer',
    'valid',
    'synthetic'
  ),
  (
    'a52a0000-0000-4000-8000-000000000105',
    'a52a0000-0000-4000-8000-000000000052',
    'blood_glucose',
    122,
    NULL,
    'mg/dL',
    'fasting',
    '2026-11-15 07:20:00+05:30',
    'glucometer',
    'synthetic-ravi-glucometer',
    'valid',
    'synthetic'
  ),
  (
    'a52a0000-0000-4000-8000-000000000201',
    'a52a0000-0000-4000-8000-000000000052',
    'systolic_blood_pressure',
    136,
    86,
    'mmHg',
    'resting',
    '2026-11-08 08:00:00+05:30',
    'home_monitor',
    'synthetic-ravi-home-monitor',
    'valid',
    'synthetic'
  ),
  (
    'a52a0000-0000-4000-8000-000000000202',
    'a52a0000-0000-4000-8000-000000000052',
    'diastolic_blood_pressure',
    86,
    NULL,
    'mmHg',
    'resting',
    '2026-11-08 08:00:00+05:30',
    'home_monitor',
    'synthetic-ravi-home-monitor',
    'valid',
    'synthetic'
  ),
  (
    'a52a0000-0000-4000-8000-000000000203',
    'a52a0000-0000-4000-8000-000000000052',
    'systolic_blood_pressure',
    142,
    88,
    'mmHg',
    'resting',
    '2026-11-10 08:15:00+05:30',
    'home_monitor',
    'synthetic-ravi-home-monitor',
    'valid',
    'synthetic'
  ),
  (
    'a52a0000-0000-4000-8000-000000000204',
    'a52a0000-0000-4000-8000-000000000052',
    'diastolic_blood_pressure',
    88,
    NULL,
    'mmHg',
    'resting',
    '2026-11-10 08:15:00+05:30',
    'home_monitor',
    'synthetic-ravi-home-monitor',
    'valid',
    'synthetic'
  ),
  (
    'a52a0000-0000-4000-8000-000000000205',
    'a52a0000-0000-4000-8000-000000000052',
    'systolic_blood_pressure',
    130,
    82,
    'mmHg',
    'resting',
    '2026-11-13 09:00:00+05:30',
    'clinic',
    NULL,
    'valid',
    'synthetic'
  ),
  (
    'a52a0000-0000-4000-8000-000000000206',
    'a52a0000-0000-4000-8000-000000000052',
    'diastolic_blood_pressure',
    82,
    NULL,
    'mmHg',
    'resting',
    '2026-11-13 09:00:00+05:30',
    'clinic',
    NULL,
    'valid',
    'synthetic'
  )
ON CONFLICT (id) DO NOTHING;

INSERT INTO consultations (
  id,
  patient_id,
  clinician,
  appointment_date,
  consultation_type,
  status
)
VALUES (
  'a52a0000-0000-4000-8000-0000000000c1',
  'a52a0000-0000-4000-8000-000000000052',
  'Dr. Mehta',
  '2026-11-24 11:00:00+05:30',
  'consultation',
  'scheduled'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO care_plans (
  id,
  patient_id,
  condition,
  monitoring_schedule,
  clinician,
  approved_rules,
  escalation_protocol
)
VALUES (
  'a52a0000-0000-4000-8000-0000000000b1',
  'a52a0000-0000-4000-8000-000000000052',
  'type_2_diabetes',
  '{
    "blood_glucose": {
      "window_start": "2026-11-09",
      "window_end": "2026-11-15",
      "expected": "daily"
    }
  }'::jsonb,
  'Dr. Mehta',
  '[]'::jsonb,
  '{
    "clinic": "CityCare Clinic",
    "doctor": "Dr. Mehta",
    "voice_calls": "allowed_only_after_consent",
    "onboarding_rule": "not_onboarded_until_call_records_consent",
    "outbound_contact_policy": "The stored contact +15555501052 is synthetic and is not a real person. Outbound tests must use the operator-entered participant number, never this stored contact."
  }'::jsonb
)
ON CONFLICT (id) DO NOTHING;

-- Scenario records. Resettable by POST /api/v1/demo/ravi/reset.
INSERT INTO care_events (
  id,
  patient_id,
  event_type,
  event_description,
  priority,
  status
)
VALUES
  (
    'a52a0000-0000-4000-8000-00000000e001',
    'a52a0000-0000-4000-8000-000000000052',
    'onboarding',
    'Voice calls are allowed only after consent. Onboarding stays not onboarded until a call records consent.',
    'low',
    'open'
  ),
  (
    'a52a0000-0000-4000-8000-00000000e002',
    'a52a0000-0000-4000-8000-000000000052',
    'medication_followup',
    'Evening metformin 500 mg at 20:00 is scheduled and unconfirmed. Do not mark the dose missed until a call result says so.',
    'low',
    'open'
  ),
  (
    'a52a0000-0000-4000-8000-00000000e003',
    'a52a0000-0000-4000-8000-000000000052',
    'weekly_checkin',
    'Two glucose days have no reading: 2026-11-11 and 2026-11-14.',
    'low',
    'open'
  )
ON CONFLICT (id) DO NOTHING;

-- +919372501954 resolves to Ravi. Meera's chart contact stays +919840011223.
-- +14235838428 is the CareLoop line and is not linked. Skipped when 0003
-- has not created patient_phone_links yet.
DO $$
BEGIN
  IF to_regclass('public.patient_phone_links') IS NULL THEN
    RETURN;
  END IF;
  INSERT INTO patient_phone_links (
    id,
    patient_id,
    phone_e164,
    label
  )
  VALUES (
    'a52a0000-0000-4000-8000-0000000000f1',
    'a52a0000-0000-4000-8000-000000000052',
    '+919372501954',
    'mobile'
  )
  ON CONFLICT (phone_e164) DO UPDATE
  SET
    patient_id = EXCLUDED.patient_id,
    label = EXCLUDED.label;
END $$;
