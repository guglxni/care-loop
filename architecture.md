# Care Loop architecture

Status: the patient app, Flask API, Postgres schema, intelligence package, ingest connectors, and Bolna integration now live in this repository. This file is the design record from 15 November 2026. Where this document and the code disagree, the code and its tests are the source of truth.

Care Loop is a multilingual chronic care platform. The first conditions are type 2 diabetes and hypertension. Three systems share one database:

1. The patient application records the chart: profile, history, diagnoses, medicines, glucose, blood pressure, visits, labs, and language.
2. The health intelligence engine reads that chart and produces care plans, adherence, trends, missed measurements, reminders, care gaps, and clinician escalations.
3. Bolna runs the voice channel. It does not own the chart.

Inspected sources for the voice design:

- Connected MCP server `user-bolna`, status `ready`, inspected 15 November 2026.
- Live tool schemas from that server. Parameter names below are copied from those schemas.
- Bolna documentation pages fetched through `get_doc` and `search_docs` on that server.
- `list_workflow_node_types`, called live, for workflow node parameters.

Nothing in this document invents a Bolna endpoint. Where a response field was not returned by a tool in this session, the implementation step is to read the live response before wiring it.

## Repository

| Item | Value |
| --- | --- |
| Path | repository root |
| Git | `main` |
| Application | `web/` patient app, `backend/` Flask API, `intelligence/`, `supabase/` |

The requested stack is React and TypeScript, Tailwind CSS, shadcn/ui, a Python Flask API, PostgreSQL through Supabase, Recharts, and Bolna. The frontend toolchain in the plan is Vite. The brief also says “White”; no package or repository by that name was on disk, so this plan does not depend on one.

## Product boundaries

The database is the source of truth. Bolna receives a small, call-specific context packet and writes nothing clinical except by calling Care Loop.

Every glucose and blood pressure row stores:

- the measurement timestamp (`measured_at`), separate from the time the row was saved
- the unit (`mg/dL` or `mmol/L` for glucose, `mmHg` for pressure)
- the source: `manual`, `cgm`, `glucometer`, `home_monitor`, or `clinic`

A CGM sample, a fingerstick, and a typed number are different observations. Trends label the source and do not silently average them together.

Clinical thresholds live in versioned rows. A threshold affects care only after a clinician approves that version. Draft numbers may be seeded from published guidelines. They are not care rules until approved.

The voice agent collects, confirms, and records. Clinicians diagnose, prescribe, and change medicines. Care Loop exposes no tool whose effect is a diagnosis, a prescription, or a dose change.

Development data is synthetic. No real patient record enters this environment.

## System shape

```text
Patient app (React, Vite, TypeScript, Tailwind, shadcn, Recharts)
        │  reads and writes through Flask
        ▼
Flask API  ──►  Supabase Postgres (source of truth)
        │         Supabase Storage (prescriptions, lab reports)
        │
        │  context packet, function-tool responses, webhook inbox
        ▼
Bolna MCP / Bolna voice runtime
        │
        ├── graph agent (conversation)
        ├── dispositions (post-call extraction)
        ├── workflows (retry, wait, callback, WhatsApp)
        └── webhooks back to Flask
                │
                ▼
        Intelligence engine (inside Flask, over Postgres)
        care gaps, adherence, missed readings, escalations
                │
                ▼
        Clinician queue in the same application
```

Flask is the only component allowed to change clinical rows. The browser never holds the Supabase service role. Bolna never holds a database credential. Bolna holds a Care Loop tool token that can call a fixed set of HTTP tools.

A call is allowed to see:

- preferred language and the name the patient uses
- why this call is happening (missed glucose, missed blood pressure, medicine check, visit reminder)
- today’s due medicine names and scheduled times
- the latest glucose, if it is inside the freshness window, with value, unit, time, and source
- the latest blood pressure on the same rule
- the next visit
- the escalation instruction for this call

A call is not allowed to see the longitudinal chart, past notes, uploaded PDFs, or other patients.

## What Bolna does, and what Care Loop must build

| Capability | Native to Bolna | Care Loop backend |
| --- | --- | --- |
| Spoken conversation, turn-taking, barge-in | Yes. Graph nodes and the default voice pipeline. | Write the graph. Keep `agent_information` short. |
| Multilingual speech | Yes. `list_tts_providers` and `list_voices` take a BCP-47 language. `create_graph_agent.language` sets the transcriber language. Graph edges can read `detected_language`. | Store `preferred_language`. Select provider, model, and voice from the live lists at setup time. Do not hard-code a voice id in this document. |
| Outbound check-ins | `start_outbound_call` and workflows with an `agent` node. | Decide who to call, when, and which context packet to send. |
| Inbound calls | `setup_inbound_agent` binds an agent to a `phone_number_id`. Optional `ivr_config`. | Map `from_number` to a patient. Refuse the chart if the number is unknown or shared. |
| Dynamic patient context | `start_outbound_call.user_data` and workflow `agent.variables`. Prompt placeholders and `{variable}` substitution. | Assemble the packet from Postgres immediately before the call. |
| Retrieve and update patient facts during a call | Custom function tools. Bolna performs the HTTP call. The schema is documented, not a separate MCP tool. | Implement the endpoints. Validate units, ranges, identity, and the no-prescribe rule. |
| Post-call structured extraction | Dispositions and extraction categories. Results arrive on `extracted_data`. | Treat extraction as a proposal. Accept it only after schema checks. Clinician-approved thresholds decide urgency. |
| Call outcome sync | Agent `webhook_url` and workflow `settings.webhook`. | Idempotent inbox keyed by execution id. |
| Human escalation | Transfer tooling in the product docs, graph event edges, workflow `callback` nodes. | Clinician queue, acknowledgement, and the callback POST that resumes the workflow. |
| Knowledge the agent may quote | `create_knowledgebase` ingests a URL. Graph `rag_config` retrieves chunks per turn. | Publish stable education pages. Patient PDFs stay in Storage and are not pasted into prompts. |
| Medication schedule, readings, care plans, trends, care gaps | No. | All of this is Postgres plus Flask. |
| Diagnosis, prescribing, dose changes | Must not be given to the agent. | Not implemented as agent tools. |

`list_batches` describes itself as read-only and says batch creation is not available through the connector. `create_batch` and `schedule_batch` are present on the same server and have full schemas. The implementation uses those two tools. The `list_batches` sentence is stale relative to the live catalog.

## Bolna tool catalog

Every tool below was listed on the connected server. `api_key` is an optional override on the account tools: a sub-account key (`sa-...`) runs that one call as the sub-account. `mcp_auth` authenticates the MCP session itself.

### Agents and graph agents

