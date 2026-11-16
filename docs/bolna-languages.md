# Bolna languages

Agent CareLoop AI Health Companion, `8ad7201e-2fe5-4595-8a45-35ed60fb1fcd`. Confirmed with `get_graph_agent` after `update_graph_agent`. `validation.valid` is true. No phone call was placed.

The stored prompts do not contain "only English" or "speak English".

## Language instruction

Global `agent_information`, prepended to every node:

```
When {preferred_language} is present, start in that language. {preferred_language} may be en, hi, or kn, which are English, Hindi, and Kannada. Supported languages are English, Hindi, and Kannada. Follow detected_language ({detected_language}). If the person switches language, continue in the language they are using. If they speak another language, say you can continue in English, Hindi, or Kannada and ask which they prefer.
```

`detected_language` is the built-in graph variable Bolna documents for switching language mid-call. It is not a transcriber field.

The same instruction is on the `start` node, after the outbound opening, and on the `inbound` node, where the agent may ask what the person needs in the language they are speaking.

Outbound opening, stored as the welcome message and as the `start` node opening line:

```
Hello {patient_name}, this is the CareLoop AI assistant calling on behalf of {clinic_name}. {call_reason}
```

That welcome does not ask what the person needs. The agent does not diagnose or change doses.

## Transcriber

`get_agent` still shows transcriber `language` `en` (Deepgram `nova-3`). `multilingual_config` is null. That language code was not changed.

`update_graph_agent` has no language parameter and keeps the transcriber. `update_agent` accepts name, welcome message, webhook, synthesizer, ingest source, telephony provider, and prompts. It has no transcriber language field, so this change did not send one.

## Left in place

Nine `api_tools` remain: `get_context`, `get_medications`, `get_history`, `post_glucose`, `post_blood_pressure`, `post_adherence`, `get_upcoming_consultation`, `post_follow_up_task`, and `post_clinical_escalation`. `webhook_url` is still set. Graph `rag_config` was null before and after this update. Nodes other than `start` and `inbound` were not rewritten.
