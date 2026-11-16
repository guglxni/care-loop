export const API_PROXY_TARGET = "http://127.0.0.1:5055"
export const API_DOWN_MESSAGE = `The CareLoop API is not running. The dev proxy targets ${API_PROXY_TARGET}.`
export const RAVI_ID = "a52a0000-0000-4000-8000-000000000052"
export const RAVI_PATH = "/api/v1/demo/ravi"
export const PATIENT_NAME = "Ravi Sharma"
export const DEMO_CALLS_PATH = "/api/v1/demo/calls"
/** Synthetic chart contact. Never send this as an outbound destination. */
export const STORED_CONTACT = "+15555501052"

const BLOCKED_DESTINATIONS = new Set(["+919840011223", "+14235838428", STORED_CONTACT])
const E164 = /^\+[1-9]\d{1,14}$/
const EXECUTION_KEYS = ["execution_id", "executionId", "bolna_call_id", "bolnaCallId", "run_id", "runId"] as const
const STATUS_KEYS = ["call_status", "callStatus", "status"] as const
const NESTED_KEYS = ["data", "result", "execution", "call"] as const

const QUEUED_STATUSES = new Set(["queued", "scheduled", "pending", "accepted"])
const INITIATED_STATUSES = new Set(["initiated", "in_progress", "ringing", "answered", "ongoing", "started"])
const FAILED_STATUSES = new Set([
  "failed",
  "error",
  "cancelled",
  "canceled",
  "busy",
  "no_answer",
  "unanswered",
  "rejected",
  "balance_low",
])
const COMPLETED_STATUSES = new Set(["completed", "complete"])

export const SCENARIOS = [
  {
    id: "onboarding",
    title: "Onboarding",
    reason: "Enrolled. Ravi is on the CityCare record, so the companion calls to introduce the check-ins.",
    purpose: "onboarding",
  },
  {
    id: "medication",
    title: "Medication follow-up",
    reason: "The evening dose is still unconfirmed.",
    purpose: "medication_check",
  },
  {
    id: "weekly",
    title: "Weekly check-in",
    reason: "A weekly check-in is due.",
    purpose: "glucose_check",
  },
] as const

export type ScenarioId = (typeof SCENARIOS)[number]["id"]
export type CallPhase = "not_started" | "queued" | "initiated" | "completed" | "failed"

export const PHASE_LABEL: Record<CallPhase, string> = {
  not_started: "Not started",
  queued: "Queued",
  initiated: "Initiated",
  completed: "Completed",
  failed: "Failed",
}

export class DemoRequestError extends Error {
  constructor(message: string) {
    super(message)
    this.name = "DemoRequestError"
  }
}

export type ApiResult = {
  status: number
  path: string
  text: string
  json: unknown
}

export type StartedCall = {
  executionId: string
  startStatus: string | null
  phase: Exclude<CallPhase, "not_started" | "completed">
  patientId: string | null
}

export type LaterCallStatus = {
  state: "unavailable" | "unreadable" | "reported"
  status: string | null
  executionId: string | null
  patientId: string | null
  raw: string
}

export type ScenarioBrief = {
  summary: string | null
  lines: string[]
}

export type ParsedVoiceCall = {
  scenario: ScenarioId | null
  executionId: string | null
  patientId: string | null
  summary: string | null
  status: string | null
  duration: string | null
  reported: string | null
  concerns: string | null
  followUps: string | null
  createdAt: string | null
}

export type CareEventRow = {
  id: string
  eventType: string
  scenario: ScenarioId | null
  kind: "scenario" | "follow_up" | "concern" | "other"
  description: string | null
  summary: string | null
  status: string | null
  duration: string | null
  reported: string | null
  concerns: string | null
  followUps: string | null
  createdAt: string | null
}

export type CareEventsLoad =
  | { state: "loading" }
  | { state: "ready"; events: CareEventRow[] }
  | { state: "down" }
  | { state: "error"; message: string }
  | { state: "skipped"; message: string }

export type ScenarioCallResults = {
  summary: string | null
  status: string | null
  duration: string | null
  reported: string | null
  concerns: string | null
  followUps: string | null
  executionId: string | null
  callCompleted: boolean
}

export type LoadedPatient =
  | { state: "down" }
  | { state: "missing"; message: string }
  | { state: "error"; message: string }
  | {
      state: "ravi"
      id: string
      name: string
      age: number | null
      conditions: string | null
      clinic: string | null
      clinician: string | null
      language: string | null
      policy: string | null
      scenarios: Partial<Record<ScenarioId, ScenarioBrief>>
      voiceCalls: ParsedVoiceCall[]
      reportedByScenario: Partial<Record<ScenarioId, string>>
    }

