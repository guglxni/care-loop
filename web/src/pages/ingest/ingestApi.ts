// Preview rows are local fixtures. Device is applied only when the API sets ingest_origin.

export const API_BASE = "http://127.0.0.1:5000"
export const DEMO_PATIENT_ID = "11111111-1111-4111-8111-111111111111"

export type IngestOrigin = "synthetic" | "manual" | "device"

export type GlucosePoint = {
  measured_at: string
  value: number
  unit: string
  source: string
  ingest_origin: IngestOrigin
  measurement_context?: string | null
}

export type BpPoint = {
  measured_at: string
  systolic: number
  diastolic: number
  unit: string
  source: string
  ingest_origin: IngestOrigin
}

export type IngestStatus = {
  status?: string
  finished_at?: string
  connector?: string
  inserted_count?: number
  duplicate_count?: number
}

export type IngestSnapshot = {
  glucose: GlucosePoint[]
  bloodPressure: BpPoint[]
  status: IngestStatus | null
  statusUnavailable: boolean
  usingFixture: boolean
}

export class IngestRequestError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = "IngestRequestError"
    this.status = status
  }
}

type PreviewOrigin = Exclude<IngestOrigin, "device">

type PreviewGlucose = Omit<GlucosePoint, "ingest_origin"> & { ingest_origin: PreviewOrigin }
type PreviewBp = Omit<BpPoint, "ingest_origin"> & { ingest_origin: PreviewOrigin }

const FIXTURE_GLUCOSE: PreviewGlucose[] = [
  {
    measured_at: "2026-11-12T07:10:00+05:30",
    value: 118,
    unit: "mg/dL",
    source: "synthetic_chart",
    ingest_origin: "synthetic",
    measurement_context: "fasting",
  },
  {
    measured_at: "2026-11-13T07:16:00+05:30",
    value: 131,
    unit: "mg/dL",
    source: "synthetic_chart",
    ingest_origin: "synthetic",
    measurement_context: "fasting",
  },
  {
    measured_at: "2026-11-13T13:40:00+05:30",
    value: 154,
    unit: "mg/dL",
    source: "manual",
    ingest_origin: "manual",
    measurement_context: "post_meal",
  },
  {
    measured_at: "2026-11-15T07:20:00+05:30",
    value: 125,
    unit: "mg/dL",
    source: "manual",
    ingest_origin: "manual",
    measurement_context: "fasting",
  },
]

const FIXTURE_BP: PreviewBp[] = [
  {
    measured_at: "2026-11-12T08:05:00+05:30",
    systolic: 128,
    diastolic: 82,
    unit: "mmHg",
    source: "synthetic_chart",
    ingest_origin: "synthetic",
  },
  {
    measured_at: "2026-11-15T08:10:00+05:30",
    systolic: 126,
    diastolic: 80,
    unit: "mmHg",
    source: "manual",
    ingest_origin: "manual",
  },
]

const ORIGINS = new Set<IngestOrigin>(["synthetic", "manual", "device"])
const TIME_ZONE = "Asia/Kolkata"

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function finiteNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) return parsed
  }
  return null
}

export function ingestOriginFrom(record: { source?: unknown; ingest_origin?: unknown }): IngestOrigin {
  if (typeof record.ingest_origin === "string") {
    const raw = record.ingest_origin.trim().toLowerCase()
    if (raw === "synthetic" || raw === "manual" || raw === "device") return raw
  }
  if (typeof record.source === "string" && record.source.trim().toLowerCase() === "manual") return "manual"
  return "synthetic"
}

function explicitOrigin(value: unknown): IngestOrigin | null {
  if (typeof value !== "string") return null
  const raw = value.trim().toLowerCase()
  if (ORIGINS.has(raw as IngestOrigin)) return raw as IngestOrigin
  return null
}

type RawReading = {
  measurement_type: string
  measured_at: string
  value: number
  unit: string
  source: string
  ingest_origin: unknown
  measurement_context: string | null
}

