import { useMemo, useState, type FormEvent } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/field";
import { EmptyState } from "@/components/layout/EmptyState";
import { PageHeader } from "@/components/layout/PageHeader";
import { SectionHeading } from "@/components/layout/SectionHeading";
import {
  glucoseReadings,
  glucoseSchedule,
  missingGlucoseDays,
  type GlucoseContext,
  type GlucoseSource,
} from "@/data/demo";
import {
  formatDay,
  formatWhen,
  GlucoseChart,
  glucoseContextLabel,
  glucoseSourceLabel,
  type GlucosePoint,
} from "./GlucoseChart";

const CONTEXTS: { value: GlucoseContext; label: string }[] = [
  { value: "fasting", label: "Fasting" },
  { value: "post_meal", label: "Post-meal" },
  { value: "other", label: "Other" },
];

const SOURCES: { value: GlucoseSource; label: string }[] = [
  { value: "manual", label: "Manual" },
  { value: "cgm", label: "CGM" },
  { value: "glucometer", label: "Glucometer" },
];

type GlucoseEntry = GlucosePoint & { id: string };

function localId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `glucose-${crypto.randomUUID()}`;
  }
  return `glucose-${Date.now()}`;
}

function toKolkataIso(localValue: string): string {
  const withSeconds = localValue.length === 16 ? `${localValue}:00` : localValue;
  return `${withSeconds}+05:30`;
}

function sourceTone(source: GlucoseSource): "neutral" | "green" | "blue" | "amber" {
  if (source === "glucometer") return "green";
  if (source === "cgm") return "blue";
  return "neutral";
}

