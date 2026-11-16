# Ravi Sharma knowledge base

The knowledge page is live. A Bolna knowledge base was created from it and attached as RAG. No call was placed. The agent's tools, webhook, and purpose prompts were left unchanged.

## Page

`GET /api/v1/patients/a52a0000-0000-4000-8000-000000000052/knowledge` is served by the Flask app factory on `127.0.0.1:5055`.

Local check: **200**, `text/markdown`, first line `Care coordination facts. Not medical advice. Do not diagnose or change medicines.` The body is Ravi Sharma's chart.

The existing Cloudflare quick tunnel to `http://127.0.0.1:5055` was reused. No second tunnel was started.

Public check of the same path: **200**, same advice line.

`https://echo-criterion-revolutionary-months.trycloudflare.com/api/v1/patients/a52a0000-0000-4000-8000-000000000052/knowledge`

## Bolna

`create_knowledgebase` was called with that public URL and `language_support: multilingual`. The create response returned `rag_id` and `status: processing`. It did not return `vector_id`.

`get_knowledgebase` then reported `status: processed` and returned `vector_id`. That value was not invented.

RAG is the graph-level `rag_config` on agent `8ad7201e-2fe5-4595-8a45-35ed60fb1fcd`. `vector_store.provider` is `lancedb`. `provider_config.vector_id` is the id from `get_knowledgebase`. `similarity_top_k` is 15. No node has its own `rag_config`.

After the update, `validation.valid` is true. These were compared to the graph read before the update and were unchanged:

- Nine `api_tools`: `get_context`, `get_medications`, `get_history`, `post_glucose`, `post_blood_pressure`, `post_adherence`, `get_upcoming_consultation`, `post_follow_up_task`, `post_clinical_escalation`
- Webhook `https://echo-criterion-revolutionary-months.trycloudflare.com/api/v1/bolna/webhook`
- Welcome message, `agent_information`, routing instructions, and every node prompt, including the multilingual purpose prompts on `start` and `inbound`

## Result

| Field | Value |
| --- | --- |
| Knowledge base id | `9609d1af-d58f-4813-8f97-fd6cf84ae8f1` |
| Vector id | `2f4d9e35-29a6-4a73-bf19-08f136d3aa7f` |
| Patient | Ravi Sharma `a52a0000-0000-4000-8000-000000000052` |
| Agent | `8ad7201e-2fe5-4595-8a45-35ed60fb1fcd` |
| Status | processed |
| RAG attached | yes |
| Call placed | no |