| Tool | What it does |
| --- | --- |
| `list_agents` | Lists agents with id, name, status, and creation date. |
| `get_agent` | Full configuration of one agent: prompts, model, voice, tasks. |
| `create_agent` | Creates an agent from `agent_config` and `agent_prompts`. |
| `update_agent` | Partial update of name, welcome message, prompts, webhook, voice, or telephony provider. |
| `delete_agent` | Permanently deletes an agent and its batches and execution history. |
| `stop_agent_queued_calls` | Cancels every queued call for an agent. In-progress calls continue. |
| `list_agent_variables` | Lists `{placeholder}` variables in prompts without returning the full config. |
| `create_graph_agent` | Creates a node-based voice flow. Validates before save. |
| `get_graph_agent` | Returns the graph, routing settings, `api_tools`, and a validation report. |
| `update_graph_agent` | Replaces or patches a live graph. Validates before save. Voice and telephony are kept. |
| `validate_graph_agent` | Checks a graph against the editor rules and does not save. |
| `send_graph_agent_event` | Pushes a named event into a live call. Returns once queued, or 404 if the call has ended. |

### Calls, batches, executions

| Tool | What it does |
| --- | --- |
| `start_outbound_call` | Places a real outbound call. Returns an execution id. Spends balance. |
| `stop_call` | Cancels one call that is still `queued` or `scheduled`. |
| `list_agent_executions` | Call history for one agent. The API requires a window no wider than 7 days. Default is the last 7 days. |
| `get_execution` | One call: transcript, status, `termination_reason`, cost, telephony, `extracted_data`. |
| `get_execution_raw_logs` | Pipeline logs across telephony, transcriber, LLM, and synthesizer. |
| `get_execution_debug` | One compact debug payload: execution, per-turn latency, transcript, and logs. |
| `create_batch` | Creates an idle batch from recipients. |
| `schedule_batch` | Starts a batch at a future time. Spends balance. |
| `get_batch` | Batch status, schedule, and contact counts. |
| `list_batches` | Lists batches for one agent. |
| `list_batch_executions` | Executions inside one batch. |
| `stop_batch` | Halts a running or queued batch. |
| `delete_batch` | Permanently deletes a batch. |

### Voice, numbers, inbound

| Tool | What it does |
| --- | --- |
| `list_tts_providers` | TTS providers and models for one BCP-47 language. The live API requires `language`. |
| `list_voices` | Voices for one provider, model, and language. |
| `list_providers` | Third-party providers on the account. Secrets are masked. |
| `remove_provider` | Removes a provider by `provider_name`. |
| `list_phone_numbers` | Numbers on the account, including telephony provider. |
| `search_phone_numbers` | Numbers available to buy. |
| `buy_phone_number` | Purchases a number. Recurring charge. |
| `delete_phone_number` | Removes a number and stops billing. |
| `setup_inbound_agent` | Answers inbound calls on a number, optionally with an IVR. |
| `unlink_inbound_agent` | Removes inbound routing from a number. |

### Extraction

| Tool | What it does |
| --- | --- |
| `create_extraction_category` | Groups dispositions into one LLM pass, with an optional start rule or follow-up rule. |
| `list_extraction_categories` | Categories and the dispositions inside them. |
| `update_extraction_category` | Renames a category, changes its model, or changes when it runs. |
| `delete_extraction_category` | Deletes the category and every disposition in it. |
| `create_disposition` | One structured question evaluated against each transcript. |
| `bulk_create_dispositions` | Creates many dispositions in one request. All fail if any one is invalid. |
| `list_dispositions` | Lists dispositions, optionally for one agent. |
| `get_disposition` | One disposition, including `category_id`. |
| `update_disposition` | Partial update. A shared disposition forks a private copy when `agent_id` is set. |
| `delete_disposition` | Deletes future use. Past results remain. |
| `test_dispositions` | Runs an agent’s dispositions against a transcript. No phone call. |

### Workflows

| Tool | What it does |
| --- | --- |
| `list_workflow_node_types` | Node types, parameters, namespaces, and effects. Called during this design. |
| `create_workflow` | Creates an empty unpublished workflow. |
| `list_workflows` | Lists workflows, optional name filter. |
| `get_workflow` | Status, masked webhook settings, and version history. |
| `duplicate_workflow` | Copies a version into a new unpublished workflow. |
| `rename_workflow` | Renames a workflow. |
| `get_workflow_draft` | Current draft and the revision the next save must send. |
| `save_workflow_draft` | Replaces the draft, then validates. Required: `workflow_id`, `expected_revision`, `definition`. |
| `patch_workflow_draft` | Small edits instead of resending the whole definition. |
| `rename_workflow_node` | Renames a draft node id and rewrites references. |
| `validate_workflow` | Errors block publish. Warnings do not. |
| `publish_workflow` | Freezes the draft as an immutable version. |
| `get_workflow_version` | One published node graph. |
| `update_workflow_settings` | Live webhook settings. Takes effect immediately, including for running executions. |
| `test_workflow_webhook` | Sends one sample `execution.terminal` POST. |
| `run_workflow` | Runs one contact through the latest published version. |
| `get_workflow_execution` | Current node, attempts, and the latest 100 timeline events. |
| `cancel_workflow_execution` | Terminates one running execution. |
| `resend_workflow_webhook` | Requeues the original terminal payload to the current URL. |
| `get_workflow_callback` | Callback URL and signing secret for one callback node. |
| `create_workflow_campaign` | Campaign pinned to a published version. Starts empty. |
| `upload_workflow_campaign_entries` | Adds contacts. Standard fields are `reference_id`, `mobile_number`, `name`, `email`. Other start-node fields go in `custom_fields`. |
| `list_workflow_campaigns` | Lists campaigns. |
| `get_workflow_campaign` | Status, totals, and validation errors. |
| `get_workflow_campaign_entries_template` | CSV header the pinned version expects. |
| `list_workflow_campaign_entries` | Uploaded contacts. |
| `list_workflow_campaign_executions` | Per-contact executions. |
| `get_workflow_campaign_report` | Counts by status, termination reason, and node. |
| `start_workflow_campaign` | Dispatches pending entries. Spends balance. |
| `pause_workflow_campaign` | Pauses dispatch. |
| `resume_workflow_campaign` | Resumes a paused campaign. |
| `abort_workflow_campaign` | Terminal. Cannot be resumed. |
| `delete_workflow_campaign` | Deletes an empty draft that has not started. |
| `delete_workflow` | Deletes the workflow and every version. |

### Knowledge bases, account, docs