function parseReading(value: unknown): RawReading | null {
  if (!isRecord(value)) return null
  const measurementType = value.measurement_type
  const measuredAt = value.measured_at
  const unit = value.unit
  const numeric = finiteNumber(value.value)
  if (typeof measurementType !== "string" || typeof measuredAt !== "string" || typeof unit !== "string") {
    return null
  }
  if (numeric === null || unit.trim() === "" || measuredAt.trim() === "") return null
  const source = typeof value.source === "string" && value.source.trim() ? value.source.trim() : "unspecified"
  const context = typeof value.measurement_context === "string" ? value.measurement_context : null
  return {
    measurement_type: measurementType,
    measured_at: measuredAt,
    value: numeric,
    unit,
    source,
    ingest_origin: value.ingest_origin,
    measurement_context: context,
  }
}

export function glucoseFromHistory(readings: readonly unknown[]): GlucosePoint[] {
  const points: GlucosePoint[] = []
  for (const item of readings) {
    const row = parseReading(item)
    if (!row || row.measurement_type !== "blood_glucose") continue
    const point: GlucosePoint = {
      measured_at: row.measured_at,
      value: row.value,
      unit: row.unit,
      source: row.source,
      ingest_origin: ingestOriginFrom(row),
    }
    if (row.measurement_context) point.measurement_context = row.measurement_context
    points.push(point)
  }
  return points
}

export function bpFromHistory(readings: readonly unknown[]): BpPoint[] {
  const systolic = new Map<string, RawReading>()
  const diastolic = new Map<string, RawReading>()
  for (const item of readings) {
    const row = parseReading(item)
    if (!row) continue
    if (row.measurement_type === "systolic_blood_pressure") systolic.set(row.measured_at, row)
    if (row.measurement_type === "diastolic_blood_pressure") diastolic.set(row.measured_at, row)
  }
  const points: BpPoint[] = []
  for (const [measuredAt, sys] of systolic) {
    const dia = diastolic.get(measuredAt)
    if (!dia) continue
    const sysOrigin = explicitOrigin(sys.ingest_origin)
    const diaOrigin = explicitOrigin(dia.ingest_origin)
    const ingestOrigin = sysOrigin ?? diaOrigin ?? ingestOriginFrom(sys)
    points.push({
      measured_at: measuredAt,
      systolic: sys.value,
      diastolic: dia.value,
      unit: sys.unit || dia.unit,
      source: sys.source,
      ingest_origin: ingestOrigin,
    })
  }
  return points
}

export function parseIngestStatus(body: unknown): IngestStatus {
  if (!isRecord(body)) return {}
  const status: IngestStatus = {}
  if (typeof body.status === "string" && body.status.trim()) status.status = body.status.trim()
  if (typeof body.finished_at === "string" && body.finished_at.trim()) status.finished_at = body.finished_at.trim()
  if (typeof body.connector === "string" && body.connector.trim()) status.connector = body.connector.trim()
  const inserted = finiteNumber(body.inserted_count)
  const duplicates = finiteNumber(body.duplicate_count)
  if (inserted !== null) status.inserted_count = inserted
  if (duplicates !== null) status.duplicate_count = duplicates
  return status
}

function calendarDay(iso: string): string | null {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return null
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date)
  const year = parts.find((part) => part.type === "year")?.value
  const month = parts.find((part) => part.type === "month")?.value
  const day = parts.find((part) => part.type === "day")?.value
  if (!year || !month || !day) return null
  return `${year}-${month}-${day}`
}

function nextIsoDate(iso: string): string {
  const [year, month, day] = iso.split("-").map(Number)
  const date = new Date(Date.UTC(year, month - 1, day))
  date.setUTCDate(date.getUTCDate() + 1)
  return date.toISOString().slice(0, 10)
}

/** True when the visible span includes a Kolkata calendar day with no fasting glucose point. */
export function rangeMissesFastingGlucose(points: readonly GlucosePoint[]): boolean {
  const dated = points
    .map((point) => ({
      day: calendarDay(point.measured_at),
      fasting: point.measurement_context === "fasting",
    }))
    .filter((row): row is { day: string; fasting: boolean } => row.day !== null)
  if (!dated.some((row) => row.fasting)) return false
  const fastingDays = new Set(dated.filter((row) => row.fasting).map((row) => row.day))
  const days = dated.map((row) => row.day).sort()
  const start = days[0]
  const end = days[days.length - 1]
  if (!start || !end) return false
  let cursor = start
  for (let guard = 0; cursor <= end && guard < 4000; guard += 1) {
    if (!fastingDays.has(cursor)) return true
    const next = nextIsoDate(cursor)
    if (next <= cursor) return false
    cursor = next
  }
  return false
}

