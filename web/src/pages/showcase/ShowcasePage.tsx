import { useId, useState, type FormEvent } from "react"
import { PageHeader } from "@/components/layout/PageHeader"
import { SectionHeading } from "@/components/layout/SectionHeading"
import { Badge, type BadgeTone } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Label, Textarea } from "@/components/ui/field"

const LUMA_URL = "https://luma.com/1a2rjj9r"
const WISPR_URL = "https://wisprflow.ai/"

const linkClass =
  "underline decoration-line underline-offset-4 hover:decoration-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sage focus-visible:ring-offset-2 focus-visible:ring-offset-canvas"

type Mark = "used" | "open" | "unsuitable"

const markLabel: Record<Mark, string> = {
  used: "Already used",
  open: "Available, not wired",
  unsuitable: "Unsuitable",
}

const markTone: Record<Mark, BadgeTone> = {
  used: "green",
  open: "blue",
  unsuitable: "amber",
}

const rules = [
  "Build entirely by voice using Wispr Flow, with no typing",
  "Build a working voice agent or multi-agent system on Bolna",
  "Teams can have up to 4 people",
  "Make at least 3 test calls, each over 45 seconds, with people who've agreed to take part",
  "Show how your project improved along the way",
]

const submission = [
  "The agent you've built",
  "A short note on how you used Wispr Flow",
  "Examples of how you tested and improved your agent",
]

const capabilities: { group: string; tools: string; mark: Mark; note: string }[] = [
  {
    group: "Graph agent",
    tools: "get_graph_agent, validate_graph_agent, send_graph_agent_event, create_graph_agent, update_graph_agent",
    mark: "used",
    note: "get_graph_agent is the source for the agent recorded in docs/bolna-demo-link.md. Sending an event needs a live call. This page does not create or replace the graph.",
  },
  {
    group: "Multilingual language field",
    tools: "language on get_agent and update_agent, list_tts_providers, list_voices",
    mark: "open",
    note: "The recorded agent language is en. Companion can show Hindi, English, Tamil, and Kannada locally. That menu does not write Bolna, and this app does not call the voice lists.",
  },
  {
    group: "Inbound number",
    tools: "setup_inbound_agent, list_phone_numbers, unlink_inbound_agent",
    mark: "used",
    note: "+14235838428 is linked. Phone id 8820ada7-a2c5-44c5-b658-ea3109b6b702. No number was purchased. Unlink would remove that route.",
  },
  {
    group: "Dispositions and test_dispositions",
    tools: "list_dispositions, get_disposition, create_disposition, update_disposition, bulk_create_dispositions, test_dispositions, list_extraction_categories, create_extraction_category",
    mark: "used",
    note: "Three synthetic transcripts returned status completed. They were not phone calls. Deleting a disposition or its category is unsuitable here.",
  },
  {
    group: "Webhooks",
    tools: "webhook_url via update_agent, test_workflow_webhook, resend_workflow_webhook, get_workflow_callback",
    mark: "used",
    note: "The Flask inbox POST /api/v1/bolna/webhook is already in this repo and tested locally. The agent has no webhook_url, so Bolna has not delivered one. Live chart-writing tools depend on a public webhook.",
  },
  {
    group: "Workflows",
    tools: "list_workflows, create_workflow, save_workflow_draft, validate_workflow, publish_workflow, list_workflow_node_types, run_workflow, test_workflow_webhook",
    mark: "open",
    note: "No CareLoop workflow is published. run_workflow and start_workflow_campaign place real calls or messages, so those runs are unsuitable in this demo.",
  },
  {
    group: "Knowledge base URL ingest",
    tools: "create_knowledgebase, list_knowledgebases, get_knowledgebase",
    mark: "open",
    note: "create_knowledgebase scrapes a URL. PDF upload is not on that tool. None is attached to this agent. delete_knowledgebase would drop that context.",
  },
  {
    group: "Docs search",
    tools: "search_docs, get_doc",
    mark: "open",
    note: "Searches Bolna documentation. The app does not call it. Reading docs does not change the agent.",
  },
  {
    group: "Batches",
    tools: "list_batches, get_batch, list_batch_executions, create_batch, schedule_batch, stop_batch",
    mark: "open",
    note: "No batch exists for this agent. create_batch and schedule_batch set up outbound calls. schedule_batch commits real dials, so it is unsuitable here.",
  },
  {
    group: "Executions",
    tools: "list_agent_executions, get_execution, get_execution_debug, get_execution_raw_logs",
    mark: "open",
    note: "Reading an execution does not place a call. This demo has no execution id. The seed id demo-call-001 is fixture text, not a Bolna execution.",
  },
]

