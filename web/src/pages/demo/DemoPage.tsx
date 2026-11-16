import { useEffect, useId, useRef, useState } from "react"
import { Badge, type BadgeTone } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input, Label } from "@/components/ui/field"
import { KnowledgeCard } from "@/components/knowledge/KnowledgeCard"
import { PageHeader } from "@/components/layout/PageHeader"
import { SectionHeading } from "@/components/layout/SectionHeading"
import { DEMO_TODAY, languageOptions } from "@/data/demo"
import {
  EXPECTED_LINK_LABEL,
  RAVI_CALL_RECOGNITION,
  RAVI_RECOGNIZED_PHONE_DISPLAY,
  demoPhoneRecognition,
  loadPhoneLinks,
  raviRecognizedLinkPending,
  type PhoneLinksLoad,
} from "@/lib/phoneLinks"
import {
  API_DOWN_MESSAGE,
  PATIENT_NAME,
  PHASE_LABEL,
  RAVI_ID,
  RAVI_PATH,
  SCENARIOS,
  careEventsPath,
  loadCareEvents,
  loadRaviProfile,
  participantPhoneError,
  phaseFromLaterStatus,
  purposeForScenario,
  readScenarioStatus,
  scenarioCallResults,
  startScenarioCall,
  type CallPhase,
  type CareEventsLoad,
  type LoadedPatient,
  type ScenarioBrief,
  type ScenarioCallResults,
  type ScenarioId,
} from "@/pages/demo/demoApi"

type ScenarioState = {
  phase: CallPhase
  executionId: string | null
  startStatus: string | null
  laterStatus: string | null
  error: string | null
  note: string | null
  pending: "start" | "status" | null
}

const INITIAL_SCENARIO: ScenarioState = {
  phase: "not_started",
  executionId: null,
  startStatus: null,
  laterStatus: null,
  error: null,
  note: null,
  pending: null,
}

type PatientCard = {
  source: string
  detail: string
  name: string
  id: string
  age: string
  conditions: string
  clinic: string
  clinician: string
  language: string
}

const UNLOADED = "Not loaded"
const NOT_IN_CHART = "Not in the chart yet"

function phaseTone(phase: CallPhase): BadgeTone {
  if (phase === "completed") return "green"
  if (phase === "initiated") return "blue"
  if (phase === "queued" || phase === "failed") return "amber"
  return "neutral"
}

function languageLabel(tag: string): string {
  const match = languageOptions.find((option) => option.code === tag)
  return match?.label ?? tag
}

function blankPatient(detail: string): PatientCard {
  return {
    source: "CareLoop API",
    detail,
    name: PATIENT_NAME,
    id: UNLOADED,
    age: UNLOADED,
    conditions: UNLOADED,
    clinic: UNLOADED,
    clinician: UNLOADED,
    language: UNLOADED,
  }
}

function shown(value: string | null): string {
  return value && value.trim() ? value : "Not on the API profile"
}

function patientFromApi(loaded: Extract<LoadedPatient, { state: "ravi" }>): PatientCard {
  const policy = loaded.policy
    ? `Loaded from GET ${RAVI_PATH}. ${loaded.policy}`
    : `Loaded from GET ${RAVI_PATH}. The stored contact on this chart is not the outbound destination.`
  return {
    source: "CareLoop API",
    detail: policy,
    name: loaded.name,
    id: loaded.id,
    age: loaded.age === null ? "Not on the API profile" : String(loaded.age),
    conditions: shown(loaded.conditions),
    clinic: shown(loaded.clinic),
    clinician: shown(loaded.clinician),
    language: loaded.language ? languageLabel(loaded.language) : "Not on the API profile",
  }
}

function patientWhileWaiting(loaded: LoadedPatient | null, checking: boolean): PatientCard {
  if (checking || !loaded) return blankPatient(`Loading Ravi Sharma from GET ${RAVI_PATH}.`)
  if (loaded.state === "ravi") return patientFromApi(loaded)
  if (loaded.state === "down") return blankPatient(API_DOWN_MESSAGE)
  return blankPatient(loaded.message)
}

