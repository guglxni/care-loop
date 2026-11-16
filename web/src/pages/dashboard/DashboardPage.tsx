import { Link } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/layout/EmptyState";
import { PageHeader } from "@/components/layout/PageHeader";
import { SectionHeading } from "@/components/layout/SectionHeading";
import {
  DEMO_TODAY,
  demoPatient,
  latestBp,
  latestGlucose,
  medications,
  nextConsultation,
  measurementAlerts,
  pendingActivities,
} from "@/data/demo";
import { useDoseTracker, type TrackedDose } from "@/state/dose-tracker";
import { bpSourceLabel } from "@/pages/blood-pressure/BloodPressureChart";
import { formatDay, formatWhen, glucoseContextLabel, glucoseSourceLabel } from "@/pages/glucose/GlucoseChart";
import { TrendCharts } from "@/pages/dashboard/TrendCharts";

const followLink =
  "font-medium text-ink underline decoration-line underline-offset-4 hover:decoration-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sage focus-visible:ring-offset-2 focus-visible:ring-offset-canvas";

const ADHERENCE = [
  { key: "scheduled", label: "Scheduled" },
  { key: "taken", label: "Taken" },
  { key: "missed", label: "Missed" },
  { key: "unknown", label: "Unknown" },
] as const;

function formatDetail(value: string): string {
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return formatDay(value);
  return value.replace(
    /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?/g,
    (iso) => formatWhen(iso),
  );
}

function formatClock(clock: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(`${DEMO_TODAY}T${clock}:00+05:30`));
}

function doseLabel(slot: TrackedDose): string {
  const medication = medications.find((item) => item.id === slot.medicationId);
  const name = medication ? `${medication.name} ${medication.dose}` : "Scheduled medicine";
  return `${name} at ${formatClock(slot.time)}`;
}

function medicineFollowThrough(slots: TrackedDose[]): string {
  const pending = slots.filter((slot) => slot.date === DEMO_TODAY && slot.status !== "taken");
  if (pending.length === 0) {
    return "Today's doses are marked taken. The companion calls about a medicine when the care record still has one unconfirmed.";
  }
  return pending
    .map((slot) => {
      const label = doseLabel(slot);
      if (slot.status === "missed") {
        return `${label} was marked not taken. The companion will call about that dose.`;
      }
      return `${label} is still unconfirmed. The companion will call about that dose.`;
    })
    .join(" ");
}

function withLocalDates(text: string): string {
  return text
    .replace(/\b\d{4}-\d{2}-\d{2}\b/g, (iso) => formatDay(iso))
    .replace(/\b(?:[01]\d|2[0-3]):[0-5]\d\b/g, (clock) => formatClock(clock));
}

function ReadingFigure({
  label,
  value,
  unit,
  detail,
  when,
}: {
  label: string;
  value: string;
  unit: string;
  detail: string;
  when: string;
}) {
  return (
    <article className="flex h-full flex-col bg-card px-6 py-6">
      <h3 className="text-sm font-medium text-muted">{label}</h3>
      <p className="mt-4 flex items-baseline gap-2">
        <span className="font-serif text-4xl font-medium tracking-tight text-ink tabular-nums">{value}</span>
        <span className="text-sm text-muted">{unit}</span>
      </p>
      <p className="mt-4 text-sm leading-6 text-ink">{detail}</p>
      <p className="mt-1 text-sm text-muted">{when}</p>
    </article>
  );
}

