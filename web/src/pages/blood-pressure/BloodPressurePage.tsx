import { useMemo, useState, type FormEvent } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/field";
import { EmptyState } from "@/components/layout/EmptyState";
import { PageHeader } from "@/components/layout/PageHeader";
import { SectionHeading } from "@/components/layout/SectionHeading";
import { bpReadings, type BpSource } from "@/data/demo";
import {
  BloodPressureChart,
  bpSourceLabel,
  formatWhen,
  type BloodPressurePoint,
} from "./BloodPressureChart";

const SOURCES: { value: BpSource; label: string }[] = [
  { value: "manual", label: "Manual" },
  { value: "home_monitor", label: "Home monitor" },
  { value: "clinic", label: "Clinic" },
];

type PressureEntry = BloodPressurePoint & { id: string };

function localId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `bp-${crypto.randomUUID()}`;
  }
  return `bp-${Date.now()}`;
}

function toKolkataIso(localValue: string): string {
  const withSeconds = localValue.length === 16 ? `${localValue}:00` : localValue;
  return `${withSeconds}+05:30`;
}

function sourceTone(source: BpSource): "neutral" | "green" | "blue" | "amber" {
  if (source === "home_monitor") return "green";
  if (source === "clinic") return "blue";
  return "neutral";
}

function parseRequired(raw: string): number | null {
  const trimmed = raw.trim();
  if (trimmed === "") return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

export function BloodPressurePage() {
  const [readings, setReadings] = useState<PressureEntry[]>(() =>
    bpReadings
      .map((reading) => ({
        id: String(reading.id),
        measuredAt: reading.measuredAt,
        systolic: reading.systolic,
        diastolic: reading.diastolic,
        pulse: reading.pulse ?? null,
        unit: reading.unit,
        source: reading.source,
      }))
      .sort((a, b) => (a.measuredAt < b.measuredAt ? 1 : a.measuredAt > b.measuredAt ? -1 : 0)),
  );
  const [systolic, setSystolic] = useState("");
  const [diastolic, setDiastolic] = useState("");
  const [pulse, setPulse] = useState("");
  const [source, setSource] = useState<BpSource>("home_monitor");
  const [measuredAt, setMeasuredAt] = useState("");
  const [sourceFilter, setSourceFilter] = useState<BpSource | "all">("all");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const filtered = useMemo(
    () => (sourceFilter === "all" ? readings : readings.filter((reading) => reading.source === sourceFilter)),
    [readings, sourceFilter],
  );

  const systolicInvalid = error !== null && parseRequired(systolic) === null;
  const diastolicInvalid = error !== null && parseRequired(diastolic) === null;
  const timeInvalid = error !== null && measuredAt.trim() === "";
  const pulseInvalid = error === "Enter a numeric pulse, or leave pulse blank.";

  function clearStatus() {
    setError(null);
    setSaved(false);
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const systolicValue = parseRequired(systolic);
    const diastolicValue = parseRequired(diastolic);
    const timeOk = measuredAt.trim() !== "";
    const pulseTrimmed = pulse.trim();
    const pulseValue = pulseTrimmed === "" ? null : parseRequired(pulseTrimmed);

    if (systolicValue === null || diastolicValue === null || !timeOk) {
      setSaved(false);
      setError("Enter systolic, diastolic, and the time of the reading.");
      return;
    }
    if (pulseTrimmed !== "" && pulseValue === null) {
      setSaved(false);
      setError("Enter a numeric pulse, or leave pulse blank.");
      return;
    }

    const entry: PressureEntry = {
      id: localId(),
      measuredAt: toKolkataIso(measuredAt),
      systolic: systolicValue,
      diastolic: diastolicValue,
      pulse: pulseValue,
      unit: "mmHg",
      source,
    };
    setReadings((current) => [entry, ...current]);
    setSystolic("");
    setDiastolic("");
    setPulse("");
    setMeasuredAt("");
    setSourceFilter("all");
    setError(null);
    setSaved(true);
  }

  return (
    <div className="flex w-full min-w-0 flex-col gap-12 text-ink">
      <PageHeader
        title="Blood pressure"
        lede="Blood pressure in mmHg, with time and source. Pulse is optional."
        note="Demo data. Not medical advice."
      />

        <Card>
          <CardHeader>
            <CardTitle>Add a reading</CardTitle>
            <CardDescription>Saves stay in this browser session. The unit is mmHg.</CardDescription>
          </CardHeader>
          <CardContent>
            <form noValidate onSubmit={onSubmit}>
              <fieldset className="grid grid-cols-1 gap-4 border-0 p-0 sm:grid-cols-2">
                <legend className="sr-only">New blood pressure reading</legend>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="bp-systolic">Systolic</Label>
                  <Input
                    id="bp-systolic"
                    name="systolic"
                    type="number"
                    inputMode="decimal"
                    step="any"
                    autoComplete="off"
                    value={systolic}
                    aria-invalid={systolicInvalid || undefined}
                    aria-describedby={systolicInvalid ? "bp-form-error" : undefined}
                    onChange={(event) => {
                      setSystolic(event.target.value);
                      clearStatus();
                    }}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="bp-diastolic">Diastolic</Label>
                  <Input
                    id="bp-diastolic"
                    name="diastolic"
                    type="number"
                    inputMode="decimal"
                    step="any"
                    autoComplete="off"
                    value={diastolic}
                    aria-invalid={diastolicInvalid || undefined}
                    aria-describedby={diastolicInvalid ? "bp-form-error" : undefined}
                    onChange={(event) => {
                      setDiastolic(event.target.value);
                      clearStatus();
                    }}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="bp-pulse">Pulse (optional)</Label>
                  <Input
                    id="bp-pulse"
                    name="pulse"
                    type="number"
                    inputMode="numeric"
                    step="any"
                    autoComplete="off"
                    value={pulse}
                    aria-invalid={pulseInvalid || undefined}
                    aria-describedby={pulseInvalid ? "bp-form-error" : undefined}
                    onChange={(event) => {
                      setPulse(event.target.value);
                      clearStatus();
                    }}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="bp-unit">Unit</Label>
                  <Input id="bp-unit" name="unit" value="mmHg" readOnly aria-readonly="true" />
                  <p className="text-sm text-muted">Locked for this demo.</p>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="bp-source">Source</Label>
                  <Select
                    id="bp-source"
                    name="source"
                    value={source}
                    onChange={(event) => {
                      setSource(event.target.value as BpSource);
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
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="bp-measured-at">Measured at (Asia/Kolkata)</Label>
                  <Input
                    id="bp-measured-at"
                    name="measured_at"
                    type="datetime-local"
                    step={60}
                    value={measuredAt}
                    aria-invalid={timeInvalid || undefined}
                    aria-describedby={timeInvalid ? "bp-form-error" : undefined}
                    onChange={(event) => {
                      setMeasuredAt(event.target.value);
                      clearStatus();
                    }}
                  />
                </div>
                {error ? (
                  <p id="bp-form-error" role="alert" className="text-sm text-amber sm:col-span-2">
                    {error}
                  </p>
                ) : null}
                {saved ? (
                  <p id="bp-form-status" role="status" className="text-sm text-sage sm:col-span-2">
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

        <section className="flex min-w-0 flex-col gap-4" aria-labelledby="bp-readings-heading">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <SectionHeading
              id="bp-readings-heading"
              title="Readings"
              lede={`Showing ${filtered.length} of ${readings.length}.`}
            />
            <div className="flex w-full flex-col gap-1.5 sm:w-56">
              <Label htmlFor="bp-source-filter">Source</Label>
              <Select
                id="bp-source-filter"
                value={sourceFilter}
                onChange={(event) => setSourceFilter(event.target.value as BpSource | "all")}
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
              <CardDescription>Systolic and diastolic on one chart.</CardDescription>
            </CardHeader>
            <CardContent>
              <BloodPressureChart
                readings={filtered}
                emptyLabel={
                  readings.length === 0
                    ? "No blood pressure readings to plot."
                    : "No readings match this filter."
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
                  title={
                    readings.length === 0
                      ? "No blood pressure readings in this demo."
                      : "No readings match this filter."
                  }
                >
                  {readings.length === 0
                    ? "A reading you save appears here with its time, unit, and source."
                    : "Choose another source to see time, unit, and source for those readings."}
                </EmptyState>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[720px] text-left text-sm">
                    <caption className="sr-only">Blood pressure history</caption>
                    <thead>
                      <tr className="border-b border-line text-sm text-muted">
                        <th scope="col" className="pb-3 pr-4 font-medium">
                          Time
                        </th>
                        <th scope="col" className="pb-3 pr-4 font-medium">
                          Systolic
                        </th>
                        <th scope="col" className="pb-3 pr-4 font-medium">
                          Diastolic
                        </th>
                        <th scope="col" className="pb-3 pr-4 font-medium">
                          Pulse
                        </th>
                        <th scope="col" className="pb-3 pr-4 font-medium">
                          Unit
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
                          <td className="py-4 pr-4 font-medium tabular-nums">{reading.systolic}</td>
                          <td className="py-4 pr-4 font-medium tabular-nums">{reading.diastolic}</td>
                          <td className="py-4 pr-4 font-medium tabular-nums">
                            {reading.pulse == null ? "Not recorded" : reading.pulse}
                          </td>
                          <td className="py-4 pr-4">{reading.unit}</td>
                          <td className="py-4">
                            <Badge tone={sourceTone(reading.source)}>{bpSourceLabel(reading.source)}</Badge>
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
    </div>
  );
}

export default BloodPressurePage;