const unsuitable = [
  ["start_outbound_call", "Places a real call and spends balance."],
  ["schedule_batch and create_batch", "Prepare outbound calls. Scheduling commits the dial."],
  ["run_workflow and start_workflow_campaign", "Run real calls or messages."],
  ["buy_phone_number", "Buys a number. The tool describes a recurring charge of about $5 a month."],
  ["delete_agent", "Permanently deletes the agent, its batches, and its execution history."],
  ["delete_phone_number", "Removes the rented number. Recovery is not guaranteed."],
  ["delete_knowledgebase, delete_disposition, delete_workflow, delete_batch", "Delete data this demo would have to rebuild."],
  ["unlink_inbound_agent", "Removes the inbound route on +14235838428."],
]

const verified = [
  "Agent CareLoop AI Health Companion, id 8ad7201e-2fe5-4595-8a45-35ed60fb1fcd, language en. Recorded from get_graph_agent in docs/bolna-demo-link.md.",
  "Nodes: start, medication, glucose, blood_pressure, consultation, concern, escalation, close.",
  "Inbound +14235838428, phone id 8820ada7-a2c5-44c5-b658-ea3109b6b702. No number was purchased for that link.",
  "test_dispositions completed on three synthetic transcripts. Not phone calls. Category Call outcomes, 0090ff6d-242b-46d6-bef8-3d85ff2e6064.",
  "No outbound call has been placed. api_tools were omitted because localhost is not reachable from Bolna.",
  "The local webhook inbox is covered by backend/tests/test_voice.py. A posted glucose value does not write the chart.",
]

const notVerified = [
  "Three consented test calls, each over 45 seconds. The Luma rule is unmet.",
  "A Bolna execution id. Companion does not place a call from this app.",
  "Webhook delivery from Bolna’s cloud. webhook_url is unset.",
  "Live chart writes during a call. Those tools depend on a public webhook.",
  "Wispr Flow as an SDK in this repo. The presenter dictates with the Wispr app into the field below.",
  "Unofficial GlucoFM. It is not Google’s model, and CareLoop does not call it.",
  "Workflows, URL knowledge bases, batches, and a multilingual Bolna language. The tools exist. They are not wired. The agent language is en.",
]

const transcripts = [
  ["Missed metformin, away from home", "Medication_Check", "Missed", "I was away from home", "Not_Discussed", "Not_Discussed"],
  ["Fasting glucose 142 mg/dL", "Glucose_Check", "Not_Discussed", "Not_Discussed", "Fasting", "Not_Discussed"],
  ["Chest discomfort, told to contact emergency services", "Patient_Concern", "Not_Discussed", "Not_Discussed", "Not_Discussed", "Escalated"],
]

function MarkBadge({ mark }: { mark: Mark }) {
  return <Badge tone={markTone[mark]}>{markLabel[mark]}</Badge>
}

