# Call extractions

Agent `8ad7201e-2fe5-4595-8a45-35ed60fb1fcd`. No phone call was placed. Categories were created on 2026-11-15. A later change the same day added a Call purpose category and made Onboarding, Medication adherence, and Weekly check-in follow-ups of its `call_purpose` disposition.

Call outcomes `0090ff6d-242b-46d6-bef8-3d85ff2e6064` still runs on every transcript. It has its own `call_purpose` (`ab482f7c-972c-47e2-b8bc-4d13ddb2365f`) with values Medication_Check, Glucose_Check, Blood_Pressure_Check, Appointment_Reminder, Patient_Concern, and Not_Discussed. That disposition does not gate the three follow-up categories.

## Categories

| Category | Id | Model | When it runs |
| --- | --- | --- | --- |
| Call purpose | `439b7802-db98-425f-807c-faed53346df8` | gpt-4.1-mini | starting category, every call |
| Onboarding | `e2d0ff10-31ff-43ae-a148-c95b1f8f9ac9` | gpt-4.1-mini | follow-up: `call_purpose` in `Onboarding` |
| Medication adherence | `c3ec6503-a11f-4cdb-94d1-792bfcb764c5` | gpt-4.1-mini | follow-up: `call_purpose` in `Medication` |
| Weekly check-in | `3fa10cc1-27d1-4773-a94e-e9760c994947` | gpt-4.1-mini | follow-up: `call_purpose` in `Weekly` |

The parent is Call purpose `call_purpose` `9f6e27d1-c83f-402b-8a1f-c6eda1d7eb01`. Each follow-up uses `parent_disposition_id` `9f6e27d1-c83f-402b-8a1f-c6eda1d7eb01`, `match_mode` `in`, and one `match_values` entry: `Onboarding`, `Medication`, or `Weekly`. `min_duration_s` is null and `skip_voicemail` is false. The API accepted these rules.

Parent values are `Onboarding`, `Medication`, `Weekly`, and `Not_Discussed`. A follow-up whose parent answer is something else returns `status` `skipped` and `status_reason` `parent_mismatch`. The answer fields stay empty.

Each disposition question in the three follow-up categories now says: if this topic was not discussed, choose Not_Discussed.

## Dispositions

| Category | Name | Id | Kind | Values |
| --- | --- | --- | --- | --- |
| Call purpose | `call_purpose` | `9f6e27d1-c83f-402b-8a1f-c6eda1d7eb01` | objective | Onboarding, Medication, Weekly, Not_Discussed |
| Onboarding | `consented` | `72d12761-4fd7-402a-a423-690d860bbc82` | objective | Yes, No, Not_Discussed |
| Onboarding | `preferred_language` | `26901873-2021-4025-96ac-57a8ca4bacab` | objective | English, Hindi, Kannada, Not_Discussed |
| Medication adherence | `medication_status` | `a01217d9-19de-4521-b328-9f6dc14ba5d5` | objective | Taken, Missed, Uncertain, Not_Discussed |
| Medication adherence | `missed_reason` | `f7b5743e-f615-4c36-8d54-38165416cb76` | subjective text | Not_Discussed when no reason was given |
| Weekly check-in | `readings_missed` | `934616cd-b967-4d7c-b095-ef0dd4b6b748` | objective | Yes, No, Not_Discussed |
| Weekly check-in | `concern` | `fd515ba0-a702-4077-a199-92738b998105` | subjective text | Not_Discussed when no separate concern was raised |
| Weekly check-in | `follow_up` | `7569d35e-ce1c-4d3f-b3b6-cfd70595a003` | objective | Yes, No, Not_Discussed |

## Onboarding transcript

This table is the run from before the follow-up gate. It was not repeated after the gate.

```
Agent: Hello, this is CareLoop. I am calling to introduce the check-in calls. Do you agree to these calls?
Patient: Yes, I agree to the check-in calls.
Agent: Which language should we use for the calls?
Patient: Please use Hindi.
Agent: Thank you. Goodbye.
```

Expected for this type: `consented` Yes, `preferred_language` Hindi. Other new questions: Not_Discussed.