| Tool | What it does |
| --- | --- |
| `create_knowledgebase` | Scrapes one URL. PDF upload is not supported on this tool. Processing is asynchronous. |
| `get_knowledgebase` | File name, status, and settings. |
| `list_knowledgebases` | Every knowledge base on the account. |
| `delete_knowledgebase` | Permanent delete. Agents lose that retrieval context. |
| `get_user_info` | Profile, wallet balance, concurrency limits. |
| `list_violations` | Content, regulatory, or fraud flags. |
| `search_docs` | Searches Bolna documentation. |
| `get_doc` | Fetches one documentation page as markdown. |

### SIP trunks and sub-accounts

Present on the server and out of scope for the first phases unless Care Loop brings its own carrier: `create_trunk`, `get_trunk`, `list_trunks`, `update_trunk`, `delete_trunk`, `add_trunk_gateway`, `remove_trunk_gateway`, `add_trunk_carrier_ip`, `remove_trunk_carrier_ip`, `add_number_to_trunk`, `remove_number_from_trunk`, `assign_trunk_number_agent`, `list_trunk_calls`, `get_trunk_connection_details`, `start_trunk_test_call`, `get_trunk_test_call`, `arm_trunk_inbound_test`, `get_trunk_inbound_test`, `disarm_trunk_inbound_test`.

Legacy trunk tools, marked deprecated on the server: `create_sip_trunk`, `get_sip_trunk`, `list_sip_trunks`, `update_sip_trunk`, `delete_sip_trunk`, `add_trunk_number`, `remove_trunk_number`, `list_trunk_numbers`.

Sub-accounts, enterprise admin only: `create_sub_account`, `list_sub_accounts`, `update_sub_account`, `delete_sub_account`, `get_sub_account_usage`, `get_all_sub_accounts_usage`.

## Parameters for the tools Care Loop will use

Optional `api_key` is omitted from each list. It is the sub-account override described above.

### Creating agents

`create_agent` requires `agent_config` and `agent_prompts`.

`agent_config` requires `agent_name` and `tasks` (at least one). Optional: `agent_welcome_message`, `webhook_url` (URI), `agent_type`, `calling_guardrails`, `ingest_source_config`.

Each task requires `task_type` (`conversation`, `extraction`, or `summarization`), `toolchain`, and `tools_config`. `toolchain` requires `execution` (`parallel` or `sequential`) and `pipelines` (array of string arrays). `tools_config` requires `llm_agent`, `synthesizer`, `transcriber`, `input`, and `output`. Their inner objects are open in the MCP schema. `task_config` is optional.

`agent_prompts` is a map. Each entry requires `system_prompt`.

`update_agent` requires `agent_id`. Optional `agent_config` fields include `agent_name`, `agent_welcome_message`, `webhook_url`, `synthesizer` (`provider` and `provider_config` are both required if `synthesizer` is sent), `ingest_source_config`, and `telephony_provider` (`twilio`, `plivo`, `exotel`, `vobiz`, `sip-trunk`, `trunk`, `default`). `agent_prompts` may be sent as the same map shape.

Care Loop’s conversational agent should be a graph agent, not a single static prompt stuffed with history. `create_agent` remains the tool for any non-graph task configuration the graph tools do not cover.

### Editing graph agents

`create_graph_agent` requires `agent_name` and `graph`.

`graph` requires `current_node_id` and `nodes` (at least one). Optional graph fields: `agent_information`, `routing_instructions`, `model` (default `gpt-4.1-mini`), `provider` (default `openai`), `max_tokens`, `temperature`, `routing_model`, `routing_max_tokens`, `routing_reasoning_effort` (`minimal`, `low`, `medium`, `high`), `variable_types`.

Each node requires `id`. Optional: `node_type` (`llm`, `static`, `router`), `prompt`, `static_message`, `description`, `repeat_after_silence_seconds`, `rag_config`, `edges`.

Each edge requires `to_node_id`. Optional: `condition`, `condition_type` (`llm`, `expression`, `unconditional`, `event`), `expression`, `event_name`, `parameters`, `priority`, `function_name`, `function_description`.

