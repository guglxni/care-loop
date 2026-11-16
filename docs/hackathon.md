# Build Out Loud: CareLoop presenter notes

Source for the event text below: [Build Out Loud: A Wispr Flow × Bolna Hackathon](https://luma.com/1a2rjj9r), fetched 15 November 2026. Quotes are from that page. This file does not add a scorecard the page does not publish.

Bolna facts below are the ones still written in [bolna-demo-link.md](bolna-demo-link.md) and [DEMO.md](../DEMO.md). The showcase page repeats them at `/showcase`.

## Event

| | |
| --- | --- |
| Title | Build Out Loud: A Wispr Flow × Bolna Hackathon |
| When | Sunday, November 15, 2026, 12:00 PM – 5:00 PM GMT+5:30. The about text also says “In person · 15th November 2026 · 12 PM to 5 PM”. |
| Where | Bolna : AI Voice Agents, 2nd Floor, TOWER-B, MANTRI COMMERCIO, Marathahalli – Sarjapur Outer Ring Rd, Kariyammana Agrahara, Bellandur, Bengaluru, Karnataka 560103, India |
| Presented by | Bolna |
| Hosted by | Tanisha Sharma |
| Listed under | Bengaluru, and the AI topic on Luma |
| Registration | “Approval Required. Your registration is subject to host approval.” |

Afternoon on the Luma page:

- 12:00 to 12:30 PM: Registration
- 12:30 to 1:00 PM: Instructions and setup
- 1:00 to 4:00 PM: Build
- 4:30 to 5:00 PM: Awards

The page does not describe 4:00 to 4:30 PM.

## What the page requires

From **The Setup**:

> Wispr Flow turns what you say into text, so every prompt, edit and fix happens by voice.
>
> Bolna is where your agents come to life. Create them, make calls, read transcripts and tune how they perform.

From **The Rules**:

> - Build entirely by voice using Wispr Flow, with no typing
> - Build a working voice agent or multi-agent system on Bolna
> - Teams can have up to 4 people
> - Make at least 3 test calls, each over 45 seconds, with people who've agreed to take part
> - Show how your project improved along the way

From **What You'll Submit**:

> - The agent you've built
> - A short note on how you used Wispr Flow
> - Examples of how you tested and improved your agent

The page then says: “Full guidelines go out to registered participants.”

**Judging criteria:** the Luma page does not publish a scored rubric, weights, or a judge checklist. Do not invent one. The rules and the submission list above are the public requirements. **What's Up for Grabs** says only: “Prizes, awards and a few surprises. We'll announce them soon.”

**What You Could Build** is a list of ideas, not a scoring rubric:

> - An AI recruiter that interviews and evaluates candidates
> - A multilingual support agent
> - An outbound agent that qualifies leads and handles objections
> - A feedback agent that runs surveys and pulls out insights
> - An agent that keeps up when customers change their minds mid-call
>
> We'd love to see projects that go beyond a basic voice agent.

CareLoop is one patient-companion graph agent. That is “a working voice agent,” not a claim that it is a multi-agent system, and not a claim that it matches the recruiter or outbound-lead ideas.

## Wispr Flow, without a fake integration

Wispr Flow is voice dictation. Its site says it “turns speech into clear, polished writing in every app,” is “Available on Mac, Windows, iPhone, and Android,” and “types wherever your cursor is… with no setup or integrations” ([wisprflow.ai](https://wisprflow.ai/)).

CareLoop does not install the Wispr SDK, and this repo does not add one. The Luma rule still asks the team to build by voice. Concrete step for the judge:

1. Open `/showcase` in the browser.
2. Run Wispr Flow the way the judge already does, as the desktop or phone app.
3. Focus **Note on how Wispr Flow was used**.
4. Dictate the short submission note. Wispr types into that field. Do not paste a prewritten integration claim.
5. Choose **Keep this note in the tab**. The text stays in the browser tab. It is not sent to Bolna, Wispr, or Luma.

The same app can dictate into Calendar’s **Preferred time note**. That field is also session-only and does not book a visit.

## Demo script

Say what is verified. The three-call rule is not met.

1. **Rules.** Open the Luma page and read **The Rules**. Say the page has no public scorecard and that prizes are not announced there.
2. **The agent you submit.** On `/showcase`, read CareLoop AI Health Companion, `8ad7201e-2fe5-4595-8a45-35ed60fb1fcd`. Nodes recorded in `docs/bolna-demo-link.md`: `start`, `medication`, `glucose`, `blood_pressure`, `consultation`, `concern`, `escalation`, `close`. Language on the agent is `en`. Purpose routes on `recipient_data.purpose`: `medication_check`, `glucose_check`, `bp_check`, `appointment_reminder`.
3. **Wispr note.** Dictate the submission note into the showcase field, as above. That is the “short note on how you used Wispr Flow.” It is dictation into a browser field, not a Wispr API.
4. **How it changed.** Use only the decisions already written down. The start node is an LLM: a router was rejected unless it had an unconditional catch-all, and a start router runs before the caller has spoken. `api_tools` were omitted because `http://127.0.0.1:5000` is not reachable from Bolna. `validation.valid` is true, with a warning that four purpose edges share priority 0 (`duplicate_transition_priorities`).
5. **What was tested.** Show the three `test_dispositions` rows. They are synthetic transcripts, not phone calls. Every question in those runs returned `status: completed`. Category `Call outcomes`, id `0090ff6d-242b-46d6-bef8-3d85ff2e6064`, model `gpt-4.1-mini`.
6. **The call rule, unmet.** Luma asks for at least three test calls, each over 45 seconds, with people who agreed. This repo has not placed an outbound call, and no Bolna execution id was created. Do not dial from the showcase. `start_outbound_call`, `schedule_batch`, and `buy_phone_number` are out of this demo.
7. **Inbound number, if someone calls in.** The linked number is `+14235838428`, phone id `8820ada7-a2c5-44c5-b658-ea3109b6b702`. No number was purchased for that link. A judge calling that number is their own call. This script does not place one.
8. **Chart writes.** Say that live chart-writing tools depend on a public webhook. Bolna’s cloud cannot call this laptop, so `api_tools` are omitted and `webhook_url` is unset. The Flask inbox can store `extracted_data` on a voice-call row. It does not copy those values onto the glucose or blood-pressure chart.
9. **What is not Google’s glucose model.** Say that unofficial GlucoFM packages are not Google’s model. CareLoop does not call them. The forecast route, when the library is missing, stays on TimesFM with an empty estimate list. Details stay in `docs/glucose-forecast.md`.

| Published item | What the presenter shows | Status in this repo |
| --- | --- | --- |
| Build entirely by voice using Wispr Flow, with no typing | Dictate the showcase note with the Wispr Flow app | Wispr is the judge’s app. No Wispr SDK in CareLoop |
| A working voice agent on Bolna | Agent id, graph nodes, inbound number | Agent and inbound link are recorded. No live execution in this package |
| Teams of up to 4 | Say the team size | Not a software check |
| At least 3 consented test calls, each over 45 seconds | Say this is still required | Not met. No outbound call was placed |
| Show how the project improved | Start-node choice, omitted `api_tools`, disposition tests | Written in `docs/bolna-demo-link.md` |
| Submit the agent | Read the agent id | The agent exists on the connected account |
| A short note on Wispr Flow | The dictated field | Local to the browser tab |
| Examples of testing and improvement | The three transcript rows | `test_dispositions` only. Not phone calls |

## Bolna MCP capabilities

Grouped from the connected `user-bolna` tool list on 15 November 2026. A tool is listed only if that list includes it.

| Group | Tools on the MCP server | Mark | What a patient-companion demo can honestly say |
| --- | --- | --- | --- |
| Graph agent | `get_graph_agent`, `validate_graph_agent`, `send_graph_agent_event`, `create_graph_agent`, `update_graph_agent` | Already used | `get_graph_agent` is the source for the agent section in `docs/bolna-demo-link.md`. `validate_graph_agent` checks a graph without saving. `send_graph_agent_event` needs a live call. Creating or replacing the graph is a live edit and is not part of this page. |
| Multilingual language field | Agent `language` on `get_agent` / `update_agent`; `list_tts_providers`; `list_voices` | Available but not wired | The recorded agent language is `en`. Companion can show Hindi, English, Tamil, and Kannada as local state. That menu does not write Bolna. `list_tts_providers` and `list_voices` take a BCP-47 code. This app does not call them. |
| Inbound number | `setup_inbound_agent`, `list_phone_numbers`, `unlink_inbound_agent` | Already used | Linked: `+14235838428`, phone id `8820ada7-a2c5-44c5-b658-ea3109b6b702`. `list_phone_numbers` failed on a response-shape change; the number was read from the grouped payload. No number was purchased. `unlink_inbound_agent` would remove that routing. |
| Dispositions and `test_dispositions` | `list_dispositions`, `get_disposition`, `create_disposition`, `update_disposition`, `bulk_create_dispositions`, `test_dispositions`, `list_extraction_categories`, `create_extraction_category`, `update_extraction_category` | Already used | Three synthetic transcripts, not calls. Results are in the verified list. `delete_disposition` and `delete_extraction_category` remove future extraction and are unsuitable here. |
| Webhooks | Agent `webhook_url` through `update_agent`; `test_workflow_webhook`; `resend_workflow_webhook`; `get_workflow_callback` | Already used in this repo for the local inbox; Bolna delivery is not wired | `POST /api/v1/bolna/webhook` is implemented and covered by `backend/tests/test_voice.py`. The agent has no `webhook_url`, so Bolna’s cloud has not delivered one. Workflow webhook tools belong to workflows, and no CareLoop workflow exists. |
| Workflows | `list_workflows`, `create_workflow`, `get_workflow`, `get_workflow_draft`, `save_workflow_draft`, `patch_workflow_draft`, `validate_workflow`, `publish_workflow`, `list_workflow_node_types`, `run_workflow`, `test_workflow_webhook` | Available but not wired | Nothing in this repo publishes a Bolna workflow. `run_workflow` and `start_workflow_campaign` create real executions. Do not run them in this demo. `list_workflow_node_types` was not called for this note. |
| Knowledge base URL ingest | `create_knowledgebase`, `list_knowledgebases`, `get_knowledgebase` | Available but not wired | `create_knowledgebase` scrapes a URL. The tool description says PDF upload is not supported on this path. No knowledge base is attached in `docs/bolna-demo-link.md`. `delete_knowledgebase` drops that context and is unsuitable here. |
| Docs search | `search_docs`, `get_doc` | Available but not wired | Searches Bolna’s documentation. The CareLoop app does not call it. Safe to read during a question. It does not change the agent. |
| Batches | `list_batches`, `get_batch`, `list_batch_executions`, `create_batch`, `schedule_batch`, `stop_batch` | Available but not wired | No CareLoop batch exists. `create_batch` builds an outbound-call batch. `schedule_batch` commits that batch to real calls. Do not schedule one. `delete_batch` removes it. |
| Executions | `list_agent_executions`, `get_execution`, `get_execution_debug`, `get_execution_raw_logs` | Available but not wired | Reading an execution does not place a call. This demo has no execution id. The seed row `demo-call-001` is fixture text in `DEMO.md`, not a Bolna execution. |

`list_batches` still describes itself as read-only and says batch creation and scheduling are not available through this connector yet. `create_batch` and `schedule_batch` are also on the same tool list, and `schedule_batch` says it commits the batch to placing real calls. Treat scheduling as unsuitable either way.

### Unsuitable for this demo

These tools exist. Do not use them while presenting CareLoop.

| Tool | Why it stays off |
| --- | --- |
| `start_outbound_call` | Places a real phone call and spends balance |
| `schedule_batch`, `create_batch` | Sets up outbound calls. Scheduling commits the dial |
| `run_workflow`, `start_workflow_campaign` | Run real calls or messages for contacts |
| `buy_phone_number` | Purchases a number. The tool description says this is a recurring charge, around $5 a month, until the number is removed |
| `search_phone_numbers` | Only a search, but it exists to feed `buy_phone_number` |
| `delete_agent` | Permanently deletes the agent, its batches, and its execution history |
| `delete_phone_number` | Removes the rented number and stops billing. The number is not guaranteed back |
| `delete_knowledgebase`, `delete_disposition`, `delete_extraction_category`, `delete_workflow`, `delete_batch` | Delete data the demo would then have to rebuild |
| `unlink_inbound_agent` | Drops the inbound route on `+14235838428` |

No outbound call has been placed. `api_tools` were omitted because localhost is not reachable from Bolna.

## Verified

Recorded in `docs/bolna-demo-link.md` and `DEMO.md`, and still present when this note was written:

- Agent **CareLoop AI Health Companion**, id `8ad7201e-2fe5-4595-8a45-35ed60fb1fcd`, language `en`, confirmed with `get_graph_agent`.
- Nodes: `start`, `medication`, `glucose`, `blood_pressure`, `consultation`, `concern`, `escalation`, `close`.
- Inbound link to `+14235838428`, phone id `8820ada7-a2c5-44c5-b658-ea3109b6b702`. No number was purchased in that step.
- `test_dispositions` on three synthetic transcripts. Not phone calls. Each question returned `status: completed`.

  | Transcript | call_purpose | medication_adherence | missed_reason | glucose_context | escalation_status |
  | --- | --- | --- | --- | --- | --- |
  | Missed metformin because they were away from home | Medication_Check | Missed | I was away from home | Not_Discussed | Not_Discussed |
  | Fasting glucose of 142 mg/dL from a glucometer | Glucose_Check | Not_Discussed | Not_Discussed | Fasting | Not_Discussed |
  | Chest discomfort, agent told them to contact emergency services | Patient_Concern | Not_Discussed | Not_Discussed | Not_Discussed | Escalated |

- No `webhook_url` on the agent. `api_tools` omitted.
- No outbound call was placed.
- Local context packet and webhook inbox: `backend/tests/test_voice.py`. The inbox test posts from the Flask test client. A posted glucose of 400 mg/dL does not change the reading count.

## Simulated, or not done

- The Luma rule of three consented test calls, each longer than 45 seconds. Not done.
- Any Bolna execution id. Companion’s “Start a voice check-in” control does not place a call (`DEMO.md`).
- Webhook delivery from Bolna’s cloud. `webhook_url` is unset.
- Live chart-writing tools. They depend on a public webhook Bolna can reach. Localhost was not attached.
- `voice_calls.bolna_call_id` `demo-call-001`. Fixture text, not an execution.
- Wispr Flow inside this repository. The presenter uses the Wispr app they already have.
- Unofficial GlucoFM. Those packages are not Google’s model, and CareLoop does not call them. Google’s GlucoFM paper is also not wired in. See `docs/glucose-forecast.md`.
- A numeric TimesFM forecast while the library is missing. The route stays `available: false` with `estimates: []` (`DEMO.md`).
- Bolna workflows, URL knowledge bases, batches, and execution history for this agent. The tools exist. They are not wired to CareLoop.
- Hindi, Tamil, or Kannada on the Bolna agent. The recorded language field is `en`.
