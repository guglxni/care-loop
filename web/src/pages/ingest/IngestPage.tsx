import { useEffect, useMemo, useState } from "react"
import {
  CartesianGrid,
  Label,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipProps,
} from "recharts"
import { Badge, type BadgeTone } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { EmptyState } from "@/components/layout/EmptyState"
import { PageHeader } from "@/components/layout/PageHeader"
import { SectionHeading } from "@/components/layout/SectionHeading"
import {
  DEMO_PATIENT_ID,
  IngestRequestError,
  fixtureSnapshot,
  loadIngestSnapshot,
  postNightscoutMock,
  rangeMissesFastingGlucose,
  type BpPoint,
  type GlucosePoint,
  type IngestOrigin,
  type IngestSnapshot,
  type IngestStatus,
} from "./ingestApi"

const CAPTION =
  "Synthetic and device-reported rows are labeled separately. Forecasts and uploads are not live sensor connections."

const TIME_ZONE = "Asia/Kolkata"
const LOCALE = "en-IN"

const ORIGINS: { origin: IngestOrigin; label: string; tone: BadgeTone; stroke: string; border: string }[] = [
  { origin: "synthetic", label: "Synthetic", tone: "green", stroke: "var(--color-sage, #2f5d45)", border: "var(--color-sage)" },
  { origin: "manual", label: "Manual", tone: "amber", stroke: "var(--color-amber, #7a4e0d)", border: "var(--color-amber)" },
  { origin: "device", label: "Device", tone: "blue", stroke: "var(--color-calm, #3d5f78)", border: "var(--color-calm)" },
]

type GlucoseRow = {
  measuredAt: number
  unit: string
  synthetic: number | null
  manual: number | null
  device: number | null
}

type PressureRow = {
  measuredAt: number
  systolic: number
  diastolic: number
  unit: string
  origin: string
}

function formatWhen(value: string | number): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return new Intl.DateTimeFormat(LOCALE, {
    timeZone: TIME_ZONE,
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date)
}

function formatAxisTime(value: number): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ""
  return new Intl.DateTimeFormat(LOCALE, {
    timeZone: TIME_ZONE,
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  }).format(date)
}

function contextLabel(value: string | null | undefined): string {
  if (value === "fasting") return "Fasting"
  if (value === "post_meal") return "Post-meal"
  if (value === "other") return "Other"
  if (value === "resting") return "Resting"
  if (value) return value
  return "Not specified"
}

function originLabel(origin: string): string {
  return ORIGINS.find((item) => item.origin === origin)?.label ?? origin
}

function rowCountLabel(count: number): string {
  return count === 1 ? "1 row" : `${count} rows`
}

function visibleRows<T extends { ingest_origin: IngestOrigin }>(rows: readonly T[], usingFixture: boolean): T[] {
  if (!usingFixture) return [...rows]
  return rows.filter((row) => row.ingest_origin !== "device")
}

function byMeasuredAtDesc<T extends { measured_at: string }>(rows: readonly T[]): T[] {
  return [...rows].sort((a, b) => {
    const aTime = new Date(a.measured_at).getTime()
    const bTime = new Date(b.measured_at).getTime()
    if (Number.isFinite(aTime) && Number.isFinite(bTime) && aTime !== bTime) return bTime - aTime
    if (a.measured_at === b.measured_at) return 0
    return a.measured_at < b.measured_at ? 1 : -1
  })
}

function majorityUnit(rows: readonly { unit: string }[]): string | null {
  const counts = new Map<string, number>()
  for (const row of rows) counts.set(row.unit, (counts.get(row.unit) ?? 0) + 1)
  let best: string | null = null
  let bestCount = 0
  for (const [unit, count] of counts) {
    if (count > bestCount) {
      best = unit
      bestCount = count
    }
  }
  return best
}

function toGlucoseRows(points: readonly GlucosePoint[], unit: string): GlucoseRow[] {
  const byTime = new Map<number, GlucoseRow>()
  for (const point of points) {
    if (point.unit !== unit || !Number.isFinite(point.value)) continue
    const measuredAt = new Date(point.measured_at).getTime()
    if (!Number.isFinite(measuredAt)) continue
    const row = byTime.get(measuredAt) ?? {
      measuredAt,
      unit: point.unit,
      synthetic: null,
      manual: null,
      device: null,
    }
    row[point.ingest_origin] = point.value
    byTime.set(measuredAt, row)
  }
  return [...byTime.values()].sort((a, b) => a.measuredAt - b.measuredAt)
}

