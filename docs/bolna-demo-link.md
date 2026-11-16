# Bolna demo link

## Verified opening

No call was placed for this change.

Confirmed with `get_graph_agent` and `get_agent` on CareLoop AI Health Companion, `8ad7201e-2fe5-4595-8a45-35ed60fb1fcd`. `validation.valid` is true. `api_tools` still has the same nine tools. `webhook_url` is still set.

Welcome message, which Bolna substitutes from `user_data`:

```
Hello {patient_name}, this is the CareLoop AI assistant calling on behalf of {clinic_name}. {call_reason}
```

That welcome does not contain "What can I help you with".

Start node prompt:

```
This is an outbound call. You already know the purpose from {call_type}, {call_reason}, and {call_objective}. Introduce that purpose immediately. Never ask "what can I help you with today" on an outbound call. Ask one question at a time. Do not ask for facts already in context. Do not diagnose or change doses. If they ask what to do about a missed dose, tell them to follow the instructions they were given or talk to their clinician.

Opening line, using the call variables and not a fixed patient: Hello {patient_name}, this is the CareLoop AI assistant calling on behalf of {clinic_name}. {call_reason}

Branch on {call_type}. If it is onboarding, explain the service, ask if it is a good time, ask preferred language, and record consent. If they decline, record that and stop. If it is medication_adherence, ask about the specific {medication_name} at {scheduled_time}, which is {event_status}. Yes means patient-reported taken. No means ask why, then record missed and the reason. Unsure means record uncertain, not taken and not missed. If it is weekly_checkin, ask how the week has been, refer to missing readings already in context, and record a patient-reported reason. Do not interpret the numbers. For any other outbound {call_type}, introduce {call_reason} and {call_objective} and ask one question that serves that purpose.

If they report chest pain, fainting, severe dizziness, trouble breathing, confusion, or a very low sugar, call @post_clinical_escalation in this call and move to escalation. When the purpose is finished and there is no urgent symptom, move to close.
```

`{call_type}` routes before that prompt speaks: `onboarding`, `medication_adherence`, and `weekly_checkin` go to those nodes. `inbound`, a missing `call_type`, or an empty `call_type` goes to `inbound`, which may ask what they need and does not reveal chart details until `{patient_id}` is present. No patient name is hardcoded.

## Answered outbound call

Execution `509df70d-9023-4a98-897a-84354189866b` completed. It was an outbound call from `+14235838428` to `+919372501954` for agent `8ad7201e-2fe5-4595-8a45-35ed60fb1fcd`. `conversation_duration` was 122 seconds. `termination_reason` was `unknown`. The person spoke. The transcript includes the user line `hello hello`. The companion stayed in English. `user_data.preferred_language` was `en`.

The chart fetch failed. `get_execution` had no `tool_call_logs`. The debug function-call log shows two `get_context` requests, both with `purpose` `onboarding` and patient id `a52a0000-0000-4000-8000-000000000052` (Ravi Sharma). Both responses were HTTP 400: `purpose must be one of: glucose_check, bp_check, medication_check, appointment_reminder, general`. The tunnel `https://echo-criterion-revolutionary-months.trycloudflare.com` was up. That URL returned 400, not a connection failure, 404, or auth error. Webhooks to the same host returned 200. The call context used Ravi's id. `+919372501954` belongs to Meera Iyer (`11111111-1111-4111-8111-111111111111`) when that number is in `patient_phone_links`, so a call to that number should load her chart.

No second call was placed. After the fix, `GET` of that public context URL with `purpose=onboarding` returns 200. The same URL with `to_number=+919372501954` returns Meera Iyer, `11111111-1111-4111-8111-111111111111`. That check was an HTTP GET.

## Earlier link check

No outbound call was placed in the checks below.

## Recheck for the companion inbound line

