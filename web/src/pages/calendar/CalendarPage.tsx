import { useId, useState, type FormEvent, type KeyboardEvent } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label, Textarea } from "@/components/ui/field";
import { EmptyState } from "@/components/layout/EmptyState";
import { PageHeader } from "@/components/layout/PageHeader";
import { SectionHeading } from "@/components/layout/SectionHeading";
import { DEMO_TODAY, calendarItems, medications, type DoseSlot } from "@/data/demo";
import { useDoseTracker } from "@/state/dose-tracker";

const TIME_ZONE = "Asia/Kolkata";
const DEMO_CAPTION = "Demo data. Not medical advice.";
type Kind = "consultation" | "laboratory" | "medication" | "follow_up";
type KindFilter = "all" | Kind;
type AgendaItem = {
  id: string;
  kind: Kind;
  title: string;
  start: string;
  location?: string;
  status: string;
  origin: "appointment" | "dose";
};

const KIND_LABEL: Record<Kind, string> = {
  consultation: "Consultation",
  laboratory: "Laboratory",
  medication: "Medication schedule",
  follow_up: "Follow-up",
};

const KIND_TONE: Record<Kind, "blue" | "green" | "neutral" | "amber"> = {
  consultation: "blue",
  laboratory: "green",
  medication: "neutral",
  follow_up: "amber",
};

const FILTERS: { id: KindFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "consultation", label: "Consultations" },
  { id: "laboratory", label: "Laboratory tests" },
  { id: "medication", label: "Medication schedule" },
  { id: "follow_up", label: "Follow-ups" },
];

const KIND_ORDER: Kind[] = ["consultation", "laboratory", "medication", "follow_up"];

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

function formatTime(iso: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: TIME_ZONE,
    hour: "numeric",
    minute: "2-digit",
  }).format(parseIso(iso));
}

function formatWeekday(isoDate: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: TIME_ZONE,
    weekday: "short",
  }).format(parseIso(isoDate));
}

function dayNumber(isoDate: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: TIME_ZONE,
    day: "numeric",
  }).format(parseIso(isoDate));
}

function isoDateInKolkata(iso: string): string {
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) return iso;
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(parseIso(iso));
}

function clockInKolkata(iso: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: TIME_ZONE,
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(parseIso(iso));
}

