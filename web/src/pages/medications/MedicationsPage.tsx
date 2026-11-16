import { useId, useState, type ChangeEvent } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input, Label } from "@/components/ui/field";
import { EmptyState } from "@/components/layout/EmptyState";
import { PageHeader } from "@/components/layout/PageHeader";
import { SectionHeading } from "@/components/layout/SectionHeading";
import { DEMO_TODAY, medications, type DoseStatus } from "@/data/demo";
import { useDoseTracker, type TrackedDose } from "@/state/dose-tracker";

const TIME_ZONE = "Asia/Kolkata";
const DEMO_CAPTION = "Demo data. Not medical advice.";
type Medication = (typeof medications)[number];
type SlotStatus = DoseStatus;

function parseIso(iso: string): Date {
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) return new Date(`${iso}T00:00:00+05:30`);
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(iso)) return new Date(`${iso}:00+05:30`);
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(iso)) return new Date(`${iso}+05:30`);
  return new Date(iso);
}

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: TIME_ZONE,
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(parseIso(iso));
}

function formatTime(value: string): string {
  const clock = /^\d{2}:\d{2}$/.test(value) ? `${DEMO_TODAY}T${value}:00+05:30` : value;
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: TIME_ZONE,
    hour: "numeric",
    minute: "2-digit",
  }).format(parseIso(clock));
}

function formatScheduleToken(value: string): string {
  if (/^\d{2}:\d{2}$/.test(value)) return formatTime(value);
  return value.replace(/\b\d{2}:\d{2}\b/g, (match) => formatTime(match));
}

