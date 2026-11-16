-- Synthetic demo, not a real person, not medical advice.

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
  '11111111-1111-4111-8111-111111111111',
  'Meera Iyer',
  '1978-04-12',
  'en',
  '+919840011223',
  'Lives in Pune. Synthetic chart for clinic follow-up.',
  '["Penicillin"]'::jsonb,
  '{
    "name": "Arjun Iyer",
    "relationship": "spouse",
    "contact_number": "+919840044556"
  }'::jsonb
)
ON CONFLICT (id) DO NOTHING;

-- preferred_language is a single tag. Re-applying this seed sets it to en.
-- hi and kn are not stored on the patient: the column holds one code.
-- Tests may PATCH preferred_language to hi or kn. The web language list
-- also offers those codes. The voice_calls row below keeps language hi as
-- fixture text. It is not a Bolna execution.
UPDATE patients
SET preferred_language = 'en'
WHERE id = '11111111-1111-4111-8111-111111111111';

INSERT INTO conditions (
  id,
  patient_id,
  condition_type,
  diagnosis_date,
  treating_clinician
)
VALUES
  (
    '55555555-5555-4555-8555-555555555555',
    '11111111-1111-4111-8111-111111111111',
    'type_2_diabetes',
    '2019-06-01',
    'Dr. Anika Shah'
  ),
  (
    '66666666-6666-4666-8666-666666666666',
    '11111111-1111-4111-8111-111111111111',
    'hypertension',
    '2021-02-14',
    'Dr. Anika Shah'
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
VALUES
  (
    '22222222-2222-4222-8222-222222222222',
    '11111111-1111-4111-8111-111111111111',
    'Metformin',
    '500 mg',
    'twice daily',
    '{"times":["08:00","20:00"]}'::jsonb,
    '2019-06-15',
    'Dr. Anika Shah',
    true
  ),
  (
    '33333333-3333-4333-8333-333333333333',
    '11111111-1111-4111-8111-111111111111',
    'Telmisartan',
    '40 mg',
    'once daily',
    '{"times":["08:00"]}'::jsonb,
    '2021-02-20',
    'Dr. Anika Shah',
    true
  )
ON CONFLICT (id) DO NOTHING;

-- measured_at values use a +00 offset. 02:00+00 is 07:30 in Asia/Kolkata.
INSERT INTO health_readings (
  id,
  patient_id,
  measurement_type,
  value,
  unit,
  measurement_context,
  measured_at,
  source,
  device_id,
  data_quality
)
VALUES
  (
    'a1111111-1111-4111-8111-111111111101',
    '11111111-1111-4111-8111-111111111111',
    'blood_glucose',
    126,
    'mg/dL',
    'fasting',
    '2026-11-10 02:00:00+00',
    'glucometer',
    'synthetic-glucometer-01',
    'valid'
  ),
  (
    'a1111111-1111-4111-8111-111111111102',
    '11111111-1111-4111-8111-111111111111',
    'blood_glucose',
    119,
    'mg/dL',
    'fasting',
    '2026-11-12 02:10:00+00',
    'glucometer',
    'synthetic-glucometer-01',
    'valid'
  ),
  (
    'a1111111-1111-4111-8111-111111111103',
    '11111111-1111-4111-8111-111111111111',
    'blood_glucose',
    158,
    'mg/dL',
    'post_meal',
    '2026-11-13 08:45:00+00',
    'glucometer',
    'synthetic-glucometer-01',
    'valid'
  ),
  (
    'a1111111-1111-4111-8111-111111111104',
    '11111111-1111-4111-8111-111111111111',
    'blood_glucose',
    131,
    'mg/dL',
    'fasting',
    '2026-11-15 02:05:00+00',
    'glucometer',
    'synthetic-glucometer-01',
    'valid'
  ),
  (
    'a1111111-1111-4111-8111-111111111105',
    '11111111-1111-4111-8111-111111111111',
    'systolic_blood_pressure',
    134,
    'mmHg',
    'resting',
    '2026-11-11 02:20:00+00',
    'home_monitor',
    'synthetic-home-monitor-01',
    'valid'
  ),
  (
    'a1111111-1111-4111-8111-111111111106',
    '11111111-1111-4111-8111-111111111111',
    'diastolic_blood_pressure',
    82,
    'mmHg',
    'resting',
    '2026-11-11 02:20:00+00',
    'home_monitor',
    'synthetic-home-monitor-01',
    'valid'
  ),
  (
    'a1111111-1111-4111-8111-111111111107',
    '11111111-1111-4111-8111-111111111111',
    'systolic_blood_pressure',
    128,
    'mmHg',
    'resting',
    '2026-11-15 02:30:00+00',
    'home_monitor',
    'synthetic-home-monitor-01',
    'valid'
  ),
  (
    'a1111111-1111-4111-8111-111111111108',
    '11111111-1111-4111-8111-111111111111',
    'diastolic_blood_pressure',
    80,
    'mmHg',
    'resting',
    '2026-11-15 02:30:00+00',
    'home_monitor',
    'synthetic-home-monitor-01',
    'valid'
  ),
  (
    'a1111111-1111-4111-8111-111111111109',
    '11111111-1111-4111-8111-111111111111',
    'weight',
    68.4,
    'kg',
    NULL,
    '2026-11-09 03:00:00+00',
    'home_monitor',
    'synthetic-scale-01',
    'valid'
  )
ON CONFLICT (id) DO NOTHING;

-- Older chart rows. source cgm here is a label on synthetic data, not a paired transmitter.
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
  data_quality
)
VALUES
  (
    'a1111111-1111-4111-8111-111111111110',
    '11111111-1111-4111-8111-111111111111',
    'blood_glucose',
    118,
    NULL,
    'mg/dL',
    'fasting',
    '2026-11-08 01:35:00+00',
    'manual',
    NULL,
    'valid'
  ),
  (
    'a1111111-1111-4111-8111-111111111111',
    '11111111-1111-4111-8111-111111111111',
    'blood_glucose',
    164,
    NULL,
    'mg/dL',
    'post_meal',
    '2026-11-12 08:10:00+00',
    'cgm',
    NULL,
    'valid'
  ),
  (
    'a1111111-1111-4111-8111-111111111112',
    '11111111-1111-4111-8111-111111111111',
    'systolic_blood_pressure',
    132,
    84,
    'mmHg',
    'resting',
    '2026-11-08 02:35:00+00',
    'home_monitor',
    'synthetic-home-monitor-01',
    'valid'
  ),
  (
    'a1111111-1111-4111-8111-111111111113',
    '11111111-1111-4111-8111-111111111111',
    'diastolic_blood_pressure',
    84,
    NULL,
    'mmHg',
    'resting',
    '2026-11-08 02:35:00+00',
    'home_monitor',
    'synthetic-home-monitor-01',
    'valid'
  )