export function DashboardPage() {
  const { todayAdherence, doseAlerts, slots } = useDoseTracker();
  const alerts = [...measurementAlerts, ...doseAlerts];
  const sugarContext = latestGlucose.context === "other" ? "" : `${glucoseContextLabel(latestGlucose.context).toLowerCase()} `;
  const followThrough = [
    {
      title: "Medicines",
      detail: medicineFollowThrough(slots),
    },
    {
      title: "Sugar checks",
      detail: `The companion will ask about sugar checks. The latest one on this chart is a ${sugarContext}reading of ${latestGlucose.value} ${latestGlucose.unit}, recorded ${formatWhen(latestGlucose.measuredAt)}.`,
    },
    {
      title: "Next visit",
      detail: nextConsultation
        ? `The companion will ask about the next visit: ${nextConsultation.title} on ${formatWhen(nextConsultation.start)}.`
        : "No upcoming visit is on this chart.",
    },
  ];

  return (
    <div className="flex w-full min-w-0 flex-col gap-12 text-ink">
      <PageHeader
        title="Dashboard"
        lede={`A snapshot of the demo chart for ${formatDay(DEMO_TODAY)}.`}
        note="Demo data. Not medical advice."
      />

      <section className="flex flex-col gap-8 border-b border-line pb-10">
        <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div className="min-w-0">
            <h2 className="font-serif text-3xl font-medium tracking-tight text-ink">{demoPatient.preferredName}</h2>
            <p className="mt-2 text-base text-muted">{demoPatient.city}</p>
          </div>
          <div className="min-w-0">
            <p className="text-sm text-muted">Preferred language</p>
            <p className="mt-1 text-base font-medium text-ink">{demoPatient.languageLabel}</p>
          </div>
        </div>
        {demoPatient.conditions.length === 0 ? (
          <EmptyState title="No conditions recorded in this demo.">
            Diagnosed conditions for this chart will be listed here.
          </EmptyState>
        ) : (
          <ul className="flex flex-wrap gap-2">
            {demoPatient.conditions.map((condition) => (
              <li key={condition.name}>
                <Badge tone="neutral">{condition.name}</Badge>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="flex flex-col gap-5" aria-labelledby="today-heading">
        <SectionHeading id="today-heading" title="Today" lede="Latest readings, today’s medicines, and the next visit." />
        <div className="grid grid-cols-1 gap-px overflow-hidden rounded-2xl border border-line bg-line md:grid-cols-2">
          <ReadingFigure
            label="Glucose"
            value={String(latestGlucose.value)}
            unit={latestGlucose.unit}
            detail={`${glucoseContextLabel(latestGlucose.context)} · ${glucoseSourceLabel(latestGlucose.source)}`}
            when={formatWhen(latestGlucose.measuredAt)}
          />
          <ReadingFigure
            label="Blood pressure"
            value={`${latestBp.systolic}/${latestBp.diastolic}`}
            unit={latestBp.unit}
            detail={`${latestBp.pulse == null ? "Pulse not recorded" : `Pulse ${latestBp.pulse}`} · ${bpSourceLabel(latestBp.source)}`}
            when={formatWhen(latestBp.measuredAt)}
          />
          <div className="bg-card px-6 py-6">
            <h3 className="text-sm font-medium text-muted">Adherence</h3>
            <p className="mt-2 max-w-prose text-sm leading-6 text-muted">
              Counts for today&apos;s scheduled medicines. A dose marked not taken is missed here.
            </p>
            <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
              {ADHERENCE.map((item) => (
                <div key={item.key}>
                  <dt className="text-sm text-muted">{item.label}</dt>
                  <dd className="mt-1 font-serif text-3xl font-medium text-ink tabular-nums">
                    {todayAdherence[item.key]}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
          <div className="bg-card px-6 py-6">
            <h3 className="text-sm font-medium text-muted">Next consultation</h3>
            <p className="mt-2 text-sm leading-6 text-muted">The next consultation in the demo calendar.</p>
            {nextConsultation ? (
              <div className="mt-5 flex flex-col items-start gap-2">
                <p className="font-medium text-ink">{nextConsultation.title}</p>
                <p className="text-sm text-muted">{formatWhen(nextConsultation.start)}</p>
                {nextConsultation.location ? <p className="text-sm text-muted">{nextConsultation.location}</p> : null}
                <Badge tone={nextConsultation.status === "upcoming" ? "blue" : "neutral"}>
                  {nextConsultation.status === "upcoming" ? "Upcoming" : "Done"}
                </Badge>
              </div>
            ) : (
              <div className="mt-5">
                <EmptyState title="No upcoming consultation in this demo.">
                  Visits still ahead on the demo calendar will appear here.
                </EmptyState>
              </div>
            )}
          </div>
        </div>
      </section>

      <section className="flex flex-col gap-5" aria-labelledby="follow-through-heading">
        <SectionHeading
          id="follow-through-heading"
          title="Today's follow-through"
          lede="What the companion will call about. The patient does not start the call."
        />
        <Card>
          <CardContent className="flex flex-col gap-4">
            <ul className="flex flex-col">
              {followThrough.map((item) => (
                <li
                  key={item.title}
                  className="flex flex-col gap-1 border-b border-line py-3 first:pt-0 last:border-b-0 last:pb-0"
                >
                  <p className="text-sm font-medium text-ink">{item.title}</p>
                  <p className="text-sm leading-6 text-muted">{item.detail}</p>
                </li>
              ))}
            </ul>
            <p className="text-sm leading-6 text-muted">
              A clinic operator can{" "}
              <Link className={followLink} to="/demo">
                open the clinic demo
              </Link>{" "}
              to start a scripted scenario.
            </p>
          </CardContent>
        </Card>
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Pending activities</CardTitle>
            <CardDescription>Items still open on the demo day.</CardDescription>
          </CardHeader>
          <CardContent>
            {pendingActivities.length === 0 ? (
              <EmptyState title="No pending activities in this demo.">
                Open items for this demo day will be listed here.
              </EmptyState>
            ) : (
              <ul className="flex flex-col divide-y divide-line">
                {pendingActivities.map((activity) => (
                  <li key={activity.id} className="py-4 text-sm leading-6 first:pt-0 last:pb-0">
                    <p className="font-medium text-ink">{activity.title}</p>
                    <p className="mt-1 text-muted">{formatDetail(activity.detail)}</p>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent alerts</CardTitle>
            <CardDescription>Missing data and schedule notes from the demo.</CardDescription>
          </CardHeader>
          <CardContent>
            {alerts.length === 0 ? (
              <EmptyState title="No recent alerts.">
                Missing readings and schedule notes will show up here.
              </EmptyState>
            ) : (
              <ul className="flex flex-col divide-y divide-line">
                {alerts.map((alert) => (
                  <li key={alert} className="py-4 text-sm leading-6 text-ink first:pt-0 last:pb-0">
                    {withLocalDates(alert)}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      <section className="flex min-w-0 flex-col gap-5" aria-labelledby="trends-heading">
        <SectionHeading
          id="trends-heading"
          title="Trends"
          lede="Each glucose source is its own line. Blood pressure shows systolic and diastolic."
        />
        <TrendCharts />
      </section>
    </div>
  );
}

export default DashboardPage;
