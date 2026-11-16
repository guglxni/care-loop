import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { EmptyState } from "@/components/layout/EmptyState";
import { PageHeader } from "@/components/layout/PageHeader";
import { SectionHeading } from "@/components/layout/SectionHeading";
import { calls, languageOptions } from "@/data/demo";
import { useDoseTracker } from "@/state/dose-tracker";

const TIME_ZONE = "Asia/Kolkata";
const DEMO_CAPTION = "Demo data. Not medical advice.";
const VOICE_NUMBER_DISPLAY = "+1 423 583 8428";
const VOICE_NUMBER_TEL = "+14235838428";
type Call = (typeof calls)[number];

const linkClass =
  "font-medium text-ink underline decoration-line underline-offset-4 hover:decoration-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sage focus-visible:ring-offset-2 focus-visible:ring-offset-canvas";

function parseIso(iso: string): Date {
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) return new Date(`${iso}T00:00:00+05:30`);
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(iso)) return new Date(`${iso}:00+05:30`);
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(iso)) return new Date(`${iso}+05:30`);
  return new Date(iso);
}

function formatDateTime(iso: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: TIME_ZONE,
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(parseIso(iso));
}

function languageName(value: string): string {
  const match = languageOptions.find((option) => option.code === value || option.label === value);
  return match?.label ?? value;
}

function statusLabel(status: string): string {
  if (status === "completed") return "Completed";
  return status;
}

function statusTone(status: string): "green" | "neutral" {
  return status === "completed" ? "green" : "neutral";
}

const recentCalls = calls
  .slice()
  .sort((a, b) => parseIso(b.at).getTime() - parseIso(a.at).getTime());

function callKey(call: Call): string {
  return call.id;
}

export function CompanionPage() {
  const { queuedCheckIns } = useDoseTracker();

  const followUps = recentCalls.flatMap((call) =>
    call.followUps.map((item, index) => ({
      id: `${callKey(call)}-${index}`,
      text: item,
      at: call.at,
      language: call.language,
    })),
  );

  return (
    <div className="flex w-full min-w-0 flex-col gap-12 text-ink">
      <PageHeader
        title="Companion"
        lede="CareLoop calls you from CityCare about your medicines, your sugar checks, and your next visit. You do not need to press a button."
        note={DEMO_CAPTION}
      />

      <section className="flex flex-col gap-3" aria-labelledby="how-calls-work">
        <SectionHeading
          id="how-calls-work"
          title="How the call works"
          lede="The call comes because your care record says a check-in is due."
        />
        <Card>
          <CardContent className="flex flex-col gap-4">
            <p className="text-sm leading-6 text-ink">
              You do not choose a topic, and you do not start the call. CityCare places it. The call uses the language on your care record.
            </p>
            <ul className="list-disc pl-5 text-sm leading-6 text-ink">
              <li>Medicines, including a dose that is still unconfirmed.</li>
              <li>Sugar checks.</li>
              <li>The next visit.</li>
            </ul>
            <p className="text-sm leading-6 text-muted">
              The companion is not a clinician and will not change a dose.
            </p>
          </CardContent>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>If you want to call in</CardTitle>
          <CardDescription>You do not need this number for a scheduled check-in.</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-6 text-muted">
            The inbound line is{" "}
            <a className={linkClass} href={`tel:${VOICE_NUMBER_TEL}`}>
              {VOICE_NUMBER_DISPLAY}
            </a>
            . This page does not dial it.
          </p>
        </CardContent>
      </Card>

      <section className="flex flex-col gap-3">
        <SectionHeading
          title="Outstanding follow-ups"
          lede="Notes from the demo calls, such as a visit to confirm."
        />
        {followUps.length === 0 ? (
          <EmptyState title="No outstanding follow-ups in the demo calls.">
            Visit confirmations from demo calls will be listed here.
          </EmptyState>
        ) : (
          <Card>
            <CardContent>
              <ul className="flex flex-col">
                {followUps.map((item) => (
                  <li
                    key={item.id}
                    className="flex flex-col gap-1 border-b border-line py-3 first:pt-0 last:border-b-0 last:pb-0"
                  >
                    <span className="text-sm font-medium text-ink">{item.text}</span>
                    <span className="text-sm text-muted">
                      From the call on {formatDateTime(item.at)} · {languageName(item.language)}
                    </span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <SectionHeading
          title="Queued check-ins"
          lede="A dose marked not taken is missed on the care record. That miss queues a medication check-in. CareLoop places the call. You do not start it here."
        />
        {queuedCheckIns.length === 0 ? (
          <EmptyState title="No check-in is queued.">
            A dose marked not taken queues a medication check-in. CareLoop places that call.
          </EmptyState>
        ) : (
          <ul className="flex flex-col gap-3">
            {queuedCheckIns.map((item) => (
              <li key={item.id}>
                <Card>
                  <CardHeader>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <CardTitle>Medication check-in</CardTitle>
                        <CardDescription>
                          {item.medicationName}
                          {item.dose ? ` ${item.dose}` : ""} ·{" "}
                          {formatDateTime(`${item.date}T${item.time}:00+05:30`)}
                        </CardDescription>
                      </div>
                      <Badge tone="amber">Queued</Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm leading-6 text-ink">
                      {item.medicationName} was marked not taken, so the care record queues this check-in. CareLoop places the call.
                    </p>
                  </CardContent>
                </Card>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <SectionHeading title="Recent calls" lede="Notes from the synthetic demo. These are not live calls." />
        {recentCalls.length === 0 ? (
          <EmptyState title="No demo calls yet.">
            Completed demo call notes will be listed here.
          </EmptyState>
        ) : (
          <ul className="flex flex-col gap-3">
            {recentCalls.map((call) => (
              <li key={callKey(call)}>
                <Card>
                  <CardHeader>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <CardTitle>{formatDateTime(call.at)}</CardTitle>
                        <CardDescription>
                          {languageName(call.language)} ·{" "}
                          {new Intl.NumberFormat("en-IN").format(call.durationMin)} min
                        </CardDescription>
                      </div>
                      <Badge tone={statusTone(call.status)}>{statusLabel(call.status)}</Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-3">
                    <p className="text-sm leading-6 text-ink">{call.summary}</p>
                    {call.followUps.length > 0 ? (
                      <div className="flex flex-col gap-2">
                        <h3 className="text-sm font-semibold text-ink">Follow-ups</h3>
                        <ul className="list-disc pl-5 text-sm text-ink">
                          {call.followUps.map((item) => (
                            <li key={item}>{item}</li>
                          ))}
                        </ul>
                      </div>
                    ) : (
                      <p className="text-sm text-muted">No follow-up on this call.</p>
                    )}
                  </CardContent>
                </Card>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