function scenarioView(
  scenario: (typeof SCENARIOS)[number],
  loaded: LoadedPatient | null,
  checking: boolean,
): { reason: string; lines: string[] } {
  if (checking || !loaded) return { reason: `Loading this scenario from GET ${RAVI_PATH}.`, lines: [] }
  if (loaded.state === "down") return { reason: API_DOWN_MESSAGE, lines: [] }
  if (loaded.state !== "ravi") return { reason: loaded.message, lines: [] }
  const brief: ScenarioBrief | undefined = loaded.scenarios[scenario.id]
  if (brief && (brief.summary || brief.lines.length > 0)) {
    return { reason: brief.summary ?? scenario.reason, lines: brief.lines }
  }
  return { reason: scenario.reason, lines: [] }
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1 border-b border-line py-3 sm:grid-cols-[11rem_minmax(0,1fr)] sm:items-baseline sm:gap-6">
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="min-w-0 text-ink">{value}</dd>
    </div>
  )
}

function RecognizedPhoneField({ load }: { load: PhoneLinksLoad | null }) {
  const pending = load !== null && raviRecognizedLinkPending(load)
  return (
    <div className="grid gap-1 border-b border-line py-3 sm:grid-cols-[11rem_minmax(0,1fr)] sm:items-baseline sm:gap-6">
      <dt className="text-sm text-muted">Linked phone</dt>
      <dd className="min-w-0 text-ink">
        <p className="font-medium">{RAVI_RECOGNIZED_PHONE_DISPLAY}</p>
        <p className="mt-1 text-sm leading-6">{RAVI_CALL_RECOGNITION}</p>
        {pending ? (
          <p className="mt-2">
            <Badge tone="amber">{EXPECTED_LINK_LABEL}</Badge>
          </p>
        ) : null}
        {load?.state === "failed" ? (
          <p role="alert" className="mt-2 text-sm leading-6 text-amber">
            {load.message}
          </p>
        ) : null}
        {load?.state === "unavailable" ? (
          <p role="status" className="mt-2 text-sm leading-6 text-muted">
            {load.message}
          </p>
        ) : null}
      </dd>
    </div>
  )
}

function ResultField({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1 border-b border-line py-3 sm:grid-cols-[18rem_minmax(0,1fr)] sm:items-baseline sm:gap-6">
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="min-w-0 text-ink">{value}</dd>
    </div>
  )
}

function visiblePhase(state: ScenarioState, results: ScenarioCallResults): CallPhase {
  if (state.executionId) return state.phase
  if (results.executionId && results.callCompleted) return "completed"
  return state.phase === "completed" ? "initiated" : state.phase
}

function resultText(value: string | null, pending: boolean): string {
  if (pending) return "Loading the chart."
  return value && value.trim() ? value : NOT_IN_CHART
}

function resultsNote(patient: LoadedPatient | null, events: CareEventsLoad): string {
  if (!patient || events.state === "loading") return "Loading care events."
  if (patient.state === "down" || events.state === "down") return API_DOWN_MESSAGE
  if (patient.state === "missing" || patient.state === "error") return patient.message
  if (events.state === "error") return events.message
  if (events.state === "skipped") return events.message
  return `Read from GET ${careEventsPath(patient.id)}. Voice call fields are included when GET ${RAVI_PATH} has them.`
}