ON CONFLICT (id) DO NOTHING;

INSERT INTO adherence_logs (
  id,
  patient_id,
  medication_id,
  schedule_time,
  reported_status,
  reported_reason,
  recorded_at,
  source
)
VALUES
  (
    'd1111111-1111-4111-8111-111111111101',
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    '2026-11-13 02:30:00+00',
    'taken',
    NULL,
    '2026-11-13 02:36:00+00',
    'app'
  ),
  (
    'd1111111-1111-4111-8111-111111111102',
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    '2026-11-13 14:30:00+00',
    'missed',
    'Evening dose was not logged',
    '2026-11-13 15:00:00+00',
    'app'
  ),
  (
    'd1111111-1111-4111-8111-111111111103',
    '11111111-1111-4111-8111-111111111111',
    '33333333-3333-4333-8333-333333333333',
    '2026-11-14 02:30:00+00',
    'taken',
    NULL,
    '2026-11-14 02:41:00+00',
    'call_self_report'
  ),
  (
    'd1111111-1111-4111-8111-111111111104',
    '11111111-1111-4111-8111-111111111111',
    '33333333-3333-4333-8333-333333333333',
    '2026-11-15 02:30:00+00',
    'missed',
    'Morning dose was not logged',
    '2026-11-15 03:05:00+00',
    'app'
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
  '44444444-4444-4444-8444-444444444444',
  '11111111-1111-4111-8111-111111111111',
  'Dr. Anika Shah',
  '2026-11-20 09:30:00+05:30',
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
  '77777777-7777-4777-8777-777777777777',
  '11111111-1111-4111-8111-111111111111',
  'type_2_diabetes',
  '{
    "morning_fasting_glucose": {
      "measurement_type": "blood_glucose",
      "measurement_context": "fasting",
      "time_of_day": "morning"
    }
  }'::jsonb,
  'Dr. Anika Shah',
  '[]'::jsonb,
  '{
    "action": "record_and_notify_clinician",
    "must_not": ["diagnose", "prescribe", "change_dose"]
  }'::jsonb
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO care_events (
  id,
  patient_id,
  event_type,
  event_description,
  priority,
  status
)
VALUES (
  '88888888-8888-4888-8888-888888888888',
  '11111111-1111-4111-8111-111111111111',
  'missing_fasting_glucose',
  'Fasting glucose was not recorded on 2026-11-14.',
  'low',
  'open'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO voice_calls (
  id,
  patient_id,
  bolna_call_id,
  call_type,
  language,
  call_status,
  summary,
  extracted_data
)
VALUES (
  '99999999-9999-4999-8999-999999999999',
  '11111111-1111-4111-8111-111111111111',
  'demo-call-001',
  'outbound',
  'hi',
  'completed',
  'Outbound Hindi demo call completed. The line connected and the call then ended.',
  '{}'::jsonb
)
ON CONFLICT (bolna_call_id) DO NOTHING;

INSERT INTO documents (
  id,
  patient_id,
  document_type,
  file_location,
  extraction_status
)
VALUES
  (
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    '11111111-1111-4111-8111-111111111111',
    'prescription',
    'synthetic://prescriptions/meera-metformin.txt',
    'not_requested'
  ),
  (
    'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
    '11111111-1111-4111-8111-111111111111',
    'lab_report',
    'synthetic://lab-reports/meera-panel.txt',
    'not_requested'
  )
ON CONFLICT (id) DO NOTHING;

-- Chart contact_number stays +919840011223. +919372501954 is not Meera's
-- phone link. supabase/seed/0002_ravi.sql attaches that number to Ravi Sharma.
-- +14235838428 is the CareLoop line and is not inserted here.