const SCENARIO_KEY_TO_ID: Record<string, ScenarioId> = {
  onboarding: "onboarding",
  medication: "medication",
  medication_followup: "medication",
  medication_check: "medication",
  weekly: "weekly",
  weekly_checkin: "weekly",
  glucose_check: "weekly",
}

const CONDITION_LABEL: Record<string, string> = {
  type_2_diabetes: "Type 2 diabetes",
  hypertension: "Hypertension",
}

export function normalizeDestination(input: string): string {
  return input.trim().replace(/[\s().-]/g, "")
}

export function participantPhoneError(input: string): string | null {
  const destination = normalizeDestination(input)
  if (!destination) {
    return "Enter the participant phone. Use international form, starting with + and the country code."
  }
  if (destination === "+919840011223") {
    return "Do not use +919840011223. That number is on the synthetic chart and is not the participant phone."
  }
  if (destination === STORED_CONTACT) {
    return "Do not use +15555501052. That stored contact is synthetic and is not the outbound destination."
  }
  if (BLOCKED_DESTINATIONS.has(destination)) {
    return "Do not use +1 423 583 8428. That is the companion inbound line, not the participant phone."
  }
  if (!E164.test(destination)) {
    return "Use an E.164 number, starting with + and the country code."
  }
  return null
}

export function normalizeCallStatus(value: string): string {
  return value.trim().toLowerCase().replace(/[\s-]+/g, "_")
}

export function phaseFromStartStatus(status: string | null): Exclude<CallPhase, "not_started" | "completed"> {
  const normalized = status ? normalizeCallStatus(status) : ""
  if (FAILED_STATUSES.has(normalized)) return "failed"
  if (INITIATED_STATUSES.has(normalized)) return "initiated"
  if (COMPLETED_STATUSES.has(normalized)) return "initiated"
  if (!normalized || QUEUED_STATUSES.has(normalized)) return "queued"
  return "initiated"
}

export function phaseFromLaterStatus(current: CallPhase, status: string | null, executionId: string | null): CallPhase {
  if (!executionId) return current
  if (!status) return current
  const normalized = normalizeCallStatus(status)
  if (COMPLETED_STATUSES.has(normalized)) return "completed"
  if (FAILED_STATUSES.has(normalized)) return "failed"
  if (INITIATED_STATUSES.has(normalized)) return "initiated"
  if (QUEUED_STATUSES.has(normalized)) return "queued"
  return current
}

export function ageInYears(dateOfBirth: string, today: string): number | null {
  const birth = /^(\d{4})-(\d{2})-(\d{2})/.exec(dateOfBirth)
  const now = /^(\d{4})-(\d{2})-(\d{2})/.exec(today)
  if (!birth || !now) return null
  const year = Number(birth[1])
  const month = Number(birth[2])
  const day = Number(birth[3])
  const todayYear = Number(now[1])
  const todayMonth = Number(now[2])
  const todayDay = Number(now[3])
  if (month < 1 || month > 12 || day < 1 || day > 31) return null
  let age = todayYear - year
  if (todayMonth < month || (todayMonth === month && todayDay < day)) age -= 1
  if (age < 0 || age > 130) return null
  return age
}

