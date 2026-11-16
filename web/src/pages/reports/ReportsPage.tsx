import { useId, useState, type ChangeEvent, type FormEvent } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/field";
import { EmptyState } from "@/components/layout/EmptyState";
import { PageHeader } from "@/components/layout/PageHeader";
import { SectionHeading } from "@/components/layout/SectionHeading";
import { documents, documentsPlaceholderNote } from "@/data/demo";

const TIME_ZONE = "Asia/Kolkata";
const DEMO_CAPTION = "Demo data. Not medical advice.";
type DocumentKind = "prescription" | "lab_report";
type LocalDocument = {
  id: string;
  name: string;
  kind: DocumentKind;
  sizeLabel: string;
};

const KIND_LABEL: Record<DocumentKind, string> = {
  prescription: "Prescription",
  lab_report: "Lab report",
};

const KIND_TONE: Record<DocumentKind, "blue" | "green"> = {
  prescription: "blue",
  lab_report: "green",
};

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

function isKind(value: string): value is DocumentKind {
  return value === "prescription" || value === "lab_report";
}

const history = documents
  .slice()
  .sort((a, b) => b.uploadedAt.localeCompare(a.uploadedAt));

export function ReportsPage() {
  const kindId = useId();
  const fileId = useId();
  const helpId = useId();
  const [kind, setKind] = useState<DocumentKind>("prescription");
  const [fileName, setFileName] = useState<string | null>(null);
  const [inputKey, setInputKey] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [localDocs, setLocalDocs] = useState<LocalDocument[]>([]);

  function onFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    setFileName(file ? file.name : null);
    setError(null);
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!fileName) {
      setError("Choose a file before adding it to the list.");
      return;
    }
    setLocalDocs((current) => [
      {
        id: `local-${current.length + 1}-${fileName}`,
        name: fileName,
        kind,
        sizeLabel: "Not saved",
      },
      ...current,
    ]);
    setFileName(null);
    setError(null);
    setInputKey((key) => key + 1);
  }

  return (
    <div className="flex w-full min-w-0 flex-col gap-12 text-ink">
      <PageHeader
        title="Reports"
        lede="Synthetic prescriptions and lab reports. Previews are unavailable in this demo."
        note={DEMO_CAPTION}
      />

      <section className="flex flex-col gap-5">
        <SectionHeading
          title="Add a document name"
          lede="Storage is not connected. Files are not saved."
        />
        <Card >
          <CardHeader>
            <CardTitle>Upload a prescription or lab report</CardTitle>
            <CardDescription>
              The name is added to a list on this page only. The file is not stored.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form className="flex flex-col gap-4" onSubmit={onSubmit}>
              <div className="flex flex-col gap-2">
                <Label htmlFor={kindId}>Document kind</Label>
                <Select
                  id={kindId}
                  value={kind}
                  onChange={(event) => {
                    if (isKind(event.target.value)) setKind(event.target.value);
                  }}
                >
                  <option value="prescription">Prescription</option>
                  <option value="lab_report">Lab report</option>
                </Select>
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor={fileId}>File</Label>
                <Input
                  key={inputKey}
                  id={fileId}
                  type="file"
                  accept=".pdf,application/pdf,image/*"
                  aria-describedby={helpId}
                  className="h-auto py-2 file:mr-3 file:min-h-10 file:rounded-md file:border-0 file:bg-sage-soft file:px-3 file:py-2 file:text-sm file:font-medium file:text-sage"
                  onChange={onFile}
                />
                <p id={helpId} className="text-sm text-muted">
                  Storage is not connected. Files are not saved.
                </p>
              </div>
              {error ? (
                <p role="alert" className="text-sm text-amber">
                  {error}
                </p>
              ) : null}
              <Button type="submit" className="min-h-10 self-start">
                Add to demo list
              </Button>
            </form>
          </CardContent>
        </Card>

        {localDocs.length > 0 ? (
          <div className="flex flex-col gap-3">
            <h3 className="text-sm font-semibold text-ink">Added in this session</h3>
            <ul className="flex flex-col gap-3" aria-live="polite">
              {localDocs.map((document) => (
                <li key={document.id}>
                  <Card >
                    <CardHeader>
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0">
                          <CardTitle>{document.name}</CardTitle>
                          <CardDescription>
                            {KIND_LABEL[document.kind]} · This session · {document.sizeLabel}
                          </CardDescription>
                        </div>
                        <Badge tone={KIND_TONE[document.kind]}>{KIND_LABEL[document.kind]}</Badge>
                      </div>
                    </CardHeader>
                    <CardContent className="flex flex-col items-start gap-3">
                      <p className="text-sm text-muted">
                        Storage is not connected. Files are not saved.
                      </p>
                      <Button type="button" variant="outline" size="sm" className="min-h-10" disabled>
                        Preview unavailable in demo
                      </Button>
                    </CardContent>
                  </Card>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </section>

      <section className="flex flex-col gap-5">
        <SectionHeading title="Document history" lede={documentsPlaceholderNote} />
        {history.length === 0 ? (
          <EmptyState title="No documents in the demo library.">
            Prescriptions and lab reports for this chart will be listed here. Previews stay unavailable.
          </EmptyState>
        ) : (
          <ul className="flex flex-col gap-3">
            {history.map((document) => (
              <li key={document.id}>
                <Card >
                  <CardHeader>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <CardTitle>{document.name}</CardTitle>
                        <CardDescription>
                          {KIND_LABEL[document.kind]} · {formatDate(document.uploadedAt)} ·{" "}
                          {document.sizeLabel}
                        </CardDescription>
                      </div>
                      <Badge tone={KIND_TONE[document.kind]}>{KIND_LABEL[document.kind]}</Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <Button type="button" variant="outline" size="sm" className="min-h-10" disabled>
                      Preview unavailable in demo
                    </Button>
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