function addDays(isoDate: string, days: number): string {
  const [year, month, day] = isoDate.split("-").map(Number);
  const next = new Date(Date.UTC(year, month - 1, day + days));
  const yyyy = next.getUTCFullYear();
  const mm = String(next.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(next.getUTCDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

const WINDOW_DAYS = Array.from({ length: 7 }, (_, index) => addDays(DEMO_TODAY, index - 6));
const WINDOW_SET = new Set(WINDOW_DAYS);

const STATUS_LABEL: Record<SlotStatus, string> = {
  taken: "Taken",
  missed: "Missed",
  unknown: "Unknown",
};

function statusTone(status: SlotStatus): "green" | "amber" | "neutral" {
  if (status === "taken") return "green";
  if (status === "missed") return "amber";
  return "neutral";
}

function endValue(end: Medication["end"]): string {
  return end ? formatDate(end) : "Ongoing";
}

function DoseStatusControl({
  slot,
  medicationName,
  onStatus,
}: {
  slot: TrackedDose;
  medicationName: string;
  onStatus: (status: "taken" | "missed") => void;
}) {
  const taken = slot.status === "taken";
  const missed = slot.status === "missed";
  const when = `${formatDate(slot.date)} at ${formatTime(slot.time)}`;

  return (
    <div className="flex w-full flex-col items-stretch gap-2 sm:w-auto sm:items-end">
      <Badge tone={statusTone(slot.status)} className="self-start sm:self-auto">
        {STATUS_LABEL[slot.status]}
      </Badge>
      <div
        role="group"
        aria-label={`Update ${medicationName} on ${when}`}
        className="flex flex-wrap gap-2 sm:justify-end"
      >
        <Button
          type="button"
          size="sm"
          variant={taken ? "default" : "outline"}
          aria-pressed={taken}
          onClick={() => onStatus("taken")}
        >
          I&apos;ve taken it
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          aria-pressed={missed}
          className={
            missed ? "border-amber bg-amber-soft text-amber hover:bg-amber-soft" : undefined
          }
          onClick={() => onStatus("missed")}
        >
          Not taken
        </Button>
      </div>
      {slot.confirmed && taken ? (
        <p className="text-xs text-muted sm:text-right" aria-live="polite">
          Recorded as taken.
        </p>
      ) : null}
      {slot.confirmed && missed ? (
        <p className="max-w-xs text-xs text-muted sm:text-right" aria-live="polite">
          Not recorded as taken. Missed on the dashboard, so a check-in is queued.
        </p>
      ) : null}
    </div>
  );
}

export function MedicationsPage() {
  const { slots: doseSlots, setStatus } = useDoseTracker();
  const inputId = useId();
  const helpId = useId();
  const [inputKey, setInputKey] = useState(0);
  const [files, setFiles] = useState<{ id: string; name: string }[]>([]);

  function onFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setFiles((current) => [
      ...current,
      { id: `${file.name}-${current.length + 1}`, name: file.name },
    ]);
    setInputKey((key) => key + 1);
  }

  return (
    <div className="flex w-full min-w-0 flex-col gap-12 text-ink">
      <PageHeader
        title="Medications"
        lede="Recorded medicines and schedule times. Mark a dose taken or not taken. Not taken stays off the taken count, so the dashboard records it as missed and queues a check-in."
        note={DEMO_CAPTION}
      />

      <section className="flex flex-col gap-5">
        <SectionHeading
          title="Recorded regimen"
          lede={`Schedule record for ${formatDate(WINDOW_DAYS[0])} – ${formatDate(DEMO_TODAY)}. Update a row with I've taken it or Not taken. Not taken is a miss.`}
        />

        {medications.map((medication) => {
          const slots = doseSlots
            .filter(
              (slot) => slot.medicationId === medication.id && WINDOW_SET.has(slot.date),
            )
            .slice()
            .sort((a, b) => a.date.localeCompare(b.date) || a.time.localeCompare(b.time));
          const earlierCount = doseSlots.filter(
            (slot) => slot.medicationId === medication.id && !WINDOW_SET.has(slot.date),
          ).length;

          return (
            <Card key={medication.id} >
              <CardHeader>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <CardTitle className="font-serif text-xl font-medium">{medication.name}</CardTitle>
                    <CardDescription>
                      {medication.dose} · {medication.frequency}
                    </CardDescription>
                  </div>
                  {medication.end ? null : <Badge tone="green">Ongoing</Badge>}
                </div>
              </CardHeader>
              <CardContent className="flex flex-col gap-5">
                <dl className="grid gap-4 sm:grid-cols-3">
                  <div>
                    <dt className="text-sm text-muted">
                      Times
                    </dt>
                    <dd className="mt-1 text-sm text-ink">
                      {medication.times.length > 0
                        ? medication.times.map(formatScheduleToken).join(", ")
                        : "No times recorded"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-sm text-muted">
                      Start
                    </dt>
                    <dd className="mt-1 text-sm text-ink">{formatDate(medication.start)}</dd>
                  </div>
                  <div>
                    <dt className="text-sm text-muted">
                      End
                    </dt>
                    <dd className="mt-1 text-sm text-ink">{endValue(medication.end)}</dd>
                  </div>
                </dl>

                <div className="flex flex-col gap-2">
                  <h3 className="text-sm font-semibold text-ink">
                    Last 7 demo days
                  </h3>
                  {slots.length === 0 ? (
                    <EmptyState title="No schedule rows in this 7-day window.">
                      {earlierCount > 0
                        ? "Earlier demo rows exist outside these dates and are not listed here."
                        : "Dose rows for this medicine will appear in this window when the schedule includes them."}
                    </EmptyState>
                  ) : (
                    <ul
                      aria-label={`Schedule rows for ${medication.name} from ${formatDate(WINDOW_DAYS[0])} to ${formatDate(DEMO_TODAY)}`}
                      className="flex flex-col"
                    >
                      {slots.map((slot) => (
                        <li
                          key={slot.id}
                          className="flex flex-col gap-3 border-t border-line py-3 sm:flex-row sm:items-start sm:justify-between"
                        >
                          <div className="min-w-0">
                            <p className="flex flex-wrap items-center gap-2 text-sm text-ink">
                              {formatDate(slot.date)}
                              {slot.date === DEMO_TODAY ? <Badge tone="blue">Today</Badge> : null}
                            </p>
                            <p className="mt-1 text-sm text-ink">{formatTime(slot.time)}</p>
                          </div>
                          <DoseStatusControl
                            slot={slot}
                            medicationName={medication.name}
                            onStatus={(status) => setStatus(slot.id, status)}
                          />
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </section>

      <section className="flex flex-col gap-5">
        <SectionHeading
          title="Prescription file"
          lede="Choosing a file keeps the filename in this session. Nothing is uploaded."
        />
        <Card >
          <CardHeader>
            <CardTitle>Add a filename</CardTitle>
            <CardDescription>
              The list below is local to this page. Demo only, file not stored.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor={inputId}>Prescription file</Label>
              <Input
                key={inputKey}
                id={inputId}
                type="file"
                accept=".pdf,application/pdf,image/*"
                aria-describedby={helpId}
                className="h-auto py-2 file:mr-3 file:min-h-10 file:rounded-md file:border-0 file:bg-sage-soft file:px-3 file:py-2 file:text-sm file:font-medium file:text-sage"
                onChange={onFile}
              />
              <p id={helpId} className="text-sm text-muted">
                Demo only, file not stored.
              </p>
            </div>
            {files.length === 0 ? (
              <EmptyState title="No filename added yet.">
                Choose a prescription file to keep its name in this session. The file is not stored.
              </EmptyState>
            ) : (
              <ul className="flex flex-col gap-2" aria-live="polite">
                {files.map((file) => (
                  <li
                    key={file.id}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-line px-4 py-3"
                  >
                    <span className="text-sm font-medium text-ink">{file.name}</span>
                    <span className="text-sm text-muted">Demo only, file not stored</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