function addDays(isoDate: string, days: number): string {
  const [year, month, day] = isoDate.split("-").map(Number);
  const next = new Date(Date.UTC(year, month - 1, day + days));
  const yyyy = next.getUTCFullYear();
  const mm = String(next.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(next.getUTCDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function mondayIndex(isoDate: string): number {
  const weekday = new Intl.DateTimeFormat("en-US", {
    timeZone: TIME_ZONE,
    weekday: "short",
  }).format(parseIso(isoDate));
  const map: Record<string, number> = { Mon: 0, Tue: 1, Wed: 2, Thu: 3, Fri: 4, Sat: 5, Sun: 6 };
  return map[weekday] ?? 0;
}

function normalizeClock(value: string): string {
  const match = value.match(/(\d{1,2}):(\d{2})/);
  if (!match) return value;
  return `${match[1].padStart(2, "0")}:${match[2]}`;
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    upcoming: "Upcoming",
    done: "Done",
    taken: "Taken",
    missed: "Missed",
    unknown: "Unknown",
  };
  return labels[status] ?? status;
}

function statusTone(status: string): "neutral" | "green" | "blue" | "amber" {
  if (status === "taken") return "green";
  if (status === "missed") return "amber";
  if (status === "upcoming") return "blue";
  return "neutral";
}

const weekStart = addDays(DEMO_TODAY, -mondayIndex(DEMO_TODAY));
const weekDays = Array.from({ length: 7 }, (_, index) => addDays(weekStart, index));
const weekSet = new Set(weekDays);

function doseSlotAhead(date: string, status: string): boolean {
  if (date > DEMO_TODAY) return true;
  return date === DEMO_TODAY && status === "unknown";
}

function buildAgenda(doseSlots: DoseSlot[]): { week: AgendaItem[]; other: AgendaItem[] } {
  const weekDoseKeys = new Set(
    doseSlots
      .filter((slot) => weekSet.has(slot.date))
      .map((slot) => `${slot.date}T${normalizeClock(slot.time)}`),
  );

  const fromAppointments: AgendaItem[] = calendarItems
    .filter((item) => KIND_ORDER.includes(item.kind))
    .filter((item) => {
      if (item.kind !== "medication") return true;
      const key = `${isoDateInKolkata(item.start)}T${clockInKolkata(item.start)}`;
      return !weekDoseKeys.has(key);
    })
    .map((item) => ({
      id: item.id,
      kind: item.kind,
      title: item.title,
      start: item.start,
      location: item.location,
      status: item.status,
      origin: "appointment" as const,
    }));

  const fromDoses: AgendaItem[] = doseSlots
    .filter((slot) => weekSet.has(slot.date))
    .map((slot) => {
      const medication = medications.find((item) => item.id === slot.medicationId);
      const clock = normalizeClock(slot.time);
      return {
        id: slot.id,
        kind: "medication" as const,
        title: medication ? `${medication.name}, ${medication.dose}` : "Medication schedule",
        start: `${slot.date}T${clock}:00+05:30`,
        status: slot.status,
        origin: "dose" as const,
      };
    });

  const all = [...fromAppointments, ...fromDoses].sort(
    (a, b) => a.start.localeCompare(b.start) || a.title.localeCompare(b.title),
  );

  return {
    week: all.filter((item) => weekSet.has(isoDateInKolkata(item.start))),
    other: all.filter((item) => !weekSet.has(isoDateInKolkata(item.start))),
  };
}

function agendaBlocks(
  items: AgendaItem[],
): Array<{ type: "doses"; items: AgendaItem[] } | { type: "visit"; item: AgendaItem }> {
  const blocks: Array<{ type: "doses"; items: AgendaItem[] } | { type: "visit"; item: AgendaItem }> = [];
  let doses: AgendaItem[] = [];
  function flush() {
    if (doses.length === 0) return;
    blocks.push({ type: "doses", items: doses });
    doses = [];
  }
  for (const item of items) {
    if (item.origin === "dose") {
      doses.push(item);
      continue;
    }
    flush();
    blocks.push({ type: "visit", item });
  }
  flush();
  return blocks;
}

function DoseSchedule({ items }: { items: AgendaItem[] }) {
  return (
    <Card >
      <CardHeader>
        <CardTitle>Medication schedule</CardTitle>
        <CardDescription>Schedule rows for this day.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[20rem] text-left text-sm">
            <caption className="sr-only">Medication schedule rows</caption>
            <thead>
              <tr className="text-sm text-muted">
                <th scope="col" className="pb-2 pr-3 font-medium">
                  Time
                </th>
                <th scope="col" className="pb-2 pr-3 font-medium">
                  Medicine
                </th>
                <th scope="col" className="pb-2 text-right font-medium">
                  Status
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const ahead = isAhead(item);
                return (
                  <tr key={item.id} className="border-t border-line">
                    <td className="py-2.5 pr-3 text-ink">
                      <span
                        aria-hidden
                        className={
                          ahead
                            ? "mr-2 inline-block h-4 w-1 rounded-full bg-calm align-middle"
                            : "mr-2 inline-block h-4 w-1 rounded-full bg-line align-middle"
                        }
                      />
                      {formatTime(item.start)}
                    </td>
                    <td className="py-2.5 pr-3 text-ink">{item.title}</td>
                    <td className="py-2.5 text-right">
                      <Badge tone={statusTone(item.status)}>{statusLabel(item.status)}</Badge>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

function isAhead(item: AgendaItem): boolean {
  if (item.origin === "dose") {
    return doseSlotAhead(isoDateInKolkata(item.start), item.status);
  }
  return item.status !== "done";
}

export function CalendarPage() {
  const { slots } = useDoseTracker();
  const agenda = buildAgenda(slots);
  const noteId = useId();
  const [kind, setKind] = useState<KindFilter>("all");
  const [day, setDay] = useState<string>("week");
  const [openId, setOpenId] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [noteError, setNoteError] = useState<string | null>(null);

  function matches(item: AgendaItem): boolean {
    return kind === "all" || item.kind === kind;
  }

  const weekItems = agenda.week.filter((item) => {
    if (!matches(item)) return false;
    if (day !== "week" && isoDateInKolkata(item.start) !== day) return false;
    return true;
  });
  const otherItems = day === "week" ? agenda.other.filter(matches) : [];

  function saveNote(event: FormEvent<HTMLFormElement>, itemId: string) {
    event.preventDefault();
    const note = (drafts[itemId] ?? "").trim();
    if (!note) {
      setNoteError("Write a note before saving.");
      return;
    }
    setNotes((current) => ({ ...current, [itemId]: note }));
    setNoteError(null);
    setOpenId(null);
  }

  function onNoteKeyDown(event: KeyboardEvent<HTMLFormElement>) {
    if (event.key === "Escape") {
      setOpenId(null);
      setNoteError(null);
    }
  }

  function renderItem(item: AgendaItem) {
    return (
      <AgendaCard
        key={item.id}
        item={item}
        noteId={noteId}
        open={openId === item.id}
        draft={drafts[item.id] ?? ""}
        savedNote={notes[item.id]}
        error={openId === item.id ? noteError : null}
        onOpen={() => {
          setOpenId(item.id);
          setDrafts((current) => ({
            ...current,
            [item.id]: current[item.id] ?? notes[item.id] ?? "",
          }));
          setNoteError(null);
        }}
        onDraft={(value) => {
          setDrafts((current) => ({ ...current, [item.id]: value }));
          setNoteError(null);
        }}
        onSubmit={(event) => saveNote(event, item.id)}
        onKeyDown={onNoteKeyDown}
        onClose={() => {
          setOpenId(null);
          setNoteError(null);
        }}
      />
    );
  }

  const weekGroups = (day === "week" ? weekDays : [day])
    .map((date) => ({
      date,
      items: weekItems.filter((item) => isoDateInKolkata(item.start) === date),
    }))
    .filter((group) => group.items.length > 0);

  return (
    <div className="flex w-full min-w-0 flex-col gap-12 text-ink">
      <PageHeader
        title="Calendar"
        lede={`Week and agenda around ${formatDate(DEMO_TODAY)}. Consultations, laboratory tests, medication times, and follow-ups.`}
        note={DEMO_CAPTION}
      />

      <section className="flex flex-col gap-5">
        <SectionHeading title={`${formatDate(weekDays[0])} – ${formatDate(weekDays[6])}`} />
        <div role="group" aria-label="Item type" className="flex flex-wrap gap-2">
          {FILTERS.map((filter) => (
            <Button
              key={filter.id}
              type="button"
              size="sm"
              variant={kind === filter.id ? "default" : "outline"}
              aria-pressed={kind === filter.id}
              className="min-h-10"
              onClick={() => setKind(filter.id)}
            >
              {filter.label}
            </Button>
          ))}
        </div>
        <div className="flex flex-col gap-2">
          <Button
            type="button"
            size="sm"
            variant={day === "week" ? "default" : "outline"}
            aria-pressed={day === "week"}
            className="min-h-10 self-start"
            onClick={() => setDay("week")}
          >
            Entire week
          </Button>
          <div role="group" aria-label="Day in the demo week" className="grid grid-cols-7 gap-1">
            {weekDays.map((date) => {
              const selected = day === date;
              return (
                <button
                  key={date}
                  type="button"
                  aria-pressed={selected}
                  aria-current={date === DEMO_TODAY ? "date" : undefined}
                  onClick={() => setDay(date)}
                  className={
                    selected
                      ? "flex min-h-11 flex-col items-center justify-center rounded-xl border border-ink bg-ink px-1 py-2 text-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sage focus-visible:ring-offset-2 focus-visible:ring-offset-canvas"
                      : "flex min-h-11 flex-col items-center justify-center rounded-xl border border-line bg-card px-1 py-2 text-ink hover:bg-neutral-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sage focus-visible:ring-offset-2 focus-visible:ring-offset-canvas"
                  }
                >
                  <span className="text-xs font-medium">{formatWeekday(date)}</span>
                  <span className="text-base font-medium leading-none tabular-nums">{dayNumber(date)}</span>
                  {date === DEMO_TODAY ? <span className="text-xs leading-tight">Today</span> : null}
                </button>
              );
            })}
          </div>
        </div>
        <p className="text-sm text-muted">
          Blue mark: still ahead in the demo. Quiet mark: already on the record.
        </p>
      </section>

      <section className="flex flex-col gap-5">
        <SectionHeading title={day === "week" ? "This week" : formatDate(day)} />
        {weekGroups.length === 0 ? (
          <EmptyState
            title="Nothing in this view for that filter."
            action={
              kind !== "all" ? (
                <Button type="button" variant="outline" size="sm" className="min-h-10" onClick={() => setKind("all")}>
                  Show all items
                </Button>
              ) : null
            }
          >
            {kind === "all"
              ? "This demo week has no items for the day you selected."
              : "Try another type, or show every item in the week."}
          </EmptyState>
        ) : (
          <div className="flex flex-col gap-6">
            {weekGroups.map((group) => (
              <div key={group.date} className="flex flex-col gap-3">
                {day === "week" ? (
                  <p className="font-serif text-base font-medium text-ink">{formatDate(group.date)}</p>
                ) : null}
                {agendaBlocks(group.items).map((block) =>
                  block.type === "visit" ? (
                    renderItem(block.item)
                  ) : (
                    <DoseSchedule key={block.items.map((item) => item.id).join("-")} items={block.items} />
                  ),
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {otherItems.length > 0 ? (
        <section className="flex flex-col gap-5">
          <SectionHeading
            title="Other demo dates"
            lede={`Appointments outside ${formatDate(weekDays[0])} – ${formatDate(weekDays[6])}.`}
          />
          <div className="flex flex-col gap-3">
            {otherItems.map((item) => renderItem(item))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

function AgendaCard({
  item,
  noteId,
  open,
  draft,
  savedNote,
  error,
  onOpen,
  onDraft,
  onSubmit,
  onKeyDown,
  onClose,
}: {
  item: AgendaItem;
  noteId: string;
  open: boolean;
  draft: string;
  savedNote?: string;
  error: string | null;
  onOpen: () => void;
  onDraft: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onKeyDown: (event: KeyboardEvent<HTMLFormElement>) => void;
  onClose: () => void;
}) {
  const ahead = isAhead(item);
  const canRequest = item.origin === "appointment" && item.status === "upcoming";
  const fieldId = `${noteId}-${item.id}`;

  return (
    <Card >
      <div className="flex">
        <div
          aria-hidden
          className={
            ahead
              ? "w-1 shrink-0 bg-calm"
              : "w-1 shrink-0 bg-line"
          }
        />
        <div className="min-w-0 flex-1">
          <CardHeader className={savedNote || canRequest ? undefined : "pb-5"}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <CardTitle>{item.title}</CardTitle>
                <CardDescription>
                  {formatDate(item.start)} · {formatTime(item.start)}
                  {item.location ? ` · ${item.location}` : ""}
                </CardDescription>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge tone={KIND_TONE[item.kind]}>{KIND_LABEL[item.kind]}</Badge>
                <Badge tone={statusTone(item.status)}>{statusLabel(item.status)}</Badge>
              </div>
            </div>
          </CardHeader>
          {savedNote || canRequest ? (
          <CardContent className="flex flex-col gap-3">
            {savedNote ? (
              <p className="rounded-2xl border border-line bg-canvas px-4 py-3 text-sm text-ink">
                Demo only. Saved in this session: {savedNote}. No appointment was created or
                changed.
              </p>
            ) : null}
            {canRequest ? (
              <div className="flex flex-col gap-3">
                {open ? (
                  <form
                    className="flex flex-col gap-2"
                    onSubmit={onSubmit}
                    onKeyDown={onKeyDown}
                  >
                    <Label htmlFor={fieldId}>Preferred time note</Label>
                    <Textarea
                      id={fieldId}
                      value={draft}
                      maxLength={240}
                      onChange={(event) => onDraft(event.target.value)}
                      placeholder="Weekday morning, or after 4 pm"
                    />
                    {error ? (
                      <p role="alert" className="text-sm text-amber">
                        {error}
                      </p>
                    ) : null}
                    <p className="text-sm text-muted">
                      Demo only. This note stays in this session and does not book or change an
                      appointment.
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <Button type="submit" size="sm" className="min-h-10">
                        Save note
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="min-h-10"
                        onClick={onClose}
                      >
                        Close
                      </Button>
                    </div>
                  </form>
                ) : (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="min-h-10 self-start"
                    onClick={onOpen}
                  >
                    {savedNote ? "Edit time note" : "Request a different time"}
                  </Button>
                )}
              </div>
            ) : null}
          </CardContent>
          ) : null}
        </div>
      </div>
    </Card>
  );
}