`get_graph_agent` still returns CareLoop AI Health Companion, `8ad7201e-2fe5-4595-8a45-35ed60fb1fcd`, with `api_tools` null. `get_agent` shows `webhook_url` null and `inbound_phone_number` `8820ada7-a2c5-44c5-b658-ea3109b6b702`, so `setup_inbound_agent` was not called again. `list_phone_numbers` failed with the same grouped-object error and did not return the `bolna` array, so this recheck did not read `+14235838428` again. `cloudflared` and `ngrok` are not installed. No public URL was set on the agent. No outbound call was placed.

## Numbers on the account

`list_phone_numbers` did not return the inventory. The MCP error was:

`Failed to reach the Bolna API: GET /phone-numbers/all returned object with keys [bolna, user] instead of a list. This is an upstream response-shape change; the tool expected a JSON array.`

The same account endpoint returns an object with keys `bolna` and `user`. `user` is empty. `bolna` has one rented number, and that is the number linked below. No number was purchased in this step.

| id | E.164 | provider | rented |
| --- | --- | --- | --- |
| `8820ada7-a2c5-44c5-b658-ea3109b6b702` | `+14235838428` | twilio | true |

## Agent

Confirmed with `get_graph_agent`.

- Name: CareLoop AI Health Companion
- Agent id: `8ad7201e-2fe5-4595-8a45-35ed60fb1fcd`
- Language: `en`
- Start node: `start` (LLM). A router was rejected unless it had an unconditional catch-all, and a start router runs before the caller has spoken, so the requested intent edges would not run. Purpose still routes with expression edges on `recipient_data.purpose` (`medication_check`, `glucose_check`, `bp_check`, `appointment_reminder`).
- Nodes: `start`, `medication`, `glucose`, `blood_pressure`, `consultation`, `concern`, `escalation`, `close`
- `api_tools`: omitted. A `http://127.0.0.1:5000/api/v1/...` URL would be stored as the tool endpoint even though Bolna cannot reach that local address. Node prompts tell the model that no chart lookup tool is attached and not to invent chart data.
- No `webhook_url`, synthesizer, or transcriber override was set.
- Validation warning only: four mutually exclusive purpose edges on `start` share priority 0 (`duplicate_transition_priorities`). `validation.valid` is true.

## Inbound link

Succeeded. `setup_inbound_agent` linked agent `8ad7201e-2fe5-4595-8a45-35ed60fb1fcd` to phone number id `8820ada7-a2c5-44c5-b658-ea3109b6b702` (`+14235838428`).

Returned inbound URL: `https://api.bolna.ai/inbound_call?agent_id=8ad7201e-2fe5-4595-8a45-35ed60fb1fcd&user_id=369723ee-d164-4f88-a71c-da32a848d888`

No other purchased numbers were on the account.

## Disposition tests

Category `Call outcomes` (`0090ff6d-242b-46d6-bef8-3d85ff2e6064`), model `gpt-4.1-mini`.

`test_dispositions` ran three synthetic transcripts. These were not phone calls.

| Transcript | call_purpose | medication_adherence | missed_reason | glucose_context | escalation_status |
| --- | --- | --- | --- | --- | --- |
| Missed metformin because they were away from home | Medication_Check | Missed | I was away from home | Not_Discussed | Not_Discussed |
| Fasting glucose of 142 mg/dL from a glucometer | Glucose_Check | Not_Discussed | Not_Discussed | Fasting | Not_Discussed |
| Chest discomfort, agent told them to contact emergency services | Patient_Concern | Not_Discussed | Not_Discussed | Not_Discussed | Escalated |

Every question in those three runs returned `status: completed`.

No outbound call was placed.

## Outbound check-in attempt

One `start_outbound_call` was sent to `+919372501954` from `+14235838428` for agent `8ad7201e-2fe5-4595-8a45-35ed60fb1fcd`, with `user_data` `patient_id` `11111111-1111-4111-8111-111111111111`, `preferred_language` `en`, `purpose` `medication_check`, and `clinic` `CityCare Clinic`.

Bolna refused the call before an execution id existed. Exact error:

`Bolna API error (HTTP 400): Trial accounts can only make calls to verified phone numbers.`

No execution id, status, termination reason, or conversation duration was returned. The call was not retried. No conversation was verified, and no chart webhook was observed from this attempt.