function assertPreview(rows: readonly { ingest_origin: IngestOrigin }[]) {
  if (rows.some((row) => row.ingest_origin === "device")) {
    throw new Error("Fixture rows must not be labeled device.")
  }
}

assertPreview(FIXTURE_GLUCOSE)
assertPreview(FIXTURE_BP)
if (!rangeMissesFastingGlucose(FIXTURE_GLUCOSE)) {
  throw new Error("Fixture preview must include a day with no fasting glucose.")
}

export function fixtureSnapshot(): IngestSnapshot {
  return {
    glucose: FIXTURE_GLUCOSE,
    bloodPressure: FIXTURE_BP,
    status: null,
    statusUnavailable: true,
    usingFixture: true,
  }
}

function patientUrl(patientId: string, suffix: string): string {
  return `${API_BASE}/api/v1/patients/${patientId}${suffix}`
}

function request(url: string, init?: RequestInit): Promise<Response> {
  const signal = typeof AbortSignal !== "undefined" && "timeout" in AbortSignal ? AbortSignal.timeout(8000) : undefined
  return fetch(url, { ...init, signal })
}

async function readError(response: Response): Promise<IngestRequestError> {
  let message = response.statusText.trim() || "Request failed"
  try {
    const body: unknown = await response.json()
    if (isRecord(body) && isRecord(body.error) && typeof body.error.message === "string") {
      const text = body.error.message.trim()
      if (text) message = text
    }
  } catch {
    // The body was not JSON.
  }
  return new IngestRequestError(message, response.status)
}

export async function fetchIngestStatus(patientId: string): Promise<IngestStatus> {
  const response = await request(patientUrl(patientId, "/ingest/status"), {
    headers: { Accept: "application/json" },
  })
  if (!response.ok) throw await readError(response)
  let body: unknown
  try {
    body = await response.json()
  } catch {
    throw new IngestRequestError("Status response was not JSON.", response.status)
  }
  return parseIngestStatus(body)
}

async function fetchHistorySeries(patientId: string): Promise<{ glucose: GlucosePoint[]; bloodPressure: BpPoint[] }> {
  const response = await request(patientUrl(patientId, "/history"), {
    headers: { Accept: "application/json" },
  })
  if (!response.ok) throw await readError(response)
  let body: unknown
  try {
    body = await response.json()
  } catch {
    throw new IngestRequestError("History response was not JSON.", response.status)
  }
  if (!isRecord(body) || !Array.isArray(body.recent_readings)) {
    throw new IngestRequestError("History response did not include recent_readings.", response.status)
  }
  return {
    glucose: glucoseFromHistory(body.recent_readings),
    bloodPressure: bpFromHistory(body.recent_readings),
  }
}

export async function loadIngestSnapshot(patientId: string): Promise<IngestSnapshot> {
  const [statusResult, historyResult] = await Promise.allSettled([
    fetchIngestStatus(patientId),
    fetchHistorySeries(patientId),
  ])
  const status = statusResult.status === "fulfilled" ? statusResult.value : null
  const statusUnavailable = statusResult.status !== "fulfilled"
  if (historyResult.status === "fulfilled") {
    return {
      glucose: historyResult.value.glucose,
      bloodPressure: historyResult.value.bloodPressure,
      status,
      statusUnavailable,
      usingFixture: false,
    }
  }
  return {
    ...fixtureSnapshot(),
    status,
    statusUnavailable,
  }
}

export async function postNightscoutMock(patientId: string): Promise<void> {
  const response = await request(patientUrl(patientId, "/ingest/nightscout/mock"), {
    method: "POST",
    headers: { Accept: "application/json" },
  })
  if (!response.ok) throw await readError(response)
}
