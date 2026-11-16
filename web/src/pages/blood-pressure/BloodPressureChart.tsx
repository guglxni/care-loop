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
import type { BpSource } from "@/data/demo";

const LOCALE = "en-IN";
const TIME_ZONE = "Asia/Kolkata";

const SOURCE_LABEL: Record<BpSource, string> = {
  manual: "Manual",
  home_monitor: "Home monitor",
  clinic: "Clinic",
};

export type BloodPressurePoint = {
  measuredAt: string;
  systolic: number;
  diastolic: number;
  pulse: number | null;
  unit: string;
  source: BpSource;
};

type ChartRow = {
  measuredAt: number;
  systolic: number;
  diastolic: number;
  pulse: number | null;
  unit: string;
  source: BpSource;
};

export function bpSourceLabel(source: string): string {
  if (source in SOURCE_LABEL) return SOURCE_LABEL[source as BpSource];
  return source.split("_").join(" ");
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

function toRows(readings: readonly BloodPressurePoint[]): ChartRow[] {
  return readings
    .filter(
      (reading) =>
        reading.unit === "mmHg" &&
        Number.isFinite(reading.systolic) &&
        Number.isFinite(reading.diastolic),
    )
    .map((reading) => ({
      measuredAt: new Date(reading.measuredAt).getTime(),
      systolic: reading.systolic,
      diastolic: reading.diastolic,
      pulse: reading.pulse,
      unit: reading.unit,
      source: reading.source,
    }))
    .filter((row) => Number.isFinite(row.measuredAt))
    .sort((a, b) => a.measuredAt - b.measuredAt);
}

function rowRecord(payload: unknown): Record<string, unknown> {
  if (!payload || typeof payload !== "object") return {};
  return payload as Record<string, unknown>;
}

function PressureTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload || payload.length === 0) return null;
  const row = rowRecord(payload[0]?.payload);
  const measuredAt = row.measuredAt;
  const unit = typeof row.unit === "string" ? row.unit : "mmHg";
  const source = typeof row.source === "string" ? bpSourceLabel(row.source) : "";
  const systolic = row.systolic;
  const diastolic = row.diastolic;
  const pulse = row.pulse;

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
      {source ? <p className="mt-1 text-muted">{source}</p> : null}
      <p className="text-muted">
        {typeof pulse === "number" ? `Pulse ${pulse}` : "Pulse not recorded"}
      </p>
    </div>
  );
}

type BloodPressureChartProps = {
  readings: readonly BloodPressurePoint[];
  emptyLabel?: string;
};

export function BloodPressureChart({
  readings,
  emptyLabel = "No blood pressure readings to plot.",
}: BloodPressureChartProps) {
  const rows = useMemo(() => toRows(readings), [readings]);
  const emptyMessage = readings.length === 0 ? emptyLabel : "No mmHg readings to plot.";
  const otherUnits = readings.some((reading) => reading.unit !== "mmHg");

  return (
    <div className="flex min-w-0 flex-col gap-3">
      <p className="text-sm text-muted">Demo data. Not medical advice.</p>
      {otherUnits && rows.length > 0 ? (
        <p className="text-sm text-muted">
          Some readings use another unit. This axis is mmHg, so those rows stay in the table only.
        </p>
      ) : null}
      {rows.length === 0 ? (
        <EmptyState title={emptyMessage}>
          The chart appears when this view has mmHg readings. Time, unit, and source stay in the list.
        </EmptyState>
      ) : (
        <div
          className="h-72 w-full min-w-0"
          role="img"
          aria-label="Line chart of systolic and diastolic blood pressure in mmHg over time."
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
                  value="mmHg"
                  angle={-90}
                  position="insideLeft"
                  offset={8}
                  style={{ fill: "var(--color-muted, #5c564e)", fontSize: 12, textAnchor: "middle" }}
                />
              </YAxis>
              <Tooltip
                content={<PressureTooltip />}
                isAnimationActive={false}
                cursor={{ stroke: "var(--color-line, #e3dcd2)" }}
              />
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
      )}
    </div>
  );
}