export function GlucosePage() {
  const [readings, setReadings] = useState<GlucoseEntry[]>(() =>
    glucoseReadings
      .map((reading) => ({
        id: String(reading.id),
        measuredAt: reading.measuredAt,
        value: reading.value,
        unit: reading.unit,
        context: reading.context,
        source: reading.source,
      }))
      .sort((a, b) => (a.measuredAt < b.measuredAt ? 1 : a.measuredAt > b.measuredAt ? -1 : 0)),
  );
  const [value, setValue] = useState("");
  const [context, setContext] = useState<GlucoseContext>("fasting");
  const [source, setSource] = useState<GlucoseSource>("glucometer");
  const [measuredAt, setMeasuredAt] = useState("");
  const [sourceFilter, setSourceFilter] = useState<GlucoseSource | "all">("all");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const filtered = useMemo(
    () => (sourceFilter === "all" ? readings : readings.filter((reading) => reading.source === sourceFilter)),
    [readings, sourceFilter],
  );
  const gapDays = useMemo(() => [...missingGlucoseDays(readings)].sort((a, b) => a.localeCompare(b)), [readings]);

  const valuePresent = value.trim() !== "" && Number.isFinite(Number(value.trim()));
  const valueInvalid = error !== null && !valuePresent;
  const timeInvalid = error !== null && measuredAt.trim() === "";

  function clearStatus() {
    setError(null);
    setSaved(false);
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = value.trim();
    const parsed = Number(trimmed);
    const valueOk = trimmed !== "" && Number.isFinite(parsed);
    const timeOk = measuredAt.trim() !== "";
    if (!valueOk && !timeOk) {
      setSaved(false);
      setError("Enter a numeric glucose value and the time of the reading.");
      return;
    }
    if (!valueOk) {
      setSaved(false);
      setError("Enter a numeric glucose value.");
      return;
    }
    if (!timeOk) {
      setSaved(false);
      setError("Enter the time of the reading.");
      return;
    }

    const entry: GlucoseEntry = {
      id: localId(),
      measuredAt: toKolkataIso(measuredAt),
      value: parsed,
      unit: "mg/dL",
      context,
      source,
    };
    setReadings((current) => [entry, ...current]);
    setValue("");
    setMeasuredAt("");
    setSourceFilter("all");
    setError(null);
    setSaved(true);
  }

  return (
    <div className="flex w-full min-w-0 flex-col gap-12 text-ink">
      <PageHeader
        title="Glucose"
        lede="Glucose readings in mg/dL, with time, context, and source."
        note="Demo data. Not medical advice."
      />

        <Card>
          <CardHeader>
            <CardTitle>Add a reading</CardTitle>
            <CardDescription>Saves stay in this browser session. The unit is mg/dL.</CardDescription>
          </CardHeader>
          <CardContent>
            <form noValidate onSubmit={onSubmit}>
              <fieldset className="grid grid-cols-1 gap-4 border-0 p-0 sm:grid-cols-2">
                <legend className="sr-only">New glucose reading</legend>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="glucose-value">Value</Label>
                  <Input
                    id="glucose-value"
                    name="value"
                    type="number"
                    inputMode="decimal"
                    step="any"
                    autoComplete="off"
                    value={value}
                    aria-invalid={valueInvalid || undefined}
                    aria-describedby={valueInvalid ? "glucose-form-error" : undefined}
                    onChange={(event) => {
                      setValue(event.target.value);
                      clearStatus();
                    }}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="glucose-unit">Unit</Label>
                  <Input id="glucose-unit" name="unit" value="mg/dL" readOnly aria-readonly="true" />
                  <p className="text-sm text-muted">Locked for this demo.</p>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="glucose-context">Context</Label>
                  <Select
                    id="glucose-context"
                    name="context"
                    value={context}
                    onChange={(event) => {
                      setContext(event.target.value as GlucoseContext);
                      clearStatus();
                    }}
                  >
                    {CONTEXTS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="glucose-source">Source</Label>
                  <Select
                    id="glucose-source"
                    name="source"
                    value={source}
                    onChange={(event) => {
                      setSource(event.target.value as GlucoseSource);
                      clearStatus();
                    }}
                  >
                    {SOURCES.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="flex flex-col gap-1.5 sm:col-span-2">
                  <Label htmlFor="glucose-measured-at">Measured at (Asia/Kolkata)</Label>
                  <Input
                    id="glucose-measured-at"
                    name="measured_at"
                    type="datetime-local"
                    step={60}
                    value={measuredAt}
                    aria-invalid={timeInvalid || undefined}
                    aria-describedby={timeInvalid ? "glucose-form-error" : undefined}
                    onChange={(event) => {
                      setMeasuredAt(event.target.value);
                      clearStatus();
                    }}
                  />
                </div>
                {error ? (
                  <p id="glucose-form-error" role="alert" className="text-sm text-amber sm:col-span-2">
                    {error}
                  </p>
                ) : null}
                {saved ? (
                  <p id="glucose-form-status" role="status" className="text-sm text-sage sm:col-span-2">
                    Saved in this demo only.
                  </p>
                ) : null}
                <div className="sm:col-span-2">
                  <Button type="submit">Save reading</Button>
                </div>
              </fieldset>
            </form>
          </CardContent>
        </Card>

        <section className="flex min-w-0 flex-col gap-4" aria-labelledby="glucose-readings-heading">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <SectionHeading
              id="glucose-readings-heading"
              title="Readings"
              lede={`Showing ${filtered.length} of ${readings.length}. Each source stays on its own line.`}
            />
            <div className="flex w-full flex-col gap-1.5 sm:w-56">
              <Label htmlFor="glucose-source-filter">Source</Label>
              <Select
                id="glucose-source-filter"
                value={sourceFilter}
                onChange={(event) => setSourceFilter(event.target.value as GlucoseSource | "all")}
              >
                <option value="all">All sources</option>
                {SOURCES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          <Card className="min-w-0">
            <CardHeader>
              <CardTitle>Over time</CardTitle>
              <CardDescription>One line for each source.</CardDescription>
            </CardHeader>
            <CardContent>
              <GlucoseChart
                readings={filtered}
                emptyLabel={
                  readings.length === 0 ? "No glucose readings to plot." : "No readings match this filter."
                }
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>History</CardTitle>
              <CardDescription>A reading you save is placed at the top of this list.</CardDescription>
            </CardHeader>
            <CardContent>
              {filtered.length === 0 ? (
                <EmptyState
                  title={readings.length === 0 ? "No glucose readings in this demo." : "No readings match this filter."}
                >
                  {readings.length === 0
                    ? "A reading you save appears here with its time, unit, and source."
                    : "Choose another source to see time, unit, and source for those readings."}
                </EmptyState>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[640px] text-left text-sm">
                    <caption className="sr-only">Glucose history</caption>
                    <thead>
                      <tr className="border-b border-line text-sm text-muted">
                        <th scope="col" className="pb-3 pr-4 font-medium">
                          Time
                        </th>
                        <th scope="col" className="pb-3 pr-4 font-medium">
                          Value
                        </th>
                        <th scope="col" className="pb-3 pr-4 font-medium">
                          Unit
                        </th>
                        <th scope="col" className="pb-3 pr-4 font-medium">
                          Context
                        </th>
                        <th scope="col" className="pb-3 font-medium">
                          Source
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map((reading) => (
                        <tr
                          key={reading.id}
                          className="border-b border-line last:border-b-0 hover:bg-neutral-soft"
                        >
                          <td className="py-4 pr-4">{formatWhen(reading.measuredAt)}</td>
                          <td className="py-4 pr-4 font-medium tabular-nums">{reading.value}</td>
                          <td className="py-4 pr-4">{reading.unit}</td>
                          <td className="py-4 pr-4">{glucoseContextLabel(reading.context)}</td>
                          <td className="py-4">
                            <Badge tone={sourceTone(reading.source)}>{glucoseSourceLabel(reading.source)}</Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </section>

        <Card>
          <CardHeader>
            <CardTitle>Gaps in the demo schedule</CardTitle>
            <CardDescription>
              Fasting dates in the last 7 demo days with no reading, plus the schedule lines used to find them.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-5">
            <div>
              <h3 className="text-sm font-medium">Demo schedule</h3>
              {glucoseSchedule.length === 0 ? (
                <EmptyState title="No schedule lines in this demo." className="mt-3">
                  Fasting expectations used to find gaps will be listed here.
                </EmptyState>
              ) : (
                <ul className="mt-2 flex flex-col gap-2">
                  {glucoseSchedule.map((slot) => (
                    <li key={slot.context} className="text-sm leading-6">
                      {slot.expectation}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div>
              <h3 className="text-sm font-medium">Dates with no fasting reading</h3>
              {gapDays.length === 0 ? (
                <EmptyState title="No fasting gaps in the last 7 demo days." className="mt-3">
                  Every fasting date in that window has a reading.
                </EmptyState>
              ) : (
                <ul className="mt-2 flex flex-col divide-y divide-line">
                  {gapDays.map((day) => (
                    <li key={day} className="py-2 text-sm">
                      {formatDay(day)}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <p className="text-sm text-muted">This list is a schedule gap in the demo data.</p>
          </CardContent>
        </Card>
    </div>
  );
}

export default GlucosePage;