export function DemoPage() {
  const phoneId = useId()
  const phoneErrorId = useId()
  const [phone, setPhone] = useState("")
  const [phoneError, setPhoneError] = useState<string | null>(null)
  const [recognizedLinks, setRecognizedLinks] = useState<PhoneLinksLoad | null>(null)
  const [checkingProfile, setCheckingProfile] = useState(true)
  const [loadedPatient, setLoadedPatient] = useState<LoadedPatient | null>(null)
  const [careEvents, setCareEvents] = useState<CareEventsLoad>({ state: "loading" })
  const [scenarios, setScenarios] = useState<Record<ScenarioId, ScenarioState>>({
    onboarding: INITIAL_SCENARIO,
    medication: INITIAL_SCENARIO,
    weekly: INITIAL_SCENARIO,
  })
  const generation = useRef<Record<ScenarioId, number>>({ onboarding: 0, medication: 0, weekly: 0 })

  useEffect(() => {
    let cancelled = false
    loadPhoneLinks(RAVI_ID)
      .then((result) => {
        if (!cancelled) setRecognizedLinks(result)
      })
      .catch((error: unknown) => {
        if (cancelled) return
        const message = error instanceof Error && error.message.trim() ? error.message.trim() : "The phone links request failed."
        setRecognizedLinks({ state: "failed", message })
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    loadRaviProfile(DEMO_TODAY)
      .then(async (loaded) => {
        if (cancelled) return
        setLoadedPatient(loaded)
        if (loaded.state !== "ravi") {
          setCareEvents(
            loaded.state === "down" ? { state: "down" } : { state: "skipped", message: loaded.message },
          )
          return
        }
        const events = await loadCareEvents(loaded.id)
        if (!cancelled) setCareEvents(events)
      })
      .catch((error: unknown) => {
        if (cancelled) return
        const message = error instanceof Error && error.message.trim() ? error.message.trim() : "The profile request failed."
        if (message === API_DOWN_MESSAGE) {
          setLoadedPatient({ state: "down" })
          setCareEvents({ state: "down" })
          return
        }
        setLoadedPatient({ state: "error", message })
        setCareEvents({ state: "skipped", message })
      })
      .finally(() => {
        if (!cancelled) setCheckingProfile(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function reloadChart() {
    const loaded = await loadRaviProfile(DEMO_TODAY)
    setLoadedPatient((current) => (loaded.state === "ravi" || current?.state !== "ravi" ? loaded : current))
    if (loaded.state !== "ravi") return
    const events = await loadCareEvents(loaded.id)
    setCareEvents((current) => (events.state === "error" && current.state === "ready" ? current : events))
  }

  function patchScenario(id: ScenarioId, recipe: (current: ScenarioState) => ScenarioState) {
    setScenarios((current) => ({ ...current, [id]: recipe(current[id]) }))
  }

  async function checkStatus(id: ScenarioId, executionId: string) {
    const seq = generation.current[id] + 1
    generation.current[id] = seq
    patchScenario(id, (current) => ({ ...current, pending: "status", error: null }))
    try {
      const later = await readScenarioStatus(executionId)
      if (generation.current[id] !== seq) return
      patchScenario(id, (current) => {
        if (current.executionId && current.executionId !== executionId) return { ...current, pending: null }
        if (later.state === "unavailable") {
          return {
            ...current,
            pending: null,
            laterStatus: null,
            note: `A later status request did not find this execution, so this page will not mark the call completed.\n${later.raw}`,
          }
        }
        if (later.state === "unreadable") {
          return {
            ...current,
            pending: null,
            note: `The later status response could not be applied. The call is not marked completed.\n${later.raw}`,
          }
        }
        if (later.patientId && later.patientId !== RAVI_ID) {
          return {
            ...current,
            pending: null,
            laterStatus: later.status,
            error: null,
            note: "This execution is on another chart, so Ravi's scenario is not marked completed.",
          }
        }
        const phase = phaseFromLaterStatus(current.phase, later.status, current.executionId ?? executionId)
        const known = phaseFromLaterStatus("not_started", later.status, executionId)
        const understood = known === "queued" || known === "initiated" || known === "failed" || known === "completed"
        return {
          ...current,
          pending: null,
          executionId: current.executionId ?? executionId,
          phase,
          laterStatus: later.status,
          error: null,
          note:
            phase === "completed" || (later.status && understood)
              ? null
              : later.status
                ? `The later status response said "${later.status}". This page will not mark the call completed.\n${later.raw}`
                : `The later status response did not say the call completed.\n${later.raw}`,
        }
      })
      void reloadChart()
    } catch (error) {
      if (generation.current[id] !== seq) return
      const message = error instanceof Error && error.message.trim() ? error.message.trim() : "The status request failed."
      patchScenario(id, (current) => ({
        ...current,
        pending: null,
        note: message,
      }))
    }
  }

  async function onStart(id: ScenarioId) {
    const problem = participantPhoneError(phone)
    if (problem) {
      setPhoneError(problem)
      return
    }
    setPhoneError(null)
    const seq = generation.current[id] + 1
    generation.current[id] = seq
    patchScenario(id, (current) => ({ ...current, pending: "start", error: null, note: null }))
    try {
      const started = await startScenarioCall({ scenario: id, to: phone })
      if (generation.current[id] !== seq) return
      patchScenario(id, (current) => ({
        ...current,
        phase: started.phase,
        executionId: started.executionId,
        startStatus: started.startStatus,
        laterStatus: null,
        error: started.phase === "failed" ? current.error : null,
        pending: "status",
        note:
          started.patientId && started.patientId !== RAVI_ID
            ? "This call is not on Ravi Sharma's chart. The scenario is not marked completed from it."
            : started.startStatus && started.phase !== "failed"
              ? "The start response is not treated as completed. Waiting for a later status response."
              : null,
      }))
      await checkStatus(id, started.executionId)
    } catch (error) {
      if (generation.current[id] !== seq) return
      const message = error instanceof Error && error.message.trim() ? error.message.trim() : "The call request failed."
      patchScenario(id, (current) => ({
        ...current,
        pending: null,
        error: message,
        phase: current.executionId ? current.phase : "failed",
      }))
    }
  }

  const patient = patientWhileWaiting(loadedPatient, checkingProfile)
  const registeredPhone = demoPhoneRecognition(phone)

  return (
    <div className="flex w-full min-w-0 flex-col gap-12 text-ink">
      <PageHeader
        title="Demo"
        lede="For the clinic operator. Start a scripted scenario for Ravi Sharma. The patient does not use this page and does not start the call."
        note="Demo data. Not medical advice."
      />

      <section className="flex flex-col gap-3" aria-labelledby="scripted-patient-heading">
        <SectionHeading
          id="scripted-patient-heading"
          title="Scripted patient"
          lede="The voice agent calls because the care record says a check-in is due."
        />
        <Card>
          <CardHeader>
            <CardTitle>{patient.name}</CardTitle>
            <CardDescription>{patient.source}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <dl className="border-t border-line">
              <Field label="Patient id" value={patient.id} />
              <Field label="Age" value={patient.age} />
              <Field label="Conditions" value={patient.conditions} />
              <Field label="Clinic" value={patient.clinic} />
              <Field label="Clinician" value={patient.clinician} />
              <Field label="Language" value={patient.language} />
              <RecognizedPhoneField load={recognizedLinks} />
            </dl>
            <p className="text-sm leading-6 text-muted">{patient.detail}</p>
          </CardContent>
        </Card>
      </section>

      <KnowledgeCard patientId={RAVI_ID} />

      <section className="flex flex-col gap-4" aria-labelledby="scenarios-heading">
        <SectionHeading
          id="scenarios-heading"
          title="Scenarios"
          lede="Start Call sends one request. It does not mark the scenario completed. Completed appears only when that request returns an execution id and a later status response says the call completed."
        />
        <div className="flex max-w-xl flex-col gap-2">
          <Label htmlFor={phoneId}>Participant phone</Label>
          <Input
            id={phoneId}
            name="participant-phone"
            type="tel"
            inputMode="tel"
            autoComplete="off"
            spellCheck={false}
            value={phone}
            aria-invalid={phoneError ? true : undefined}
            aria-describedby={phoneErrorId}
            onChange={(event) => {
              setPhone(event.target.value)
              setPhoneError(null)
            }}
          />
          <p id={phoneErrorId} className={phoneError ? "text-sm leading-6 text-amber" : "text-sm leading-6 text-muted"} role={phoneError ? "alert" : undefined}>
            {phoneError ??
              "The consenting person who will receive this test call. Leave this empty until you enter their number in E.164. The stored contact on this chart is not the outbound destination."}
          </p>
          {registeredPhone ? <p className="text-sm leading-6 text-ink">{registeredPhone}</p> : null}
        </div>

        <ul className="flex flex-col gap-3">
          {SCENARIOS.map((scenario) => {
            const state = scenarios[scenario.id]
            const view = scenarioView(scenario, loadedPatient, checkingProfile)
            const results = scenarioCallResults({
              scenario: scenario.id,
              events: careEvents.state === "ready" ? careEvents.events : [],
              voiceCalls: loadedPatient?.state === "ravi" ? loadedPatient.voiceCalls : [],
              reported: loadedPatient?.state === "ravi" ? (loadedPatient.reportedByScenario[scenario.id] ?? null) : null,
              executionId: state.executionId,
            })
            const phase = visiblePhase(state, results)
            const executionId = state.executionId ?? results.executionId
            const resultsPending = checkingProfile || careEvents.state === "loading"
            const errorId = `${scenario.id}-error`
            const resultsId = `${scenario.id}-results`
            return (
              <li key={scenario.id}>
                <Card>
                  <CardHeader>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <CardTitle>{scenario.title}</CardTitle>
                        <CardDescription>{view.reason}</CardDescription>
                      </div>
                      <Badge tone={phaseTone(phase)}>{PHASE_LABEL[phase]}</Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-4" aria-live="polite">
                    {view.lines.length > 0 ? (
                      <ul className="flex flex-col gap-1">
                        {view.lines.map((line) => (
                          <li key={line} className="text-sm leading-6 text-ink">
                            {line}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                    <p className="text-sm leading-6 text-muted">
                      Purpose {purposeForScenario(scenario.id)}. Start Call does not mark this completed.
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        type="button"
                        onClick={() => void onStart(scenario.id)}
                        disabled={state.pending !== null}
                        aria-busy={state.pending === "start"}
                        aria-label={`Start Call for ${scenario.title}`}
                      >
                        {state.pending === "start" ? "Sending request" : "Start Call"}
                      </Button>
                      {executionId ? (
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => void checkStatus(scenario.id, executionId)}
                          disabled={state.pending !== null}
                          aria-busy={state.pending === "status"}
                          aria-label={`Check status for ${scenario.title}`}
                        >
                          {state.pending === "status" ? "Checking status" : "Check status"}
                        </Button>
                      ) : null}
                    </div>
                    <p className="text-sm leading-6 text-ink">
                      {executionId ? (
                        <>
                          Execution id: <span className="font-medium break-all">{executionId}</span>
                        </>
                      ) : (
                        <span className="text-muted">No execution id.</span>
                      )}
                    </p>
                    {state.startStatus ? (
                      <p className="text-sm leading-6 text-muted">Start response status: {state.startStatus}</p>
                    ) : null}
                    {state.laterStatus ? (
                      <p className="text-sm leading-6 text-muted">Later status response: {state.laterStatus}</p>
                    ) : null}
                    {state.note ? (
                      <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words font-sans text-sm leading-6 text-muted">
                        {state.note}
                      </pre>
                    ) : null}
                    {state.error ? (
                      <pre
                        id={errorId}
                        role="alert"
                        className="max-h-80 overflow-auto whitespace-pre-wrap break-words font-sans text-sm leading-6 text-amber"
                      >
                        {state.error}
                      </pre>
                    ) : null}
                    <div className="flex flex-col gap-3 border-t border-line pt-4" aria-labelledby={resultsId}>
                      <h3 id={resultsId} className="text-base font-medium leading-snug text-ink">
                        Call results
                      </h3>
                      <p className="text-sm leading-6 text-muted">{resultsNote(loadedPatient, careEvents)}</p>
                      <dl className="border-t border-line">
                        <ResultField label="Summary" value={resultText(results.summary, resultsPending)} />
                        <ResultField label="Status" value={resultText(results.status, resultsPending)} />
                        <ResultField label="Duration" value={resultText(results.duration, resultsPending)} />
                        <ResultField label="Patient-reported missed or taken" value={resultText(results.reported, resultsPending)} />
                        <ResultField label="Concerns" value={resultText(results.concerns, resultsPending)} />
                        <ResultField label="Follow-up tasks" value={resultText(results.followUps, resultsPending)} />
                      </dl>
                    </div>
                  </CardContent>
                </Card>
              </li>
            )
          })}
        </ul>
      </section>
    </div>
  )
}