function toPressureRows(points: readonly BpPoint[], unit: string): PressureRow[] {
  return points
    .filter((point) => point.unit === unit && Number.isFinite(point.systolic) && Number.isFinite(point.diastolic))
    .map((point) => ({
      measuredAt: new Date(point.measured_at).getTime(),
      systolic: point.systolic,
      diastolic: point.diastolic,
      unit: point.unit,
      origin: originLabel(point.ingest_origin),
    }))
    .filter((row) => Number.isFinite(row.measuredAt))
    .sort((a, b) => a.measuredAt - b.measuredAt)
}

function rowRecord(payload: unknown): Record<string, unknown> {
  if (!payload || typeof payload !== "object") return {}
  return payload as Record<string, unknown>
}

function GlucoseTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload || payload.length === 0) return null
  const points = payload.filter((item) => typeof item.value === "number")
  if (points.length === 0) return null
  const row = rowRecord(points[0]?.payload)
  const measuredAt = row.measuredAt
  const unit = typeof row.unit === "string" ? row.unit : ""
  return (
    <div className="rounded-xl border border-line bg-card px-3 py-2 text-sm text-ink">
      {typeof measuredAt === "number" ? <p className="text-muted">{formatWhen(measuredAt)}</p> : null}
      <ul className="mt-1 flex flex-col gap-1">
        {points.map((point) => (
          <li key={String(point.dataKey)} className="flex items-baseline justify-between gap-4">
            <span>{point.name}</span>
            <span className="font-medium tabular-nums">
              {point.value} {unit}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function PressureTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload || payload.length === 0) return null
  const row = rowRecord(payload[0]?.payload)
  const measuredAt = row.measuredAt
  const unit = typeof row.unit === "string" ? row.unit : ""
  const origin = typeof row.origin === "string" ? row.origin : ""
  const systolic = row.systolic
  const diastolic = row.diastolic
  return (
    <div className="rounded-xl border border-line bg-card px-3 py-2 text-sm text-ink">
      {typeof measuredAt === "number" ? <p className="text-muted">{formatWhen(measuredAt)}</p> : null}
      <ul className="mt-1 flex flex-col gap-1">
        {typeof systolic === "number" ? (
          <li className="flex items-baseline justify-between gap-4">
            <span>Systolic</span>
            <span className="font-medium tabular-nums">
              {systolic} {unit}
            </span>
          </li>
        ) : null}
        {typeof diastolic === "number" ? (
          <li className="flex items-baseline justify-between gap-4">
            <span>Diastolic</span>
            <span className="font-medium tabular-nums">
              {diastolic} {unit}
            </span>
          </li>
        ) : null}
      </ul>
      {origin ? <p className="mt-1 text-muted">{origin}</p> : null}
    </div>
  )
}

function OriginBadge({ origin }: { origin: IngestOrigin }) {
  const item = ORIGINS.find((entry) => entry.origin === origin)
  return <Badge tone={item?.tone ?? "neutral"}>{item?.label ?? origin}</Badge>
}

function actionErrorText(error: unknown, usingFixture: boolean): string {
  const base =
    error instanceof IngestRequestError
      ? `${error.message} (${error.status}).`
      : error instanceof Error && error.message
        ? `${error.message}.`
        : "The Nightscout mock request failed."
  if (usingFixture) return `${base} Fixture preview stays on this page.`
  return base
}

function SyncDetails({ status, unavailable }: { status: IngestStatus | null; unavailable: boolean }) {
  if (unavailable || !status) {
    return <p>Sync status unavailable</p>
  }
  const rows: { label: string; value: string }[] = []
  if (status.status) rows.push({ label: "Status", value: status.status })
  if (status.finished_at) rows.push({ label: "Latest sync", value: formatWhen(status.finished_at) })
  if (status.connector) rows.push({ label: "Connector", value: status.connector })
  if (status.inserted_count != null) rows.push({ label: "Inserted", value: String(status.inserted_count) })
  if (status.duplicate_count != null) rows.push({ label: "Duplicates", value: String(status.duplicate_count) })
  if (rows.length === 0) {
    return <p className="text-sm text-muted">The status response did not include a status or sync time.</p>
  }
  return (
    <dl className="grid gap-3 sm:grid-cols-2">
      {rows.map((row) => (
        <div key={row.label}>
          <dt className="text-sm text-muted">{row.label}</dt>
          <dd className="mt-1 font-medium">{row.value}</dd>
        </div>
      ))}
    </dl>
  )
}

function GlucoseChart({ points }: { points: readonly GlucosePoint[] }) {
  const unit = majorityUnit(points)
  const rows = useMemo(() => (unit ? toGlucoseRows(points, unit) : []), [points, unit])
  const omitted = unit !== null && points.some((point) => point.unit !== unit)
  if (!unit || rows.length === 0) {
    return (
      <EmptyState title="No glucose readings to plot.">
        Rows in this range stay in the table with time, unit, and origin.
      </EmptyState>
    )
  }
  return (
    <div className="flex min-w-0 flex-col gap-3">
      {omitted ? (
        <p className="text-sm text-muted">Some rows use another unit. This axis is {unit}. Every row stays in the table.</p>
      ) : null}
      <div
        className="h-72 w-full min-w-0"
        role="img"
        aria-label={`Line chart of glucose in ${unit} over time. Synthetic, Manual, and Device are separate lines.`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 12, right: 12, left: 8, bottom: 8 }}>
            <CartesianGrid stroke="var(--color-line, #e3dcd2)" vertical={false} />
            <XAxis
              dataKey="measuredAt"
              type="number"
              scale="time"
              domain={[(min: number) => min - 3_600_000, (max: number) => max + 3_600_000]}
              tickFormatter={(value: number) => formatAxisTime(Number(value))}
              tick={{ fill: "var(--color-muted, #5c564e)", fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: "var(--color-line, #e3dcd2)" }}
              minTickGap={28}
              height={58}
            >
              <Label value="Time" position="insideBottom" offset={0} style={{ fill: "var(--color-muted, #5c564e)", fontSize: 12 }} />
            </XAxis>
            <YAxis
              allowDecimals={false}
              width={64}
              tick={{ fill: "var(--color-muted, #5c564e)", fontSize: 12 }}
              tickLine={false}
              axisLine={false}
            >
              <Label
                value={unit}
                angle={-90}
                position="insideLeft"
                offset={8}
                style={{ fill: "var(--color-muted, #5c564e)", fontSize: 12, textAnchor: "middle" }}
              />
            </YAxis>
            <Tooltip content={<GlucoseTooltip />} isAnimationActive={false} cursor={{ stroke: "var(--color-line, #e3dcd2)" }} />
            <Legend wrapperStyle={{ fontSize: 12, color: "var(--color-ink, #221f1b)", paddingTop: 4 }} />
            {ORIGINS.map((series) => (
              <Line
                key={series.origin}
                type="linear"
                dataKey={series.origin}
                name={series.label}
                stroke={series.stroke}
                strokeWidth={2}
                connectNulls={false}
                isAnimationActive={false}
                dot={{ r: 3, strokeWidth: 0 }}
                activeDot={{ r: 4, strokeWidth: 0 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

function PressureChart({ points }: { points: readonly BpPoint[] }) {
  const unit = majorityUnit(points)
  const rows = useMemo(() => (unit ? toPressureRows(points, unit) : []), [points, unit])
  const omitted = unit !== null && points.some((point) => point.unit !== unit)
  if (!unit || rows.length === 0) {
    return (
      <EmptyState title="No blood pressure readings to plot.">
        Rows in this range stay in the table with time, unit, and origin.
      </EmptyState>
    )
  }
  return (
    <div className="flex min-w-0 flex-col gap-3">
      {omitted ? (
        <p className="text-sm text-muted">Some rows use another unit. This axis is {unit}. Every row stays in the table.</p>
      ) : null}
      <div className="h-72 w-full min-w-0" role="img" aria-label={`Line chart of systolic and diastolic blood pressure in ${unit} over time.`}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 12, right: 12, left: 8, bottom: 8 }}>
            <CartesianGrid stroke="var(--color-line, #e3dcd2)" vertical={false} />
            <XAxis
              dataKey="measuredAt"
              type="number"
              scale="time"
              domain={[(min: number) => min - 3_600_000, (max: number) => max + 3_600_000]}
              tickFormatter={(value: number) => formatAxisTime(Number(value))}
              tick={{ fill: "var(--color-muted, #5c564e)", fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: "var(--color-line, #e3dcd2)" }}
              minTickGap={28}
              height={58}
            >
              <Label value="Time" position="insideBottom" offset={0} style={{ fill: "var(--color-muted, #5c564e)", fontSize: 12 }} />
            </XAxis>
            <YAxis
              allowDecimals={false}
              width={64}
              tick={{ fill: "var(--color-muted, #5c564e)", fontSize: 12 }}
              tickLine={false}
              axisLine={false}
            >
              <Label
                value={unit}
                angle={-90}
                position="insideLeft"
                offset={8}
                style={{ fill: "var(--color-muted, #5c564e)", fontSize: 12, textAnchor: "middle" }}
              />
            </YAxis>
            <Tooltip content={<PressureTooltip />} isAnimationActive={false} cursor={{ stroke: "var(--color-line, #e3dcd2)" }} />
            <Legend wrapperStyle={{ fontSize: 12, color: "var(--color-ink, #221f1b)", paddingTop: 4 }} />
            <Line
              type="linear"
              dataKey="systolic"
              name="Systolic"
              stroke="var(--color-sage, #2f5d45)"
              strokeWidth={2}
              isAnimationActive={false}
              dot={{ r: 3, strokeWidth: 0 }}
              activeDot={{ r: 4, strokeWidth: 0 }}
            />
            <Line
              type="linear"
              dataKey="diastolic"
              name="Diastolic"
              stroke="var(--color-calm, #3d5f78)"
              strokeWidth={2}
              isAnimationActive={false}
              dot={{ r: 3, strokeWidth: 0 }}
              activeDot={{ r: 4, strokeWidth: 0 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export function IngestPage() {
  const [snapshot, setSnapshot] = useState<IngestSnapshot | null>(null)
  const [loading, setLoading] = useState(true)
  const [posting, setPosting] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    loadIngestSnapshot(DEMO_PATIENT_ID)
      .then((next) => {
        if (!cancelled) setSnapshot(next)
      })
      .catch(() => {
        if (!cancelled) setSnapshot(fixtureSnapshot())
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function onLoadMock() {
    setActionError(null)
    setPosting(true)
    const usingFixture = snapshot?.usingFixture ?? true
    try {
      await postNightscoutMock(DEMO_PATIENT_ID)
    } catch (error) {
      setActionError(actionErrorText(error, usingFixture))
      setPosting(false)
      return
    }
    try {
      setSnapshot(await loadIngestSnapshot(DEMO_PATIENT_ID))
    } catch {
      setSnapshot(fixtureSnapshot())
    } finally {
      setPosting(false)
    }
  }

  const glucose = useMemo(
    () => visibleRows(snapshot?.glucose ?? [], snapshot?.usingFixture ?? false),
    [snapshot],
  )
  const bloodPressure = useMemo(
    () => visibleRows(snapshot?.bloodPressure ?? [], snapshot?.usingFixture ?? false),
    [snapshot],
  )
  const glucoseTable = useMemo(() => byMeasuredAtDesc(glucose), [glucose])
  const pressureTable = useMemo(() => byMeasuredAtDesc(bloodPressure), [bloodPressure])
  const missesFasting = rangeMissesFastingGlucose(glucose)

  return (
    <div className="flex w-full min-w-0 flex-col gap-12 text-ink">
      <div className="flex flex-col gap-3">
        <PageHeader
          title="Data sources"
          lede={`Glucose and blood pressure history for patient ${DEMO_PATIENT_ID}.`}
          note="Synthetic demo data. Not medical advice."
        />
        <p className="max-w-prose text-sm leading-6 text-muted">{CAPTION}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Sync status</CardTitle>
          <CardDescription>Status and sync time for this patient, when the status endpoint returns them.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col items-start gap-4">
          <div aria-live="polite">
            {loading || !snapshot ? (
              <p role="status" className="text-sm text-muted">
                Loading readings.
              </p>
            ) : (
              <SyncDetails status={snapshot.status} unavailable={snapshot.statusUnavailable} />
            )}
          </div>
          <Button type="button" onClick={() => void onLoadMock()} disabled={loading || posting} aria-busy={posting}>
            Load demo Nightscout fixture
          </Button>
          {posting ? <p role="status" className="text-sm text-muted">Loading demo Nightscout fixture.</p> : null}
          {actionError ? (
            <p role="alert" className="text-sm text-amber">
              {actionError}
            </p>
          ) : null}
          <p className="text-sm text-muted">Posts the demo Nightscout fixture for this patient, then reloads the rows.</p>
        </CardContent>
      </Card>

      {snapshot?.usingFixture ? (
        <SectionHeading
          title="Fixture preview, API not connected"
          lede="Fixture rows use Synthetic and Manual. The Device label is not applied to these rows."
        />
      ) : null}

      {snapshot ? (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Origin labels</CardTitle>
              <CardDescription>Synthetic, Manual, and Device are separate labels.</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="grid gap-3 sm:grid-cols-3">
                {ORIGINS.map((item) => {
                  const count =
                    glucose.filter((row) => row.ingest_origin === item.origin).length +
                    bloodPressure.filter((row) => row.ingest_origin === item.origin).length
                  return (
                    <li key={item.origin} className="flex flex-col items-start gap-3 rounded-xl bg-neutral-soft px-4 py-4">
                      <OriginBadge origin={item.origin} />
                      <span className="font-serif text-2xl font-medium text-ink tabular-nums">{rowCountLabel(count)}</span>
                    </li>
                  )
                })}
              </ul>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Glucose</CardTitle>
              <CardDescription>Time, value, and unit for each glucose row.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-5">
              {missesFasting ? (
                <p role="status" className="rounded-xl border border-line bg-amber-soft px-3 py-2 text-sm text-ink">
                  No fasting glucose in this range.
                </p>
              ) : null}
              <GlucoseChart points={glucose} />
              {glucoseTable.length === 0 ? (
                <EmptyState title="No glucose readings in this range.">
                  Each row lists time, value, unit, context, origin, and source.
                </EmptyState>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[720px] text-left text-sm">
                    <caption className="sr-only">Glucose history with time, value, unit, and origin</caption>
                    <thead>
                      <tr className="border-b border-line text-sm text-muted">
                        <th scope="col" className="pb-3 pr-4 font-medium">Time</th>
                        <th scope="col" className="pb-3 pr-4 font-medium">Value</th>
                        <th scope="col" className="pb-3 pr-4 font-medium">Unit</th>
                        <th scope="col" className="pb-3 pr-4 font-medium">Context</th>
                        <th scope="col" className="pb-3 pr-4 font-medium">Origin</th>
                        <th scope="col" className="pb-3 font-medium">Source</th>
                      </tr>
                    </thead>
                    <tbody>
                      {glucoseTable.map((point, index) => (
                        <tr key={`${point.measured_at}-${point.ingest_origin}-${index}`} className="border-b border-line last:border-b-0">
                          <td className="py-4 pr-4">{formatWhen(point.measured_at)}</td>
                          <td className="py-4 pr-4 font-medium tabular-nums">{point.value}</td>
                          <td className="py-4 pr-4">{point.unit}</td>
                          <td className="py-4 pr-4">{contextLabel(point.measurement_context)}</td>
                          <td className="py-4 pr-4">
                            <OriginBadge origin={point.ingest_origin} />
                          </td>
                          <td className="py-4">{point.source}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Blood pressure</CardTitle>
              <CardDescription>Systolic and diastolic values paired at the same time.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-5">
              <PressureChart points={bloodPressure} />
              {pressureTable.length === 0 ? (
                <EmptyState title="No blood pressure readings in this range.">
                  Each row lists time, systolic, diastolic, unit, origin, and source.
                </EmptyState>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[720px] text-left text-sm">
                    <caption className="sr-only">Blood pressure history with time, systolic, diastolic, and origin</caption>
                    <thead>
                      <tr className="border-b border-line text-sm text-muted">
                        <th scope="col" className="pb-3 pr-4 font-medium">Time</th>
                        <th scope="col" className="pb-3 pr-4 font-medium">Systolic</th>
                        <th scope="col" className="pb-3 pr-4 font-medium">Diastolic</th>
                        <th scope="col" className="pb-3 pr-4 font-medium">Unit</th>
                        <th scope="col" className="pb-3 pr-4 font-medium">Origin</th>
                        <th scope="col" className="pb-3 font-medium">Source</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pressureTable.map((point, index) => (
                        <tr key={`${point.measured_at}-${point.ingest_origin}-${index}`} className="border-b border-line last:border-b-0">
                          <td className="py-4 pr-4">{formatWhen(point.measured_at)}</td>
                          <td className="py-4 pr-4 font-medium tabular-nums">{point.systolic}</td>
                          <td className="py-4 pr-4 font-medium tabular-nums">{point.diastolic}</td>
                          <td className="py-4 pr-4">{point.unit}</td>
                          <td className="py-4 pr-4">
                            <OriginBadge origin={point.ingest_origin} />
                          </td>
                          <td className="py-4">{point.source}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  )
}
