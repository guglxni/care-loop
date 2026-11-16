import { useMemo } from "react";
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
} from "recharts";
import { EmptyState } from "@/components/layout/EmptyState";
import type { GlucoseContext, GlucoseSource } from "@/data/demo";

const LOCALE = "en-IN";
const TIME_ZONE = "Asia/Kolkata";

const SERIES = [
  { key: "glucometer", label: "Glucometer", stroke: "var(--color-sage, #2f5d45)" },
  { key: "cgm", label: "CGM", stroke: "var(--color-calm, #3d5f78)" },
  { key: "manual", label: "Manual", stroke: "var(--color-muted, #5c564e)" },
] as const;

type SeriesKey = (typeof SERIES)[number]["key"];

export type GlucosePoint = {
  measuredAt: string;
  value: number;
  unit: string;
  context: GlucoseContext;
  source: GlucoseSource;
};

type ChartRow = {
  measuredAt: number;
  unit: string;
  context: GlucoseContext;
  glucometer: number | null;
  cgm: number | null;
  manual: number | null;
};

const CONTEXT_LABEL: Record<GlucoseContext, string> = {
  fasting: "Fasting",
  post_meal: "Post-meal",
  other: "Other",
};

const SOURCE_LABEL: Record<GlucoseSource, string> = {
  manual: "Manual",
  cgm: "CGM",
  glucometer: "Glucometer",
};

export function glucoseContextLabel(context: string): string {
  if (context in CONTEXT_LABEL) return CONTEXT_LABEL[context as GlucoseContext];
  return context;
}

export function glucoseSourceLabel(source: string): string {
  if (source in SOURCE_LABEL) return SOURCE_LABEL[source as GlucoseSource];
  return source;
}

export function formatWhen(value: string | number): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat(LOCALE, {
    timeZone: TIME_ZONE,
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function formatDay(value: string): string {
  const date = new Date(value.length <= 10 ? `${value}T00:00:00+05:30` : value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(LOCALE, {
    timeZone: TIME_ZONE,
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(date);
}

function formatAxisTime(value: number): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat(LOCALE, {
    timeZone: TIME_ZONE,
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function toRows(readings: readonly GlucosePoint[]): ChartRow[] {
  return readings
    .filter((reading) => reading.unit === "mg/dL" && Number.isFinite(reading.value))
    .map((reading) => ({
      measuredAt: new Date(reading.measuredAt).getTime(),
      unit: reading.unit,
      context: reading.context,
      glucometer: reading.source === "glucometer" ? reading.value : null,
      cgm: reading.source === "cgm" ? reading.value : null,
      manual: reading.source === "manual" ? reading.value : null,
    }))
    .filter((row) => Number.isFinite(row.measuredAt))
    .sort((a, b) => a.measuredAt - b.measuredAt);
}

function rowRecord(payload: unknown): Record<string, unknown> {
  if (!payload || typeof payload !== "object") return {};
  return payload as Record<string, unknown>;
}

function GlucoseTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload || payload.length === 0) return null;
  const points = payload.filter((item) => typeof item.value === "number");
  if (points.length === 0) return null;
  const row = rowRecord(points[0]?.payload);
  const measuredAt = row.measuredAt;
  const context = typeof row.context === "string" ? row.context : "";
  const unit = typeof row.unit === "string" ? row.unit : "mg/dL";

  return (
    <div className="rounded-xl border border-line bg-card px-3 py-2 text-sm text-ink">
      {typeof measuredAt === "number" ? <p className="text-muted">{formatWhen(measuredAt)}</p> : null}
      <ul className="mt-1 flex flex-col gap-1">
        {points.map((point) => (
          <li key={String(point.name)} className="flex items-baseline justify-between gap-4">
            <span>{point.name}</span>
            <span className="font-medium tabular-nums">
              {point.value} {unit}
            </span>
          </li>
        ))}
      </ul>
      {context ? <p className="mt-1 text-muted">{glucoseContextLabel(context)}</p> : null}
    </div>
  );
}

type GlucoseChartProps = {
  readings: readonly GlucosePoint[];
  emptyLabel?: string;
};

export function GlucoseChart({
  readings,
  emptyLabel = "No glucose readings to plot.",
}: GlucoseChartProps) {
  const rows = useMemo(() => toRows(readings), [readings]);
  const activeSeries = SERIES.filter((series) => rows.some((row) => row[series.key as SeriesKey] != null));
  const emptyMessage = readings.length === 0 ? emptyLabel : "No mg/dL readings to plot.";
  const otherUnits = readings.some((reading) => reading.unit !== "mg/dL");

  return (
    <div className="flex min-w-0 flex-col gap-3">
      <p className="text-sm text-muted">Demo data. Not medical advice.</p>
      {otherUnits && rows.length > 0 ? (
        <p className="text-sm text-muted">
          Some readings use another unit. This axis is mg/dL, so those rows stay in the table only.
        </p>
      ) : null}
      {rows.length === 0 ? (
        <EmptyState title={emptyMessage}>
          The chart appears when this view has mg/dL readings. Time, unit, and source stay in the list.
        </EmptyState>
      ) : (
        <div
          className="h-72 w-full min-w-0"
          role="img"
          aria-label="Line chart of glucose in mg/dL over time. Each source is a separate line."
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
                <Label
                  value="Time"
                  position="insideBottom"
                  offset={0}
                  style={{ fill: "var(--color-muted, #5c564e)", fontSize: 12 }}
                />
              </XAxis>
              <YAxis
                allowDecimals={false}
                width={64}
                tick={{ fill: "var(--color-muted, #5c564e)", fontSize: 12 }}
                tickLine={false}
                axisLine={false}
              >
                <Label
                  value="mg/dL"
                  angle={-90}
                  position="insideLeft"
                  offset={8}
                  style={{ fill: "var(--color-muted, #5c564e)", fontSize: 12, textAnchor: "middle" }}
                />
              </YAxis>
              <Tooltip
                content={<GlucoseTooltip />}
                isAnimationActive={false}
                cursor={{ stroke: "var(--color-line, #e3dcd2)" }}
              />
              <Legend wrapperStyle={{ fontSize: 12, color: "var(--color-ink, #221f1b)", paddingTop: 4 }} />
              {activeSeries.map((series) => (
                <Line
                  key={series.key}
                  type="linear"
                  dataKey={series.key}
                  name={series.label}
                  stroke={series.stroke}
                  strokeWidth={2}
                  connectNulls
                  isAnimationActive={false}
                  dot={{ r: 3, strokeWidth: 0 }}
                  activeDot={{ r: 4, strokeWidth: 0 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