| Question | Returned | Expected |
| --- | --- | --- |
| Onboarding `consented` | Yes | Yes |
| Onboarding `preferred_language` | Hindi | Hindi |
| Medication adherence `medication_status` | Not_Discussed | Not_Discussed |
| Medication adherence `missed_reason` | Not_Discussed | Not_Discussed |
| Weekly check-in `readings_missed` | Not_Discussed | Not_Discussed |
| Weekly check-in `concern` | Not_Discussed | Not_Discussed |
| Weekly check-in `follow_up` | Not_Discussed | Not_Discussed |
| Call outcomes `call_purpose` | Not_Discussed | |
| Call outcomes `medication_adherence` | Not_Discussed | |
| Call outcomes `missed_reason` | Not_Discussed | |
| Call outcomes `glucose_context` | Not_Discussed | |
| Call outcomes `escalation_status` | Not_Discussed | |

The onboarding buckets matched on that earlier run.

## Medication transcript

Retested after the follow-up gate. Same transcript as the run that filled Weekly check-in `concern`.

```
Agent: Hello, this is CareLoop checking your evening medicine. Did you take it?
Patient: No, I missed it. I forgot because I was out.
Agent: Thank you for telling me. Goodbye.
```

Expected for this type: Call purpose `call_purpose` Medication, `medication_status` Missed, `missed_reason` in the patient's words about forgetting because they were out. Onboarding and Weekly check-in skipped.

| Question | Returned | Expected |
| --- | --- | --- |
| Call purpose `call_purpose` | Medication | Medication |
| Onboarding `consented` | skipped, `parent_mismatch` | skipped |
| Onboarding `preferred_language` | skipped, `parent_mismatch` | skipped |
| Medication adherence `medication_status` | Missed | Missed |
| Medication adherence `missed_reason` | The patient missed the evening medicine dose because they forgot to take it while they were out. | patient's words about forgetting because they were out |
| Weekly check-in `readings_missed` | skipped, `parent_mismatch` | skipped |
| Weekly check-in `concern` | skipped, `parent_mismatch` | skipped |
| Weekly check-in `follow_up` | skipped, `parent_mismatch` | skipped |
| Call outcomes `call_purpose` | Medication_Check | |
| Call outcomes `medication_adherence` | Missed | |
| Call outcomes `missed_reason` | I forgot because I was out. | |
| Call outcomes `glucose_context` | Not_Discussed | |
| Call outcomes `escalation_status` | Not_Discussed | |

The earlier run had returned Weekly check-in `concern` as "Missed evening medicine dose due to being out and forgetting". The retest skipped that question. The medication buckets still matched.

## Weekly check-in transcript

Retested after the follow-up gate. Same transcript as the run that marked Medication adherence `medication_status` Missed.

```
Agent: Hello, this is your weekly check-in. Did you take your glucose and blood pressure readings?
Patient: I missed the glucose readings on two days. My blood pressure I did take.
Agent: Is there anything else worrying you?
Patient: I have been getting dizzy in the afternoon.
Agent: Would you like the clinic to follow up with Dr. Mehta?
Patient: Yes, please ask the clinic to follow up.
Agent: I will pass that on. Goodbye.
```

Expected for this type: Call purpose `call_purpose` Weekly, `readings_missed` Yes, `concern` about afternoon dizziness, `follow_up` Yes. Onboarding and Medication adherence skipped.

| Question | Returned | Expected |
| --- | --- | --- |
| Call purpose `call_purpose` | Weekly | Weekly |
| Onboarding `consented` | skipped, `parent_mismatch` | skipped |
| Onboarding `preferred_language` | skipped, `parent_mismatch` | skipped |
| Medication adherence `medication_status` | skipped, `parent_mismatch` | skipped |
| Medication adherence `missed_reason` | skipped, `parent_mismatch` | skipped |
| Weekly check-in `readings_missed` | Yes | Yes |
| Weekly check-in `concern` | Dizziness in the afternoon | afternoon dizziness |
| Weekly check-in `follow_up` | Yes | Yes |
| Call outcomes `call_purpose` | Patient_Concern | |
| Call outcomes `medication_adherence` | Not_Discussed | |
| Call outcomes `missed_reason` | Not_Discussed | |
| Call outcomes `glucose_context` | Not_Discussed | |
| Call outcomes `escalation_status` | Not_Escalated | |

The earlier run had returned Medication adherence `medication_status` Missed and `missed_reason` "Missed the glucose readings on two days". No medicine dose was discussed. The retest skipped both questions. The weekly buckets still matched.