An `expression` requires `conditions`. Each condition requires `variable` and `operator` (`eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `contains`, `in`, `not_in`, `exists`, `not_exists`). `logic` is `and` or `or`. `value` is omitted for `exists` and `not_exists`.

Also optional on create: `agent_welcome_message`, `webhook_url`, `telephony_provider` (default `plivo`), `language` (default `en`), `transcriber`, `synthesizer`, `api_tools`, `task_config`.

The tool description states the defaults if `transcriber` and `synthesizer` are omitted: Deepgram nova-3, ElevenLabs turbo v2.5, Plivo. Those defaults are English-oriented. A Hindi or other-language patient needs an explicit language, transcriber, and synthesizer chosen from `list_tts_providers` and `list_voices`.

`update_graph_agent` requires `agent_id`. Send either `graph` or the edit fields `current_node_id`, `nodes`, `upsert_nodes`, `remove_node_ids`, and `settings`. `api_tools` replaces `tools_config.api_tools`. The tool keeps voice, transcriber, and telephony.

`validate_graph_agent` checks nodes, edges, and `current_node_id` without saving.

`send_graph_agent_event` requires `run_id` and `event`. `run_id` is the `execution_id` from `start_outbound_call`, or the inbound run id. Optional `properties` merge into `context_data`. `event` must match an edge `event_name`.

`get_graph_agent` is the read to perform before an update.

### Configuring voice

`list_tts_providers` requires `language`.

`list_voices` requires `provider_id`, `model_id`, and `language`. Optional `page` (default 1) and `page_size` (default 100, maximum 100).

`update_agent` can replace `synthesizer` with `provider` and `provider_config`. `create_graph_agent` can replace the whole `synthesizer` and `transcriber` objects. The MCP schema does not enumerate the keys inside those objects. The implementation reads a voice chosen from `list_voices`, then reads `get_agent` or the Bolna agent API documented at `https://www.bolna.ai/docs/api-reference/agent/v2/create` before freezing the provider config. This document does not invent voice-config keys.

### Making calls

`start_outbound_call` requires `agent_id` and `recipient_phone_number` (E.164). Optional `from_phone_number` (E.164) and `user_data` (object). This is the dynamic context channel for a single call.

`stop_call` cancels one not-yet-ringing execution. The schema was not re-fetched field by field in this session. The tool is present. Its description limits it to `queued` or `scheduled`.

`create_batch` requires `agent_id` and `recipients`. Each recipient requires `contact_number` (E.164). Any other recipient field must be a string and becomes a prompt variable. Optional `from_phone_numbers`, `webhook_url`, and `retry_config`. `retry_config`, when sent, requires `enabled`, `max_retries` (integer ≥ 1), and `retry_intervals_minutes` (integers ≥ 1).

`schedule_batch` requires `batch_id` and `scheduled_at` (date-time). The time must be at least 2 minutes ahead. Bolna rounds up to the next 10-minute mark. Optional `bypass_call_guardrails` defaults to false. Care Loop leaves that false.

`setup_inbound_agent` requires `agent_id` and `phone_number_id`. Optional `allow_multiple` (default false) and `ivr_config`. `ivr_config`, when sent, requires `enabled`. Optional IVR fields: `voice`, `welcome_message`, `timeout`, `max_retries`, `steps`, `default_agent_id`.

`run_workflow` requires `workflow_id` and `contact`. Contact may include `reference_id`, `mobile_number` (E.164), `name`, `email`, and `custom_fields`. Fields declared on the start node may also be flat on `contact`. Undeclared fields are rejected. Reusing `reference_id` returns the existing execution.

### Retrieving call details

`list_agent_executions` requires `agent_id`. Optional `from` and `to` (date-time), `page_number` (default 1), `page_size` (default 10, maximum 50). The window cannot exceed 7 days.

`get_execution` requires `execution_id`.

The execution object is also the agent webhook body. Documented fields Care Loop will store or branch on, from `https://www.bolna.ai/docs/post-call/execution-payload`:

- Identity: `id`, `agent_id`, `batch_id`, `campaign_id`
- Outcome: `status`, `termination_reason`, `conversation_duration`, `answered_by_voice_mail`, `error_message`
- Time: `created_at`, `initiated_at`, `updated_at`, `scheduled_at`
- Parties: `user_number`, `agent_number`, `provider`
- Content: `transcript` (`assistant:` and `user:` lines), `summary`, `extracted_data`
- Telephony: `telephony_data.call_type`, `recording_url`, `hangup_by`, `hangup_reason`, `from_number`, `to_number`
- Context actually used: `context_details.recipient_data`
- Money: `total_cost` and `cost_breakdown` are in cents. Reconcile with `cost_breakdown.total_cost_to_deduct`

`extracted_data` is nested as category, then extraction name, then an object with `subjective`, `objective`, `confidence`, `confidence_label`, `reasoning_subjective`, `reasoning_objective`, `validation`, `status`, and `status_reason`. `status` `skipped` means the question was not asked. An empty object means the agent has no dispositions, or that a category’s LLM call failed (`test_dispositions` uses `{}` for a failed category).

`get_execution_debug` and `get_execution_raw_logs` are for engineering review, not for the patient chart.

Three handler rules from that same payload page:

- Transcript, duration, cost, recording, and `extracted_data` are empty until the call is terminal.
- `status` `completed` does not mean the patient spoke. Branch on `termination_reason`, then `conversation_duration > 0`, then a `user:` line in `transcript`.
- The same `id` is delivered more than once. The inbox upserts on `id`.

Documented terminal statuses in the handler example on that page: `completed`, `no-answer`, `busy`, `failed`, `canceled`, `stopped`, `error`, `balance-low`.

If account PII masking is on, phone numbers, `recording_url`, and string values inside `extracted_data` arrive as `null`. The keys remain.

`tool_call_logs` is always an empty array in the API response. Function-call audit has to be written by Flask when the tool hits Care Loop.

### Function calling

There is no MCP tool named “create function.” Functions are `api_tools` on `create_graph_agent` and `update_graph_agent`, passed through as `tools_config.api_tools` with `tools` and `tools_params`. The MCP schema types `api_tools` as an open object. The function object itself is specified at `https://www.bolna.ai/docs/tool-calling/custom-function-schema`.

Each function has:

| Field | Required | Role |
| --- | --- | --- |
| `name` | Yes | `snake_case` identifier |
| `description` | Yes | When the model may call it |
| `parameters` | Yes | JSON Schema object. Types `string`, `integer`, `number`, `boolean`. |
| `key` | Yes | Must be the exact string `custom_task` |
| `value` | Yes | HTTP configuration |
| `pre_call_message` | No | Line spoken while the request runs |

`value` requires `method` (`GET`, `POST`, `PUT`, `PATCH`, `DELETE`), `url`, and `param`. Optional: `api_token`, `headers`, `pre_call_webhook_param`, `pre_call_webhook_url`.

`param` maps arguments with Python-style specifiers: `%(name)s`, `%(name)i`, `%(name)f`. Names must match `parameters.properties` exactly.

Node scope, from the `create_graph_agent` schema description: `tools_params.<name>.scope` of `node` plus a `nodes` list. The inner keys of `tools_params` are not expanded in the MCP schema. Read `https://www.bolna.ai/docs/graph-agent/tools-and-rag` before the first graph save.

Auto-injected variables, from `https://www.bolna.ai/docs/tool-calling/custom-function-variables`:

| Variable | Meaning |
| --- | --- |
| `{{agent_id}}` | Agent id |
| `{call_sid}` | Provider call id. The braces differ from the others in the doc. |
| `{{from_number}}` | Number that initiated the call |
| `{{to_number}}` | Number that received the call |

Prompt variables passed in `user_data` are substituted the same way and are not re-asked. A parameter that is neither injected nor passed is collected from the caller.

Care Loop tools, all POST, all checked server-side:

| Function | Writes | Refuses |
| --- | --- | --- |
| `get_call_context` | Nothing | Unknown caller, shared number, expired token |
| `record_glucose` | One glucose row | Missing unit, missing time, missing source, out-of-range garbage, any interpretive label |
| `record_blood_pressure` | One BP row | A single number, missing unit, missing time, missing source |
| `record_adherence` | One adherence event against an existing schedule slot | A new medicine, a dose change, a stop order |
| `record_appointment_preference` | A requested window on the existing visit | Creating a clinical order |
| `request_clinician` | An escalation row and, when a workflow is waiting, the callback POST | Free-text diagnosis or treatment advice stored as a plan |

Every tool body includes the execution id and a short-lived call token Flask minted into `user_data`. The token identifies the patient. The model does not choose the patient id.

### Webhooks

Two different webhooks exist.

Agent call webhook:

- Set with `webhook_url` on `create_agent`, `create_graph_agent`, `update_agent`, or `create_batch`.
- Bolna POSTs the execution payload as status changes.
- The endpoint must be publicly reachable.
- Source addresses to allow: `13.203.39.153`, `13.126.9.249`, `13.202.133.53`.
- A pre-call webhook without its own URL is sent to this same agent URL. Distinguish it by `status` `in-progress` plus the extra `pre_call_webhook_param` fields.
- `pre_call_webhook_param` is the on switch. `pre_call_webhook_url` is optional.

Workflow execution webhook, from the `update_workflow_settings` schema:

- `settings` is an RFC 7396 merge patch.
- The only documented section is `webhook`.
- `webhook.url` is required to turn it on. `{"webhook": null}` turns it off.
- URL must be `https` on port 443 or 8443. Private, loopback, link-local, and carrier-NAT hosts are rejected. Redirects are not followed.
- Changing host or port drops stored headers, so headers must be sent again in that call.
- Header values are write-only. Reads return `**********`. Sending the mask back is rejected. `null` removes one header.
- Reserved header names: `Host`, `Content-Length`, `Transfer-Encoding`, `Connection`, and any `x-internal*`.
- One POST per contact when the execution finishes.
- Documented body fields: `event` = `execution.terminal`, `execution_id`, `workflow_id`, `workflow_version`, `campaign_id`, `reference_id`, `status` (`completed`, `failed`, `cancelled`, `aborted`), `termination_reason`, `outcome`, `occurred_at`, `trail`.
- `termination_reason` is the end-node label, or one of `internal_error`, `required_variable_missing`, `cancelled`, `campaign_aborted`, `zombie`, `terminated`.

`test_workflow_webhook` sends one sample of that shape. `resend_workflow_webhook` replays the original payload.

Workflow `callback` nodes are the reverse direction. Care Loop POSTs to the URL from `get_workflow_callback` (`workflow_id`, `node_id`, optional `include_last`). The live node parameters require `correlation` (`payload_path` plus `matches`, default `entry.mobile_number`). Optional `payload_map`, `require_signature` (default false), and `timeout_s` from 60 to 2592000, default 86400. `status` is reserved and cannot be a `payload_map` name. The timeout branch must be explicit. Phone numbers are compared as E.164. A number without a country code is read as India (`+91`).

Care Loop turns `require_signature` on and stores the signing secret in the server environment, not in the repository.

### Knowledge bases

`create_knowledgebase` requires `url`. Optional: `chunk_size` (default 512), `similarity_top_k` (default 15), `overlapping` (default 128), `language_support` (`multilingual` only). PDF upload is outside this tool.

`get_knowledgebase` and `list_knowledgebases` take no required account fields beyond the optional `api_key`. Poll status after create.

Graph retrieval, from `https://www.bolna.ai/docs/graph-agent/tools-and-rag` and the June 2026 changelog fetched through `search_docs`:

```json
"rag_config": {
  "vector_store": {
    "provider_config": { "vector_id": "..." }
  },
  "similarity_top_k": 10
}
```

`vector_ids` is the documented array form for several collections. A node-level `rag_config` overrides a graph-level one. The MCP node schema types `rag_config` as an open object. The create response field that becomes `vector_id` was not captured in this session. Read `get_knowledgebase` before connecting one.

Use knowledge bases for stable education: how to wash hands before a fingerstick, what a home blood-pressure seat-and-rest protocol is, what to do when a reading fails. Do not use them as the patient chart.

### Post-call extraction

`create_extraction_category` requires `agent_id`, `name`, and `model`. A category is either a starting category or a follow-up, never both.

Starting-category fields: `min_duration_s` (1 to 86400) and `skip_voicemail`. Every condition that is set must pass. None set means the category runs on every call.

Follow-up fields, all three together: `parent_disposition_id` (UUID of an objective disposition in another category), `match_mode` (`in` or `not_in`), and `match_values` (exact option values). A follow-up does not run if the parent was skipped, failed, or unanswered.

`create_disposition` requires `agent_id`, `name`, and `question`. At least one of `is_subjective` and `is_objective` must be true in practice. The schema defaults both to false, so Care Loop always sets one. Objective dispositions require `objective_options`. Each option requires `value` and `condition`. `sub_options` recurse with the same shape. Subjective fields: `subjective_type` (`text`, `timestamp`, `numeric`, `boolean`, `email`, `regex`, default `text`) and, for regex, `subjective_type_config.pattern`. Place the disposition with `category_id`. `category` is the legacy name path. Omit both and it lands in `General`. `model` defaults to `gpt-4.1-mini`.

`bulk_create_dispositions` requires `agent_id` and `dispositions`. Each item requires `name` and `question` and otherwise matches `create_disposition`.

`test_dispositions` requires `agent_id` and `transcript` (maximum 50,000 characters). Optional `call_date`. Start rules pass in this test. Follow-ups still honor the parent answer. Use this before any live call.

`update_disposition` can fork a shared disposition. Care Loop creates per-agent dispositions and does not share them across agents.

Proposed first extraction set, all objective unless noted, each with an explicit “not said” option so the model is not forced:

- `medication_check`: `taken`, `missed`, `not_sure`, `not_discussed`
- `glucose_reported`: subjective numeric plus unit, or `not_reported`
- `glucose_source`: `cgm`, `glucometer`, `manual`, `not_reported`
- `bp_reported`: systolic, diastolic, or `not_reported`
- `symptom_red_flag`: a closed list of patient-reported phrases (for example severe dizziness, chest pain, fainting, signs the patient describes as a very low sugar), plus `none_reported` and `not_discussed`
- `callback_requested`: `yes`, `no`, `not_discussed`
- `preferred_language_confirmed`: the language actually used

The red-flag disposition records what the patient said. Flask, using the approved threshold set, decides whether that statement opens an escalation. The extraction text does not say “you are hypoglycemic” and does not recommend a dose.

Workflow `extraction` nodes expose these results as `extraction.<field>`. The live schema says `fields` sent by the client are ignored. The server writes them at publish from the agent’s live dispositions. `selected` must be a non-empty list of known names at publish, with no dots, braces, or edge whitespace. `agent_node_id` is required and must be the only predecessor.

## Workflow the first check-in will use

`list_workflow_node_types` returned these types: `start`, `agent`, `extraction`, `api`, `callback`, `time`, `retry`, `aisensy_whatsapp`, `end`.

Namespaces: `call`, `callback`, `entry`, `extraction`, `node`, `response`, `state`, `system`, `whatsapp`.

`set_value` into `state.*` is available and survives retries. `notify` is listed and unavailable.

| Node | Required config from the live tool | Care Loop use |
| --- | --- | --- |
| `start` | `trigger`. Only `manual` runs today. Optional `fields`. | `reference_id`, `mobile_number`, `name`, and one `timezone` field typed `timezone`. IANA names only, `Asia/Kolkata` for the synthetic India cohort. |
| `agent` | `agent_id` | `variables` carry the context packet. `timeout_s` default 86400, range 60 to 86400. |
| `extraction` | `agent_node_id` | Sits immediately after that agent node. |
| `api` | `url`. Host must be a literal. | Optional mirror into Flask. There is no credential store. Do not put a long-lived secret in `headers`. |
| `callback` | `correlation` | Clinician acknowledgement. Signature required. |
| `time` | Exactly one of `delay` or `at` | Quiet hours and “call after 10:00 local.” |
| `retry` | `target_node_id` and `attempts` (1 to 10) | The only legal cycle. No-answer and busy return here. |
| `aisensy_whatsapp` | `campaign_name` and `recipient` | Later phase, after the voice path is proven. |
| `end` | `label` and `outcome` (`success`, `failure`, `neutral`) | `label` becomes `termination_reason`. |

Local-time variables (`system.current_hour` and the rest documented on `save_workflow_draft`) require `defaults.timezone` or a required timezone field. `save_workflow_draft` requires `workflow_id`, `expected_revision`, and `definition`. `definition` requires `entry_node_id` and `nodes`. Publish fails while `validate_workflow` reports errors. After publish, the next save uses the returned `next_expected_revision` (0, because publish consumes the draft).

The first workflow:

1. `start` with the patient reference, E.164 number, display name, timezone, and the id of the context packet.
2. `agent` call. Variables are operands pointing at `entry.*`, not a copy of the chart.
3. `extraction` of the disposition names above.
4. Cases. A patient-reported red flag, or a reading Flask has not yet validated, goes to `callback` for a clinician. A clean check-in goes to `end` with outcome `success`. No answer, busy, or voicemail goes to `retry` with a small attempt list inside local daytime hours.
5. Timeout on the callback uses that node’s own `on_no_match` or an explicit `callback.status == timeout` case, then an `end` labelled for staff follow-up.

Flask remains the writer of readings. The workflow API node is not the clinical writer in phase 1, because the live API node has no credential mechanism and rejects templated hosts.

## Data model

Postgres holds the chart. Names below are the planned tables, not Bolna objects.

`patients` — synthetic identity, preferred name, primary phone in E.164, `preferred_language` (BCP-47), timezone.

`conditions` — `type_2_diabetes` or `hypertension`, status, diagnosed date, recording clinician. The agent cannot insert this table.

`medications` and `medication_schedule_slots` — the regimen as recorded. Dose text is a record of what was prescribed, not an instruction the agent may edit.

`adherence_events` — one row per slot per day: `taken`, `missed`, `unknown`. Source is `app`, `call_self_report`, or `inferred`. Inferred is never shown as fact without the rule that produced it. This follows the ABC split: initiation (first fill or first taken), implementation (taken as scheduled), persistence (still on the regimen). Those are separate columns or event types, not one percentage.

`glucose_readings` — value, unit, `measured_at`, source `manual` | `cgm` | `glucometer`, optional device label. CGM rows may be frequent. Fingersticks stay point observations.

`bp_readings` — systolic, diastolic, optional pulse, unit `mmHg`, `measured_at`, source `manual` | `home_monitor` | `clinic`, cuff or position notes when the patient supplies them.

`appointments` — consultation or laboratory, scheduled time, status, patient-requested alternate window.

`documents` — Storage path, kind `prescription` or `lab_report`, uploaded at. The file never enters a prompt.

`care_plans` — active plan, owner clinician, start.

`threshold_sets` and `threshold_rules` — version, status `draft` | `approved` | `retired`, approver, approved time. Rules name a metric, unit, comparator, value, and the escalation class. Glucose rules are source-specific where a fingerstick and a CGM threshold differ.

`care_gaps` — gap code, window, opened at, closed at, evidence row ids.

`escalations` — opened by a rule, status, clinician acknowledgement, link to the call execution if a call triggered it.

`call_sessions` — Bolna `execution_id`, `agent_id`, workflow execution id, `reference_id`, context-packet id, terminal status, `termination_reason`, duration.

`call_context_packets` — the exact JSON handed to `user_data` or workflow variables, the token hash, and expiry. This is the audit of what the agent was allowed to know.

`extraction_proposals` — raw `extracted_data` for one execution, plus `pending`, `accepted`, or `rejected`. Accepted proposals create readings or adherence rows through the same validators as the app.

`webhook_deliveries` — execution id, payload hash, received time. Duplicate deliveries no-op.

Row-level security applies to patient-facing reads. Flask uses a server credential. The browser session is the patient or the clinician, never the service role.

## Intelligence engine

All of this runs in Flask over Postgres. Bolna does not calculate it.

Adherence. For each schedule slot in the local day, an event is `taken`, `missed`, or still `unknown` until the reporting window closes. The patient app and the call write the same event type. A call report does not overwrite an app report silently. Both are kept, and the UI shows the disagreement.

Missed measurements. A patient-specific schedule says how often glucose and blood pressure are expected. A slot with no row of the accepted source after the grace period opens a missed-measurement gap. CGM silence and a missing fingerstick are different gaps.

Trends. Recharts plots glucose and blood pressure against time. Each series filter includes source and unit. Glucose charts can show a fingerstick series and a CGM series. Blood pressure charts plot systolic and diastolic. The UI shows the approved threshold lines for that patient. It does not invent a diagnosis from the slope.

Care gaps. Examples for the first release: no glucose in the expected window, no home blood pressure in the expected window, an open visit that is inside the reminder window, a lab appointment with no report uploaded after the visit date, adherence unknown for a scheduled medicine. Gaps are data, not clinical conclusions.

Escalation. A rule in an approved threshold set opens an escalation. Examples to be drafted for clinician approval, and not activated before that approval: a patient-reported red-flag phrase, a glucose below the approved low bound, a glucose above the approved high bound, a home blood pressure above the approved bound using the approved averaging rule. One extreme CGM point and one home blood-pressure reading do not use the same rule. The agent’s only action is `request_clinician`.

Consultation reminders. The workflow or a single `start_outbound_call` is scheduled from the appointment row. The call confirms the time or records a preferred window. It does not book a new clinical service by itself.

## Voice behavior

`agent_information` is the stable persona: Care Loop check-in, the patient’s language, confirm numbers by repeating them, record only what the patient just said, ask for unit and whether the number came from a sensor, a meter, or memory, and hand anything urgent to a clinician. It is sent on every turn, so it stays short.

Node prompts carry the step: greeting, medicine check, glucose, blood pressure, next visit, close. They refer to `{variable}` names from the context packet. They do not embed history.

If `preferred_language` is missing, the first node asks and `record` is a function result stored on the patient. `detected_language` can route with an expression edge when Bolna sets it. That variable is named by the graph-edge schema.

Human handoff is `request_clinician`, then a workflow callback. A live graph can also take an `event` edge if Flask sends `send_graph_agent_event` after a clinician acts during the call. The event name is an exact string agreed by the graph and the sender.

Inbound calls start with `get_call_context` using the injected from/to numbers. Until that call returns a patient, the agent can take a message and cannot read or write a chart.

## Research to implement

These sources are inputs to the design. They are not a license to copy a protocol that changes medicine.

Voice and conversational agents in diabetes

- Nayak et al., 2023, JAMA Network Open. A randomized trial of a voice conversational agent for basal insulin prescription management in type 2 diabetes. `https://jamanetwork.com/journals/jamanetworkopen/article-abstract/2812420`. Useful for call design, confirmation of numbers, and how often people will talk to a voice agent. Care Loop does not implement insulin titration or any other prescribing.
- Gong et al., 2020, JMIR. My Diabetes Coach, a mobile conversational agent plus health coaching, randomized effectiveness-implementation study. `https://www.jmir.org/2020/11/e20322/`. Implement the pattern of a coached check-in tied to self-management tasks, with a human in the loop.
- Balsa et al., 2020, Journal of Medical Systems. Usability of an intelligent virtual assistant for behavior change and self-care in older adults with type 2 diabetes. `https://link.springer.com/article/10.1007/s10916-020-01583-w`. Implement short turns, confirmation, and an older-adult usability pass before widening the cohort.
- Roca et al., 2021. A virtual assistant studied for medication adherence in type 2 diabetes with comorbid depression. `https://www.mdpi.com/1660-4601/18/22/12056`. Implement a path that notices distress and escalates, and that does not treat a mood conversation as a diagnosis.
- Shegal et al., 2025, Diabetes Research and Clinical Practice. Systematic review of conversational-agent interventions in diabetes care. `https://www.sciencedirect.com/science/article/pii/S0168822725004437`. Use it as the evidence map when choosing which check-ins are worth building.
- Kashyap et al., 2025, JMIR mHealth. Engagement with conversational-agent interventions in cardiometabolic disease. `https://mhealth.jmir.org/2025/1/e67913`. Implement engagement measurement: completed calls, patient turns, opt-out, and time-to-drop-off.
- Huang, Tiao, and Shiyanbola, 2026, Current Diabetes Reports. Scoping review of digital behavioral approaches to medication adherence in type 2 diabetes. `https://link.springer.com/article/10.1007/s11892-026-01642-5`. Keep adherence support behavioral. Do not add a clinical recommendation engine in the agent.

Blood pressure and remote monitoring

- McManus et al., 2021, BMJ. HOME BP, a digital intervention for poorly controlled hypertension. `https://www.bmj.com/content/372/bmj.m4858`. Implement supported home readings with clinician review, not an automated treatment change.
- Mehta et al., 2024, JAMA Network Open. Remote blood pressure monitoring with social support. `https://jamanetwork.com/journals/jamanetworkopen/article-abstract/2819402`. A monitor alone is not the intervention. Care Loop pairs the reading with a scheduled human review path.
- Yatabe et al., 2021, JMIR Cardio. Telemedicine with home blood pressure monitoring. `https://cardio.jmir.org/2021/2/e27347`.
- Lee et al., 2022, JAMA Network Open. What clinicians do after an alert for an elevated remote reading. `https://jamanetwork.com/journals/jamanetworkopen/article-abstract/2788120`. Alerts must be few and actionable. Every escalation needs a disposition, not only a badge.
- Davoudi et al., 2020, JMIR. Interaction phenotypes in an automated hypertension program and their relation to control. `https://www.jmir.org/2020/12/e22493/`. Log enough call and submission behavior to tell engaged, intermittent, and silent patients apart.
- Chu et al., 2024, American Journal of Hypertension. Patient experience of remote hypertension monitoring. `https://academic.oup.com/ajh/article-abstract/37/11/861/7701838`. The call script should ask whether the person was seated and rested, because patients report that the measurement conditions are the hard part.
- Noah et al., 2018, npj Digital Medicine. Meta-analysis of remote patient monitoring. `https://www.nature.com/articles/s41746-017-0002-4`. Process adherence is part of the outcome, so missed readings are a first-class gap.
- Parati, Dolan, McManus, and colleagues, 2018, Journal of Clinical Hypertension. Home blood pressure telemonitoring. `https://onlinelibrary.wiley.com/doi/abs/10.1111/jch.13305`.

Care gaps and decision support

- Wagner’s Chronic Care Model, as reviewed for type 2 diabetes by Goh et al., 2022, Systematic Reviews. `https://link.springer.com/article/10.1186/s13643-022-02117-w`. The app covers self-management support, delivery-system design, and decision support. The decision support is for clinicians.
- Wang et al., 2024, JMIR Public Health. Gaps in the hypertension and diabetes care cascade. `https://publichealth.jmir.org/2024/1/e51802`. Gap codes should follow the cascade: measured, diagnosed, on treatment, at goal, retained. Care Loop starts with measured and retained.
- Huang et al., 2023, JMIR. Scoping review of clinical decision support in diabetes. `https://www.jmir.org/2023/1/e51024/`.
- Heselmans et al., 2020, Implementation Science. A diabetes decision-support trial that did not improve quality. `https://link.springer.com/article/10.1186/s13012-019-0955-6`. Shipping rules is not an outcome. Phase 5 measures whether escalations are accepted and whether gaps close.
- Samal et al., 2024, JAMA Internal Medicine. Clinical decision support for hypertension in chronic kidney disease. `https://jamanetwork.com/journals/jamainternalmedicine/article-abstract/2816065`. Relevant once kidney disease is in the chart. Out of scope for the first condition pair except as a reason to keep thresholds patient-specific.

Measurement standards to encode as draft threshold seeds

- American Diabetes Association, Standards of Care in Diabetes—2026, glycemic goals. `https://diabetesjournals.org/care/article/49/Supplement_1/S132/163927/6-Glycemic-Goals-Hypoglycemia-and-Hyperglycemic`. A commonly cited goal for many nonpregnant adults is an A1C under 7% and CGM time in range above 70%. Those are seeds for a clinician to approve or replace. They are not hardcoded agent behavior.
- ICMR standard treatment workflow for hypertension in adults. `https://icmr.gov.in/icmrobject/uploads/STWs/1778941063_hypertensioninadults_final.pdf`. The public workflow text distinguishes a general office target from tighter targets when diabetes, CKD, or established cardiovascular disease is present, and a different target at age 80 or older. That is why thresholds are patient-specific and approved, not global constants.
- RSSDI guidance on hypertension in diabetes. `https://pmc.ncbi.nlm.nih.gov/articles/PMC9750845`.
- Asian-Pacific Society of Hypertension and Diabetes Asia Study Group consensus, 2026. `https://www.nature.com/articles/s41371-026-01150-9`. Home monitoring is the follow-up method this consensus prefers.
- Vrijens and colleagues’ ABC taxonomy (initiation, implementation, discontinuation or persistence). Current overview: `https://onlinelibrary.wiley.com/doi/abs/10.1002/9781119911685.ch37`. The adherence table uses these three phases instead of a single percent.
- Battelino and colleagues’ CGM consensus metrics (time in range, time above range, time below range) should be the CGM rollup, computed only on `source = cgm` rows. The exact consensus paper should be attached when the CGM phase is built. Fingerstick data does not enter that rollup.

What this research changes in the build

- Context packets stay small because trials that work are protocolized check-ins, not chart dumps.
- Home blood pressure is stored as repeated readings and summarized with the approved averaging rule before an escalation. One number on a phone call is a self-report, source `manual` or `home_monitor` as the patient states it.
- Escalations have a clinician outcome, because alert studies show that firing a flag is not care.
- Adherence is three phases plus a daily implementation event.
- CGM time in range is a separate computation from meter readings.
- The Nayak prescribing result is recorded as a non-goal.

## Phases

No phase starts the next one’s Bolna writes until the previous phase’s data rules exist. Phases 0 through 2 create no phone calls.

Phase 0. Foundations. Supabase project, migration set for the tables above, RLS, Storage buckets for prescriptions and reports, Flask app factory, Vite app with Tailwind and shadcn, synthetic seed of a handful of patients, and a clinician user who can approve a threshold set. Empty draft thresholds are visible and marked unapproved.

Phase 1. Patient application. Profile, conditions, medicines and schedules, glucose and blood pressure entry with the required timestamp, unit, and source, appointment list, document upload, language preference. Recharts shows the two reading types with source filters and no threshold lines until a set is approved.

Phase 2. Intelligence. Adherence from schedule slots, missed-measurement gaps, visit and lab gaps, trend lines, and the escalation table. A clinician can approve a threshold version. Only then do rules open escalations. Unit tests cover source separation, unit conversion at the boundary, and the refusal to infer a diagnosis.

Phase 3. Bolna read path. One graph agent created with `create_graph_agent`, voice chosen through `list_tts_providers` and `list_voices` for the seed languages, webhook pointed at a public Flask URL, dispositions created with `bulk_create_dispositions` and checked with `test_dispositions` against synthetic transcripts. `get_call_context` is the only function. Outbound calls in this phase use synthetic numbers or are not placed. The context packet is snapshotted.

Phase 4. Write tools and call sync. `record_glucose`, `record_blood_pressure`, `record_adherence`, and `request_clinician` through the custom-function schema. Webhook inbox is idempotent. Extraction proposals stay `pending` until the same validators accept them. `tool_call_logs` is not used as the audit.

Phase 5. Check-in workflow. `create_workflow`, `save_workflow_draft`, `validate_workflow`, `publish_workflow`, `update_workflow_settings`, then `run_workflow` for one synthetic contact. Retry, quiet hours, and the clinician callback with `require_signature` true. Campaign upload stays off until a single contact is boring and correct.

Phase 6. Inbound and multilingual confirmation. Buy or attach a number only when someone explicitly asks. `setup_inbound_agent`. Unknown numbers cannot read a chart. A second language is a second voice configuration from the live voice list, not a translated copy of the medical history.

Phase 7. Evidence pass. Measure completion, patient turns, opt-out, gap closure, and whether clinicians accept escalations. Compare the result with the limitations in Heselmans 2020 and Lee 2022 before adding any new alert.

## Risks and dependencies

| Risk | Why it is real | What to do |
| --- | --- | --- |
| The agent sounds clinical enough to be mistaken for a prescriber | Nayak 2023 did use a voice agent to manage insulin. That is adjacent and out of scope. | No tool mutates medicines or conditions. Prompts and dispositions have no dose-change language. |
| A full chart lands in the prompt | `agent_information` is sent every turn. Large prompts cost money and leak into transcripts and recordings. | Context packet is an allow-list. Packets are stored and reviewed. |
| Extraction becomes the chart | `extracted_data` is model output with a confidence and a skipped state. | Proposals only. Validators and, for escalations, an approved threshold. |
| `completed` is treated as a successful conversation | The payload reference says a rejected call can still be `completed`. | Branch on `termination_reason`, duration, and a `user:` line. |
| Duplicate webhooks double-write readings | One call produces several POSTs with the same `id`. | Upsert on execution id and payload hash. |
| Localhost webhooks | Workflow webhooks reject private hosts and require public HTTPS on 443 or 8443. Agent webhooks must also be publicly reachable. | A tunnel or a deployed Flask URL. Document the URL in the environment, not in git. |
| Secrets in the workflow API node | The live node type says there is no credential mechanism. | Clinical writes go through the function token or the signed webhook, not through a header baked into the draft. |
| PII masking nulls the fields the inbox needs | Documented behavior when masking is enabled. | Confirm the account setting before relying on `user_number` or extracted strings. Keep Care Loop’s own patient link in `reference_id` and the context packet. |
| `tool_call_logs` is empty | Documented. | Flask logs every tool request and response. |
| Voice defaults are English | `create_graph_agent` defaults language to `en` and the described default stack is Deepgram nova-3 and ElevenLabs turbo v2.5. | Call `list_tts_providers` and `list_voices` for each launched language before publish. |
| Execution history queries die past 7 days | `list_agent_executions` enforces that window. | Persist every webhook into `call_sessions` at arrival. |
| Batch scheduling slips | `schedule_batch` rounds up to 10 minutes and refuses times under 2 minutes ahead. | Schedule from Flask with that slack. Prefer workflow `time` nodes when the wait must honor a patient timezone. |
| Shared or missing country codes | Callback correlation reads a bare number as `+91`. | Store E.164 only. |
| Knowledge base used as a chart | The MCP create tool is URL-only, and retrieval injects chunks into the live turn. | Education URLs only. PDFs stay in Storage. |
| Disposition edits fork | `update_disposition` with `agent_id` can copy a shared disposition. | One disposition set per agent. Test with `test_dispositions` after every change. |
| Balance and concurrency | `start_outbound_call`, `schedule_batch`, `run_workflow`, and `start_workflow_campaign` spend wallet balance. | `get_user_info` before any live dial. Synthetic phase does not dial real patients. |
| Clinical rules shipped as code constants | Guideline numbers differ by comorbidity and age, and decision-support trials often fail. | Versioned, clinician-approved `threshold_sets`. Draft seeds cite ADA 2026 and the ICMR workflow and stay inactive. |
| Supabase service role in the client | Standard failure mode. | Browser uses the user session. Flask holds the server credential. |
| Buying a phone number | `buy_phone_number` is a recurring charge. | Not part of setup. A later explicit request only. |

Dependencies before the first live call:

- A Bolna account with balance, already connected in Cursor as `user-bolna`
- A public HTTPS callback origin for Flask
- A Supabase project and a synthetic seed
- At least one clinician account who can approve thresholds
- A language list checked against `list_tts_providers`
- An allow-list of Bolna webhook source IPs on the receiver
- The custom-function page and the execution-payload page re-read at implementation time, in case Bolna adds fields

## Out of scope for this document

This file does not create the Flask app, the React app, a Supabase migration, a Bolna agent, a workflow, a phone number, or a call. Those start only when implementation is requested, and they start at phase 0.