export function purposeForScenario(scenario: ScenarioId): string {
  const match = SCENARIOS.find((item) => item.id === scenario)
  if (!match) return scenario
  return match.purpose
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function isTimeout(error: unknown): boolean {
  return error instanceof DOMException && (error.name === "TimeoutError" || error.name === "AbortError")
}

function isApiDownText(text: string): boolean {
  const normalized = text.toLowerCase()
  return (
    text.includes("The CareLoop API is not running") ||
    normalized.includes("econnrefused") ||
    normalized.includes("http proxy error") ||
    normalized.includes("connect econnrefused")
  )
}

function parseJson(text: string): unknown {
  if (!text.trim()) return null
  try {
    return JSON.parse(text) as unknown
  } catch {
    return null
  }
}

function rawBody(text: string): string {
  const trimmed = text.trim()
  if (!trimmed) return "(empty body)"
  if (trimmed.length > 8000) return `${trimmed.slice(0, 8000)}\n…`
  return trimmed
}

export function formatRawResult(result: ApiResult): string {
  return `HTTP ${result.status} ${result.path}\n${rawBody(result.text)}`
}

function readString(record: Record<string, unknown>, keys: readonly string[]): string | null {
  for (const key of keys) {
    const value = record[key]
    if (typeof value === "string" && value.trim()) return value.trim()
  }
  return null
}

export function readExecutionId(body: unknown): string | null {
  if (!isRecord(body)) return null
  const direct = readString(body, EXECUTION_KEYS)
  if (direct) return direct
  for (const key of NESTED_KEYS) {
    const nested = readExecutionId(body[key])
    if (nested) return nested
  }
  return null
}

export function readCallStatus(body: unknown): string | null {
  if (!isRecord(body)) return null
  const direct = readString(body, STATUS_KEYS)
  if (direct) return direct
  for (const key of NESTED_KEYS) {
    const nested = readCallStatus(body[key])
    if (nested) return nested
  }
  return null
}

function statusForExecution(body: unknown, executionId: string): { status: string | null; executionId: string | null } {
  if (Array.isArray(body)) {
    for (const item of body) {
      const id = readExecutionId(item)
      if (id === executionId) return { status: readCallStatus(item), executionId: id }
    }
    return { status: null, executionId: null }
  }
  if (!isRecord(body)) return { status: null, executionId: null }
  for (const key of ["calls", "items", "results"] as const) {
    if (Array.isArray(body[key])) return statusForExecution(body[key], executionId)
  }
  const id = readExecutionId(body)
  if (id && id !== executionId) return { status: null, executionId: id }
  return { status: readCallStatus(body), executionId: id }
}

async function request(path: string, init: RequestInit): Promise<ApiResult> {
  let response: Response
  try {
    response = await fetch(path, {
      ...init,
      cache: "no-store",
      headers: {
        Accept: "application/json",
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...init.headers,
      },
      signal: init.signal ?? AbortSignal.timeout(25000),
    })
  } catch (error) {
    if (isTimeout(error)) {
      throw new DemoRequestError(
        `The request to ${path} timed out. No execution id was returned, so this page will not mark a call as started or completed.`,
      )
    }
    throw new DemoRequestError(API_DOWN_MESSAGE)
  }

  const text = await response.text()
  if (isApiDownText(text)) throw new DemoRequestError(API_DOWN_MESSAGE)
  return { status: response.status, path, text, json: parseJson(text) }
}

function startedFrom(result: ApiResult): StartedCall {
  const executionId = readExecutionId(result.json)
  if (!executionId) {
    throw new DemoRequestError(
      `The API did not return an execution id, so this page will not treat a call as started.\n${formatRawResult(result)}`,
    )
  }
  const startStatus = readCallStatus(result.json)
  return {
    executionId,
    startStatus,
    phase: phaseFromStartStatus(startStatus),
    patientId: isRecord(result.json) ? readString(result.json, ["patient_id", "patientId"]) : null,
  }
}

export async function startScenarioCall(input: { scenario: ScenarioId; to: string }): Promise<StartedCall> {
  const blocked = participantPhoneError(input.to)
  if (blocked) throw new DemoRequestError(blocked)
  const destination = normalizeDestination(input.to)
  if (destination === STORED_CONTACT) {
    throw new DemoRequestError(
      "Do not use +15555501052. That stored contact is synthetic and is not the outbound destination.",
    )
  }
  const demo = await request(DEMO_CALLS_PATH, {
    method: "POST",
    body: JSON.stringify({
      patient_name: PATIENT_NAME,
      scenario: input.scenario,
      to: destination,
    }),
  })

  if (demo.status < 200 || demo.status >= 300) {
    throw new DemoRequestError(formatRawResult(demo))
  }
  return startedFrom(demo)
}

export async function readScenarioStatus(executionId: string): Promise<LaterCallStatus> {
  const path = `${DEMO_CALLS_PATH}/${encodeURIComponent(executionId)}`
  let result: ApiResult
  try {
    result = await request(path, { method: "GET" })
  } catch (error) {
    if (error instanceof DemoRequestError) {
      return { state: "unreadable", status: null, executionId: null, patientId: null, raw: error.message }
    }
    throw error
  }

  if (result.status === 404) {
    return { state: "unavailable", status: null, executionId: null, patientId: null, raw: formatRawResult(result) }
  }
  if (result.status < 200 || result.status >= 300) {
    return { state: "unreadable", status: null, executionId: null, patientId: null, raw: formatRawResult(result) }
  }

  const match = statusForExecution(result.json, executionId)
  const patientId = isRecord(result.json) ? readString(result.json, ["patient_id", "patientId"]) : null
  if (match.executionId && match.executionId !== executionId) {
    return {
      state: "unreadable",
      status: null,
      executionId: match.executionId,
      patientId,
      raw: `The status response referred to a different execution id.\n${formatRawResult(result)}`,
    }
  }
  return {
    state: "reported",
    status: match.status,
    executionId: match.executionId ?? executionId,
    patientId,
    raw: formatRawResult(result),
  }
}

function joinList(items: string[]): string | null {
  const unique = items.filter((item, index) => item && items.indexOf(item) === index)
  if (unique.length === 0) return null
  if (unique.length === 1) return unique[0]
  if (unique.length === 2) return `${unique[0]} and ${unique[1]}`
  return `${unique.slice(0, -1).join(", ")}, and ${unique[unique.length - 1]}`
}

function readHistoryFacts(body: unknown): { conditions: string | null; clinician: string | null } {
  if (!isRecord(body)) return { conditions: null, clinician: null }
  const conditionRows = Array.isArray(body.conditions) ? body.conditions : []
  const conditions = joinList(
    conditionRows.flatMap((row) => {
      if (!isRecord(row) || typeof row.condition_type !== "string") return []
      return [CONDITION_LABEL[row.condition_type] ?? row.condition_type]
    }),
  )
  const clinicians = conditionRows.flatMap((row) => {
    if (!isRecord(row) || typeof row.treating_clinician !== "string" || !row.treating_clinician.trim()) return []
    return [row.treating_clinician.trim()]
  })
  if (clinicians.length === 0 && Array.isArray(body.care_plan)) {
    for (const row of body.care_plan) {
      if (isRecord(row) && typeof row.clinician === "string" && row.clinician.trim()) {
        clinicians.push(row.clinician.trim())
      }
    }
  }
  return { conditions, clinician: joinList(clinicians) }
}

function labelize(value: string): string {
  const text = value.trim().replace(/_/g, " ")
  if (!text) return ""
  return text.charAt(0).toUpperCase() + text.slice(1)
}

function readText(record: Record<string, unknown>, key: string): string | null {
  const value = record[key]
  if (typeof value !== "string") return null
  const trimmed = value.trim()
  return trimmed || null
}

function scenarioLines(id: ScenarioId, state: Record<string, unknown> | null): string[] {
  if (!state) return []
  if (id === "onboarding") {
    const lines: string[] = []
    const status = readText(state, "onboarding_status")
    if (status) lines.push(`Onboarding: ${labelize(status)}`)
    if (typeof state.consent_recorded === "boolean") {
      lines.push(`Consent recorded: ${state.consent_recorded ? "Yes" : "No"}`)
    }
    const voice = readText(state, "voice_calls")
    if (voice) lines.push(`Voice calls: ${labelize(voice)}`)
    return lines
  }
  if (id === "medication") {
    const lines: string[] = []
    const name = readText(state, "medication_name")
    const dose = readText(state, "prescribed_dosage")
    const time = readText(state, "time_local")
    const medication = [name, dose].filter(Boolean).join(" ")
    if (medication || time) lines.push([medication, time ? `at ${time}` : ""].filter(Boolean).join(" "))
    const adherence = readText(state, "adherence_status")
    if (adherence) lines.push(`Adherence: ${labelize(adherence)}`)
    if (state.presumed_missed === false) lines.push("Not marked missed.")
    if (state.presumed_missed === true) lines.push("Marked missed.")
    return lines
  }
  const days = state.glucose_days_without_reading
  if (!Array.isArray(days)) return []
  const labels = days.filter((day): day is string => typeof day === "string" && day.trim().length > 0)
  if (labels.length === 0) return []
  return [`Glucose days without a reading: ${labels.join(", ")}`]
}

function readScenarios(body: Record<string, unknown>): Partial<Record<ScenarioId, ScenarioBrief>> {
  if (!Array.isArray(body.scenarios)) return {}
  const scenarios: Partial<Record<ScenarioId, ScenarioBrief>> = {}
  for (const row of body.scenarios) {
    if (!isRecord(row) || typeof row.key !== "string") continue
    const id = SCENARIO_KEY_TO_ID[row.key]
    if (!id) continue
    const summary = readText(row, "summary")
    const lines = scenarioLines(id, isRecord(row.state) ? row.state : null)
    if (!summary && lines.length === 0) continue
    scenarios[id] = { summary, lines }
  }
  return scenarios
}

function readRaviChart(body: unknown, today: string): LoadedPatient {
  if (!isRecord(body) || !isRecord(body.profile)) {
    return { state: "missing", message: "GET /api/v1/demo/ravi did not return Ravi Sharma." }
  }
  const profile = body.profile
  const id = readText(profile, "id")
  const name = readText(profile, "preferred_name")?.replace(/\s+/g, " ") ?? ""
  if (id !== RAVI_ID || name.toLowerCase() !== PATIENT_NAME.toLowerCase()) {
    return {
      state: "missing",
      message: "GET /api/v1/demo/ravi did not return Ravi Sharma. This page will not show another patient as Ravi.",
    }
  }
  const facts = readHistoryFacts(profile)
  const dateOfBirth = readText(profile, "date_of_birth") ?? ""
  const reportedAge = profile.age
  const age =
    typeof reportedAge === "number" && Number.isFinite(reportedAge)
      ? reportedAge
      : ageInYears(dateOfBirth, today)
  return {
    state: "ravi",
    id,
    name,
    age,
    conditions: facts.conditions,
    clinic: readText(profile, "clinic"),
    clinician: readText(profile, "doctor") ?? facts.clinician,
    language: readText(profile, "preferred_language"),
    policy: readText(profile, "outbound_contact_policy"),
    scenarios: readScenarios(body),
    voiceCalls: readVoiceCalls(body),
    reportedByScenario: readReportedByScenario(body),
  }
}

export async function loadRaviProfile(today: string): Promise<LoadedPatient> {
  let profile: ApiResult
  try {
    profile = await request(RAVI_PATH, { method: "GET" })
  } catch (error) {
    if (error instanceof DemoRequestError && error.message === API_DOWN_MESSAGE) return { state: "down" }
    const message = error instanceof Error && error.message.trim() ? error.message.trim() : "The profile request failed."
    return { state: "error", message }
  }

  if (isApiDownText(profile.text)) return { state: "down" }
  if (profile.status === 404) {
    return {
      state: "missing",
      message: "GET /api/v1/demo/ravi was not found. This page will not substitute another patient.",
    }
  }
  if (profile.status < 200 || profile.status >= 300) {
    return { state: "error", message: `GET /api/v1/demo/ravi returned HTTP ${profile.status}.` }
  }
  return readRaviChart(profile.json, today)
}

export function careEventsPath(patientId: string): string {
  return `/api/v1/patients/${encodeURIComponent(patientId)}/care-events`
}

export async function loadCareEvents(patientId: string): Promise<CareEventsLoad> {
  const path = careEventsPath(patientId)
  let result: ApiResult
  try {
    result = await request(path, { method: "GET" })
  } catch (error) {
    if (error instanceof DemoRequestError && error.message === API_DOWN_MESSAGE) return { state: "down" }
    const message = error instanceof Error && error.message.trim() ? error.message.trim() : "The care events request failed."
    return { state: "error", message }
  }
  if (isApiDownText(result.text)) return { state: "down" }
  if (result.status < 200 || result.status >= 300) {
    return { state: "error", message: `GET ${path} returned HTTP ${result.status}.` }
  }
  return { state: "ready", events: readCareEvents(result.json, patientId) }
}

export function scenarioCallResults(input: {
  scenario: ScenarioId
  events: readonly CareEventRow[]
  voiceCalls: readonly ParsedVoiceCall[]
  reported: string | null
  executionId: string | null
}): ScenarioCallResults {
  const matched = input.voiceCalls.filter((call) => voiceCallMatches(call, input.scenario, input.executionId))
  const scenarioEvents = input.events.filter((event) => event.kind === "scenario" && event.scenario === input.scenario)
  const latestEvent = newestRow(scenarioEvents)
  const anchored = newestRow(matched.filter((call) => call.executionId))
  const voiceStatus = newestText(matched, (call) => call.status)
  const status = voiceStatus ?? latestEvent?.status ?? null
  const executionId = anchored?.executionId ?? null
  return {
    summary: newestText(matched, (call) => call.summary) ?? latestEvent?.summary ?? null,
    status: status ? labelize(status) : null,
    duration: newestText(matched, (call) => call.duration) ?? latestEvent?.duration ?? null,
    reported: newestText(matched, (call) => call.reported) ?? input.reported ?? latestEvent?.reported ?? null,
    concerns: joinUnique([
      ...matched.map((call) => call.concerns),
      ...concernTexts(input.events, input.scenario),
    ]),
    followUps: joinUnique([
      ...matched.map((call) => call.followUps),
      ...followUpTexts(input.events, input.scenario),
    ]),
    executionId,
    callCompleted: Boolean(
      executionId && anchored?.status && COMPLETED_STATUSES.has(normalizeCallStatus(anchored.status)),
    ),
  }
}

function readVoiceCalls(body: unknown): ParsedVoiceCall[] {
  if (!isRecord(body)) return []
  const calls: ParsedVoiceCall[] = []
  collectVoiceValue(body.voice_calls, null, calls)
  collectVoiceValue(body.calls, null, calls)
  if (Array.isArray(body.scenarios)) {
    for (const scenario of body.scenarios) {
      if (!isRecord(scenario)) continue
      const inherited = scenarioIdFromUnknown(scenario.key)
      collectVoiceValue(scenario.voice_call, inherited, calls)
      collectVoiceValue(scenario.voice_calls, inherited, calls)
      collectVoiceValue(scenario.call, inherited, calls)
      if (!isRecord(scenario.state)) continue
      collectVoiceValue(scenario.state.voice_call, inherited, calls)
      collectVoiceValue(scenario.state.voice_calls, inherited, calls)
      collectVoiceValue(scenario.state.call, inherited, calls)
    }
  }
  return dedupeCalls(calls)
}

function readReportedByScenario(body: Record<string, unknown>): Partial<Record<ScenarioId, string>> {
  const reported: Partial<Record<ScenarioId, string>> = {}
  if (Array.isArray(body.scenarios)) {
    for (const row of body.scenarios) {
      if (!isRecord(row)) continue
      const id = scenarioIdFromUnknown(row.key)
      if (!id || !isRecord(row.state)) continue
      const phrase = reportedFromRecord(row.state)
      if (phrase) reported[id] = phrase
    }
  }
  if (!reported.medication && isRecord(body.schedule) && isRecord(body.schedule.evening_dose)) {
    const phrase = reportedFromRecord(body.schedule.evening_dose)
    if (phrase) reported.medication = phrase
  }
  return reported
}

function readCareEvents(body: unknown, patientId: string): CareEventRow[] {
  const events: CareEventRow[] = []
  careEventList(body).forEach((row, index) => {
    if (!isRecord(row)) return
    const rowPatient = readString(row, ["patient_id", "patientId"])
    if (rowPatient && rowPatient !== patientId) return
    const eventType = readString(row, ["event_type", "eventType"])
    if (!eventType) return
    const classified = classifyEvent(eventType)
    const hinted = scenarioIdFromUnknown(row.scenario) ?? scenarioIdFromUnknown(row.purpose)
    const bits = callBits(row, false)
    events.push({
      id: readString(row, ["id"]) ?? `${eventType}-${index}`,
      eventType,
      scenario: classified.scenario ?? hinted,
      kind: classified.kind,
      description: readString(row, ["event_description", "eventDescription"]),
      summary: bits.summary,
      status: readString(row, ["status"]),
      duration: bits.duration,
      reported: bits.reported,
      concerns: bits.concerns,
      followUps: bits.followUps,
      createdAt: readString(row, ["created_at", "createdAt"]),
    })
  })
  return events
}

function careEventList(body: unknown): unknown[] {
  if (Array.isArray(body)) return body
  if (!isRecord(body)) return []
  if (Array.isArray(body.care_events)) return body.care_events
  if (Array.isArray(body.careEvents)) return body.careEvents
  return []
}

function classifyEvent(eventType: string): { kind: CareEventRow["kind"]; scenario: ScenarioId | null } {
  const key = eventType.trim().toLowerCase().replace(/[\s-]+/g, "_")
  const scenario = SCENARIO_KEY_TO_ID[key] ?? null
  if (scenario) return { kind: "scenario", scenario }
  if (key === "follow_up_task" || key === "follow_up" || key === "followup") return { kind: "follow_up", scenario: null }
  if (
    key === "concern" ||
    key === "concerns" ||
    key === "patient_concern" ||
    key === "clinical_escalation" ||
    key === "escalation"
  ) {
    return { kind: "concern", scenario: null }
  }
  return { kind: "other", scenario: null }
}

function collectVoiceValue(value: unknown, inherited: ScenarioId | null, calls: ParsedVoiceCall[]) {
  if (Array.isArray(value)) {
    for (const item of value) collectVoiceValue(item, inherited, calls)
    return
  }
  if (!isRecord(value)) return
  const parsed = parseVoiceCall(value, inherited)
  if (parsed) calls.push(parsed)
}

function parseVoiceCall(record: Record<string, unknown>, inherited: ScenarioId | null): ParsedVoiceCall | null {
  if (!isVoiceCall(record)) return null
  const extracted = nestedRecord(record, "extracted_data", "extractedData")
  const own = callBits(record, true)
  const extra = extracted ? callBits(extracted, false) : null
  return {
    scenario:
      scenarioIdFromUnknown(record.scenario) ??
      scenarioIdFromUnknown(record.purpose) ??
      (extracted ? scenarioIdFromUnknown(extracted.scenario) ?? scenarioIdFromUnknown(extracted.purpose) : null) ??
      inherited,
    executionId: readExecutionId(record) ?? (extracted ? readExecutionId(extracted) : null),
    patientId:
      readString(record, ["patient_id", "patientId"]) ??
      (extracted ? readString(extracted, ["patient_id", "patientId"]) : null),
    summary: own.summary ?? extra?.summary ?? null,
    status: own.status,
    duration: own.duration ?? extra?.duration ?? null,
    reported: own.reported ?? extra?.reported ?? null,
    concerns: joinUnique([own.concerns, extra?.concerns]),
    followUps: joinUnique([own.followUps, extra?.followUps]),
    createdAt:
      readString(record, ["created_at", "createdAt"]) ??
      (extracted ? readString(extracted, ["created_at", "createdAt"]) : null),
  }
}

function isVoiceCall(record: Record<string, unknown>): boolean {
  if (readString(record, ["bolna_call_id", "bolnaCallId", "execution_id", "executionId"])) return true
  if (readString(record, ["call_status", "callStatus", "call_type", "callType"])) return true
  if (readDuration(record)) return true
  return isRecord(record.extracted_data) || isRecord(record.extractedData)
}

function dedupeCalls(calls: ParsedVoiceCall[]): ParsedVoiceCall[] {
  const seen = new Set<string>()
  const unique: ParsedVoiceCall[] = []
  for (const call of calls) {
    const key = [
      call.executionId ?? "",
      call.scenario ?? "",
      call.createdAt ?? "",
      call.summary ?? "",
      call.status ?? "",
    ].join("|")
    if (seen.has(key)) continue
    seen.add(key)
    unique.push(call)
  }
  return unique
}

function voiceCallMatches(call: ParsedVoiceCall, scenario: ScenarioId, executionId: string | null): boolean {
  if (call.patientId && call.patientId !== RAVI_ID) return false
  if (call.scenario && call.scenario !== scenario) return false
  if (call.scenario === scenario) return true
  return Boolean(executionId && call.executionId === executionId)
}

function concernTexts(events: readonly CareEventRow[], scenario: ScenarioId): Array<string | null> {
  return events
    .filter((event) => event.kind === "concern" && (event.scenario === null || event.scenario === scenario))
    .map((event) => event.concerns ?? event.summary ?? event.description)
    .concat(
      events
        .filter((event) => event.kind === "scenario" && event.scenario === scenario)
        .map((event) => event.concerns),
    )
}

function followUpTexts(events: readonly CareEventRow[], scenario: ScenarioId): Array<string | null> {
  return events
    .filter((event) => event.kind === "follow_up" && (event.scenario === null || event.scenario === scenario))
    .map((event) => event.followUps ?? event.summary ?? event.description)
    .concat(
      events
        .filter((event) => event.kind === "scenario" && event.scenario === scenario)
        .map((event) => event.followUps),
    )
}

function callBits(record: Record<string, unknown>, includeStatus: boolean): {
  summary: string | null
  status: string | null
  duration: string | null
  reported: string | null
  concerns: string | null
  followUps: string | null
} {
  return {
    summary: prose(record.summary),
    status: includeStatus
      ? scalarText(record.call_status) ?? scalarText(record.callStatus) ?? scalarText(record.status)
      : null,
    duration: readDuration(record),
    reported: reportedFromRecord(record),
    concerns: joinUnique([
      prose(record.concerns),
      prose(record.concern),
      prose(record.patient_concern),
      prose(record.patientConcern),
      prose(record.escalation_reason),
      prose(record.escalationReason),
      prose(record.clinical_escalation),
      prose(record.clinicalEscalation),
    ]),
    followUps: joinUnique([
      prose(record.follow_up_tasks),
      prose(record.followUpTasks),
      prose(record.follow_ups),
      prose(record.followUps),
      prose(record.follow_up_task),
      prose(record.followUpTask),
    ]),
  }
}

function reportedFromRecord(record: Record<string, unknown>): string | null {
  const keys = [
    "adherence_status",
    "adherenceStatus",
    "medication_adherence",
    "medicationAdherence",
    "reported_status",
    "reportedStatus",
    "patient_reported",
    "patientReported",
  ] as const
  return joinUnique(keys.map((key) => reportedPhrase(scalarText(record[key]))))
}

function reportedPhrase(value: string | null): string | null {
  if (!value || isSentinel(value)) return null
  const token = value.trim().toLowerCase().replace(/[\s-]+/g, "_")
  if (token === "taken" || token === "patient_reported_taken") return "Patient reported taken"
  if (token === "missed" || token === "patient_reported_missed") return "Patient reported missed"
  return null
}

const DURATION_FIELDS: readonly { keys: readonly string[]; unit: "second" | "minute" | null }[] = [
  { keys: ["duration_seconds", "durationSeconds", "duration_sec"], unit: "second" },
  { keys: ["duration_minutes", "durationMinutes", "duration_min"], unit: "minute" },
  { keys: ["conversation_duration", "conversationDuration", "call_duration", "callDuration", "duration"], unit: null },
]

function readDuration(record: Record<string, unknown>): string | null {
  for (const field of DURATION_FIELDS) {
    for (const key of field.keys) {
      if (!Object.prototype.hasOwnProperty.call(record, key)) continue
      const formatted = formatDuration(record[key], field.unit)
      if (formatted) return formatted
    }
  }
  return null
}

function formatDuration(value: unknown, unit: "second" | "minute" | null): string | null {
  if (typeof value === "string") {
    const trimmed = value.trim()
    if (!trimmed || isSentinel(trimmed)) return null
    return trimmed
  }
  if (typeof value !== "number" || !Number.isFinite(value)) return null
  if (unit === null) return String(value)
  const noun = unit === "second" ? "second" : "minute"
  const amount = String(value)
  return Math.abs(value) === 1 ? `${amount} ${noun}` : `${amount} ${noun}s`
}

function prose(value: unknown): string | null {
  if (typeof value === "string") {
    const trimmed = value.trim()
    if (!trimmed || isSentinel(trimmed)) return null
    return trimmed
  }
  if (Array.isArray(value)) return joinUnique(value.map((item) => prose(item)))
  if (!isRecord(value)) return null
  return joinUnique([
    prose(value.description),
    prose(value.summary),
    prose(value.text),
    prose(value.reason),
    prose(value.task),
    prose(value.title),
    prose(value.event_description),
  ])
}

function scalarText(value: unknown): string | null {
  if (typeof value === "string") {
    const trimmed = value.trim()
    return trimmed || null
  }
  if (typeof value === "number" && Number.isFinite(value)) return String(value)
  if (!isRecord(value)) return null
  return scalarText(value.value) ?? scalarText(value.text) ?? scalarText(value.description)
}

function isSentinel(value: string): boolean {
  const token = value.trim().toLowerCase().replace(/[\s-]+/g, "_").replace(/\//g, "")
  return (
    token === "not_discussed" ||
    token === "na" ||
    token === "none" ||
    token === "null" ||
    token === "unknown" ||
    token === "unclear" ||
    token === "not_specified" ||
    token === "scheduled_unconfirmed" ||
    token === "unconfirmed" ||
    token === "false"
  )
}

function scenarioIdFromUnknown(value: unknown): ScenarioId | null {
  if (typeof value !== "string" || !value.trim()) return null
  const key = value.trim().toLowerCase().replace(/[\s-]+/g, "_")
  return SCENARIO_KEY_TO_ID[key] ?? null
}

function nestedRecord(record: Record<string, unknown>, ...keys: string[]): Record<string, unknown> | null {
  for (const key of keys) {
    const value = record[key]
    if (isRecord(value)) return value
  }
  return null
}

function joinUnique(values: readonly (string | null | undefined)[]): string | null {
  const unique: string[] = []
  for (const value of values) {
    if (!value) continue
    const trimmed = value.trim()
    if (!trimmed || unique.includes(trimmed)) continue
    unique.push(trimmed)
  }
  return unique.length > 0 ? unique.join("; ") : null
}

function compareCreated(left: { createdAt: string | null }, right: { createdAt: string | null }): number {
  const a = left.createdAt ?? ""
  const b = right.createdAt ?? ""
  if (a < b) return -1
  if (a > b) return 1
  return 0
}

function newestRow<T extends { createdAt: string | null }>(rows: readonly T[]): T | null {
  if (rows.length === 0) return null
  return [...rows].sort(compareCreated).at(-1) ?? null
}

function newestText<T extends { createdAt: string | null }>(
  rows: readonly T[],
  pick: (row: T) => string | null,
): string | null {
  const ordered = [...rows].sort(compareCreated)
  for (let index = ordered.length - 1; index >= 0; index -= 1) {
    const value = pick(ordered[index])
    if (value) return value
  }
  return null
}