export function ShowcasePage() {
  const noteId = useId()
  const [draft, setDraft] = useState("")
  const [saved, setSaved] = useState("")
  const [error, setError] = useState("")

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const note = draft.trim()
    if (!note) {
      setError("Dictate or write a note before keeping it.")
      return
    }
    setSaved(note)
    setError("")
  }

  return (
    <div className="flex w-full min-w-0 flex-col gap-12 text-ink">
      <PageHeader
        title="Hackathon showcase"
        lede="Presenter notes for Build Out Loud. Facts below are the Bolna link already recorded for CareLoop, plus the rules published on the Luma page."
        note="Synthetic chart. Not medical advice. This page does not place a call."
      />

      <section className="flex flex-col gap-4">
        <SectionHeading
          title="Verified Bolna facts"
          lede="Taken from docs/bolna-demo-link.md and DEMO.md. No outbound call has been placed."
        />
        <dl className="border-t border-line">
          <Fact label="Agent">CareLoop AI Health Companion</Fact>
          <Fact label="Agent id">8ad7201e-2fe5-4595-8a45-35ed60fb1fcd</Fact>
          <Fact label="Language field">en. Hindi, Tamil, and Kannada are not set on the agent.</Fact>
          <Fact label="Inbound number">+14235838428</Fact>
          <Fact label="Phone id">8820ada7-a2c5-44c5-b658-ea3109b6b702</Fact>
          <Fact label="Graph nodes">
            start, medication, glucose, blood_pressure, consultation, concern, escalation, close
          </Fact>
        </dl>
        <p className="max-w-prose text-sm leading-6 text-muted">
          api_tools were omitted because localhost is not reachable from Bolna. webhook_url is unset.
          Live chart-writing tools depend on a public webhook. Unofficial GlucoFM is not Google’s model,
          and this app does not call it.
        </p>
      </section>

      <section className="flex flex-col gap-4">
        <SectionHeading
          title="Published event requirements"
          lede="Quoted from the Luma page. That page does not publish a scored judging rubric or a prize list."
        />
        <p className="max-w-prose text-sm leading-6 text-ink">
          <a className={linkClass} href={LUMA_URL}>
            Build Out Loud: A Wispr Flow × Bolna Hackathon
          </a>
          . Sunday, November 15, 2026, 12:00 PM – 5:00 PM GMT+5:30, in Bengaluru. Presented by Bolna.
          Hosted by Tanisha Sharma.
        </p>
        <div className="grid gap-6 md:grid-cols-2">
          <QuoteList title="The Rules" items={rules} />
          <QuoteList title="What You'll Submit" items={submission} />
        </div>
        <p className="max-w-prose text-sm leading-6 text-muted">
          The page also says “Full guidelines go out to registered participants” and “Prizes, awards and
          a few surprises. We'll announce them soon.” The three-call rule is not met in this repo.
        </p>
      </section>

      <section className="flex flex-col gap-4">
        <SectionHeading
          id="wispr-note"
          title="Wispr Flow note"
          lede="Wispr Flow types into the field that has the cursor. CareLoop does not include the Wispr SDK."
        />
        <form className="flex max-w-3xl flex-col gap-3" onSubmit={onSubmit}>
          <Label htmlFor={noteId}>Note on how Wispr Flow was used</Label>
          <Textarea
            id={noteId}
            value={draft}
            maxLength={1000}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Focus here, then dictate with Wispr Flow"
          />
          {error ? (
            <p role="alert" className="text-sm text-amber">
              {error}
            </p>
          ) : null}
          <p className="text-sm leading-6 text-muted">
            <a className={linkClass} href={WISPR_URL}>
              Wispr Flow
            </a>{" "}
            is a dictation app for Mac, Windows, iPhone, and Android. If it is already running, put the
            cursor in this field and speak. The note stays in this tab. It is not sent to Bolna, Wispr, or
            Luma.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" size="sm">
              Keep this note in the tab
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setDraft("")
                setSaved("")
                setError("")
              }}
            >
              Clear
            </Button>
          </div>
        </form>
        {saved ? (
          <p className="max-w-3xl rounded-2xl border border-line bg-card px-4 py-3 text-sm leading-6 text-ink">
            Kept in this tab only: {saved}
          </p>
        ) : null}
      </section>

      <section className="flex flex-col gap-4">
        <SectionHeading
          title="Bolna MCP capabilities"
          lede="Only tools present on the connected Bolna MCP server. Marks say whether CareLoop already uses them."
        />
        <div className="overflow-x-auto rounded-2xl border border-line bg-card">
          <table className="w-full min-w-[760px] text-left text-sm">
            <caption className="sr-only">Bolna MCP capabilities for the patient companion demo</caption>
            <thead>
              <tr className="border-b border-line text-muted">
                <th scope="col" className="px-4 py-3 font-medium">
                  Group
                </th>
                <th scope="col" className="px-4 py-3 font-medium">
                  Mark
                </th>
                <th scope="col" className="px-4 py-3 font-medium">
                  What it means here
                </th>
              </tr>
            </thead>
            <tbody>
              {capabilities.map((row) => (
                <tr key={row.group} className="border-b border-line align-top last:border-b-0">
                  <th scope="row" className="px-4 py-4 font-medium text-ink">
                    {row.group}
                    <span className="mt-1 block font-normal text-muted">{row.tools}</span>
                  </th>
                  <td className="px-4 py-4">
                    <MarkBadge mark={row.mark} />
                  </td>
                  <td className="px-4 py-4 leading-6 text-ink">{row.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="flex flex-col gap-4">
        <SectionHeading
          title="Leave these tools unused"
          lede="They are on the MCP server. They spend money, place calls, or delete the demo."
        />
        <ul className="border-t border-line">
          {unsuitable.map(([name, reason]) => (
            <li
              key={name}
              className="grid gap-2 border-b border-line py-4 sm:grid-cols-[16rem_minmax(0,1fr)] sm:gap-6"
            >
              <span className="font-medium text-ink">{name}</span>
              <span className="text-sm leading-6 text-muted">{reason}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="flex flex-col gap-4">
        <SectionHeading
          title="Disposition checks"
          lede="test_dispositions on synthetic transcripts. Every question returned status completed. These were not calls."
        />
        <div className="overflow-x-auto rounded-2xl border border-line bg-card">
          <table className="w-full min-w-[760px] text-left text-sm">
            <caption className="sr-only">Disposition results from synthetic transcripts</caption>
            <thead>
              <tr className="border-b border-line text-muted">
                {["Transcript", "Purpose", "Adherence", "Missed reason", "Glucose", "Escalation"].map((heading) => (
                  <th key={heading} scope="col" className="px-4 py-3 font-medium">
                    {heading}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {transcripts.map((row) => (
                <tr key={row[0]} className="border-b border-line align-top last:border-b-0">
                  {row.map((cell, index) => (
                    <td key={`${row[0]}-${index}`} className="px-4 py-4 leading-6 text-ink">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="grid gap-10 md:grid-cols-2">
        <div className="flex flex-col gap-4">
          <SectionHeading title="Verified" />
          <ul className="flex flex-col gap-3">
            {verified.map((item) => (
              <li key={item} className="border-l-2 border-sage pl-3 text-sm leading-6 text-ink">
                {item}
              </li>
            ))}
          </ul>
        </div>
        <div className="flex flex-col gap-4">
          <SectionHeading title="Simulated or not done" />
          <ul className="flex flex-col gap-3">
            {notVerified.map((item) => (
              <li key={item} className="border-l-2 border-line pl-3 text-sm leading-6 text-ink">
                {item}
              </li>
            ))}
          </ul>
        </div>
      </section>
    </div>
  )
}

function Fact({ label, children }: { label: string; children: string }) {
  return (
    <div className="grid gap-1 border-b border-line py-4 sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-6">
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="min-w-0 text-ink">{children}</dd>
    </div>
  )
}

function QuoteList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-2xl border border-line bg-card px-5 py-5">
      <h3 className="font-serif text-lg font-medium text-ink">{title}</h3>
      <ul className="mt-3 flex flex-col gap-2">
        {items.map((item) => (
          <li key={item} className="text-sm leading-6 text-ink">
            {item}
          </li>
        ))}
      </ul>
    </div>
  )
}
