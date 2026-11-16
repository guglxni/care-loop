import type { ReactNode } from "react";
import { KnowledgeCard } from "@/components/knowledge/KnowledgeCard";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/layout/EmptyState";
import { PageHeader } from "@/components/layout/PageHeader";
import { SectionHeading } from "@/components/layout/SectionHeading";
import { demoPatient } from "@/data/demo";
import { MEERA_PATIENT_ID } from "@/lib/phoneLinks";
import { formatDay } from "@/pages/glucose/GlucoseChart";
import { LinkedPhonesSection } from "@/pages/profile/LinkedPhonesSection";

const linkClass =
  "underline decoration-line underline-offset-4 hover:decoration-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sage focus-visible:ring-offset-2 focus-visible:ring-offset-canvas";

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1 border-b border-line py-4 sm:grid-cols-[11rem_minmax(0,1fr)] sm:items-baseline sm:gap-6">
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="min-w-0 text-ink">{children}</dd>
    </div>
  );
}

function telHref(phone: string): string {
  return `tel:${phone.replace(/\s+/g, "")}`;
}

export function ProfilePage() {
  return (
    <div className="flex w-full min-w-0 flex-col gap-12 text-ink">
      <PageHeader
        title="Profile"
        lede={`Recorded details for ${demoPatient.preferredName}.`}
        note="Demo data. Not medical advice."
      />

      <section>
        <p className="font-serif text-3xl font-medium tracking-tight text-ink">{demoPatient.preferredName}</p>
        <p className="mt-2 text-base text-muted">{demoPatient.city}</p>
        <dl className="mt-6 border-t border-line">
          <Row label="Preferred name">
            <span className="font-serif text-lg font-medium">{demoPatient.preferredName}</span>
          </Row>
          <Row label="Date of birth">{formatDay(demoPatient.dateOfBirth)}</Row>
          <Row label="Sex">{demoPatient.sex}</Row>
          <Row label="City">{demoPatient.city}</Row>
          <Row label="Phone">
            <a className={linkClass} href={telHref(demoPatient.phone)}>
              {demoPatient.phone}
            </a>
          </Row>
          <Row label="Email">
            <a className={linkClass} href={`mailto:${demoPatient.email}`}>
              {demoPatient.email}
            </a>
          </Row>
        </dl>
      </section>

      <LinkedPhonesSection patientId={MEERA_PATIENT_ID} patientName={demoPatient.preferredName} />

      <KnowledgeCard patientId={MEERA_PATIENT_ID} />

      <section className="flex flex-col gap-4">
        <SectionHeading title="Diagnosed conditions" />
        {demoPatient.conditions.length === 0 ? (
          <EmptyState title="No diagnosed conditions recorded in this demo.">
            Conditions added to this chart will be listed with the date they were recorded.
          </EmptyState>
        ) : (
          <ul className="border-t border-line">
            {demoPatient.conditions.map((condition) => (
              <li
                key={condition.name}
                className="flex flex-wrap items-baseline justify-between gap-3 border-b border-line py-4"
              >
                <span className="font-medium text-ink">{condition.name}</span>
                <span className="flex flex-wrap items-center gap-2 text-sm text-muted">
                  <span>Since {formatDay(condition.since)}</span>
                  <Badge tone="neutral">{condition.status}</Badge>
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="flex flex-col gap-4">
        <SectionHeading title="Medical history" />
        {demoPatient.history.length === 0 ? (
          <EmptyState title="No medical history recorded in this demo.">
            Earlier notes for this chart will appear here by year.
          </EmptyState>
        ) : (
          <ol className="flex flex-col">
            {demoPatient.history.map((item) => (
              <li
                key={`${item.year}-${item.note}`}
                className="grid grid-cols-[4.5rem_minmax(0,1fr)] gap-4 border-b border-line py-4 first:border-t"
              >
                <span className="font-serif text-base font-medium text-ink tabular-nums">{item.year}</span>
                <p className="text-sm leading-6 text-ink">{item.note}</p>
              </li>
            ))}
          </ol>
        )}
      </section>

      <div className="grid gap-10 lg:grid-cols-2">
        <section className="flex flex-col gap-4">
          <SectionHeading title="Allergies" />
          {demoPatient.allergies.length === 0 ? (
            <EmptyState title="No allergies recorded in this demo.">
              Known allergies for this chart will be listed here.
            </EmptyState>
          ) : (
            <ul className="flex flex-wrap gap-2">
              {demoPatient.allergies.map((allergy) => (
                <li key={allergy}>
                  <Badge tone="amber">{allergy}</Badge>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="flex flex-col gap-4">
          <SectionHeading title="Emergency contact" />
          <dl className="border-t border-line">
            <Row label="Name">
              <span className="font-serif text-lg font-medium">{demoPatient.emergencyContact.name}</span>
            </Row>
            <Row label="Relation">{demoPatient.emergencyContact.relation}</Row>
            <Row label="Phone">
              <a className={linkClass} href={telHref(demoPatient.emergencyContact.phone)}>
                {demoPatient.emergencyContact.phone}
              </a>
            </Row>
          </dl>
        </section>

        <section className="flex flex-col gap-4">
          <SectionHeading title="Preferred language" />
          <div>
            <p className="font-serif text-2xl font-medium text-ink">{demoPatient.languageLabel}</p>
            <p className="mt-1 text-sm text-muted">{demoPatient.preferredLanguage}</p>
          </div>
        </section>

        <section className="flex flex-col gap-4">
          <SectionHeading title="Treating doctor" />
          <dl className="border-t border-line">
            <Row label="Name">
              <span className="font-serif text-lg font-medium">{demoPatient.doctor.name}</span>
            </Row>
            <Row label="Specialty">{demoPatient.doctor.specialty}</Row>
            <Row label="Clinic">{demoPatient.doctor.clinic}</Row>
          </dl>
        </section>
      </div>
    </div>
  );
}

export default ProfilePage;
