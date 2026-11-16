import type { ReactNode } from "react";
import { AbsoluteFill, Img, Sequence, staticFile, useCurrentFrame, interpolate } from "remotion";
import { loadFont as loadSans } from "@remotion/google-fonts/SourceSans3";
import { loadFont as loadSerif } from "@remotion/google-fonts/SourceSerif4";
import { theme } from "./theme";

const sans = loadSans("normal", { weights: ["400", "600"], subsets: ["latin"] }).fontFamily;
const serif = loadSerif("normal", { weights: ["600"], subsets: ["latin"] }).fontFamily;

const SLIDE = 120;

function rise(frame: number) {
  return {
    opacity: interpolate(frame, [0, 16], [0, 1], { extrapolateRight: "clamp" }),
    transform: `translateY(${interpolate(frame, [0, 16], [24, 0], { extrapolateRight: "clamp" })}px)`,
  };
}

function Chrome({ n, children }: { n: string; children: ReactNode }) {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: theme.canvas, color: theme.ink, fontFamily: sans, padding: "56px 72px 48px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", gap: 14, alignItems: "center", fontFamily: serif, fontSize: 32, fontWeight: 600 }}>
          <div style={{ width: 44, height: 44, borderRadius: 12, background: theme.sage }} />
          Care Loop
        </div>
        <div style={{ fontSize: 28, color: theme.muted, fontVariantNumeric: "tabular-nums" }}>{n}</div>
      </div>
      <div style={{ marginTop: 28, ...rise(frame) }}>{children}</div>
    </AbsoluteFill>
  );
}

function Title({ children }: { children: ReactNode }) {
  return (
    <h1 style={{ margin: 0, fontFamily: serif, fontSize: 72, fontWeight: 600, letterSpacing: "-0.03em", lineHeight: 1 }}>
      {children}
    </h1>
  );
}

function Table({ headers, rows }: { headers: string[]; rows: string[][] }) {
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", background: theme.card, borderRadius: 16, overflow: "hidden", marginTop: 24, fontVariantNumeric: "tabular-nums" }}>
      <thead>
        <tr>
          {headers.map((header) => (
            <th key={header} style={{ textAlign: "left", padding: "16px 22px", fontSize: 24, letterSpacing: "0.06em", textTransform: "uppercase", color: theme.muted, borderBottom: `1px solid ${theme.line}` }}>
              {header}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.join("-")}>
            {row.map((cell) => (
              <td key={cell} style={{ padding: "14px 22px", fontSize: 30, borderBottom: `1px solid ${theme.line}` }}>
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const slides = [
  () => (
    <Chrome n="01">
      <div style={{ display: "grid", gridTemplateColumns: "1.05fr 0.95fr", gap: 36, marginTop: 40 }}>
        <div>
          <div style={{ color: theme.sage, fontWeight: 700, letterSpacing: "0.08em", fontSize: 24 }}>TYPE 2 DIABETES AND HYPERTENSION</div>
          <div style={{ fontFamily: serif, fontSize: 84, fontWeight: 600, letterSpacing: "-0.03em", lineHeight: 0.98, marginTop: 16 }}>
            The chart, then the check-in.
          </div>
          <p style={{ fontSize: 36, color: theme.muted, lineHeight: 1.25, maxWidth: 760 }}>
            Care Loop keeps the record in the patient’s language, and asks only when a dose or a reading is still missing.
          </p>
        </div>
        <Img src={staticFile("hero.jpg")} style={{ width: "100%", height: 640, objectFit: "cover", borderRadius: 16 }} />
      </div>
    </Chrome>
  ),
  () => (
    <Chrome n="02">
      <Title>One loop, three beats.</Title>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 22, marginTop: 36 }}>
        {[
          ["01", "Record", "Glucose, pressure, medicines, and the next visit live on the chart."],
          ["02", "Mark", "She confirms a dose, or leaves it not taken."],
          ["03", "Ask", "A miss is not counted as taken. That queues the check-in."],
        ].map(([n, title, body]) => (
          <div key={n} style={{ background: theme.card, border: `1px solid ${theme.line}`, borderRadius: 16, padding: 28 }}>
            <div style={{ fontFamily: serif, fontSize: 42, color: theme.sage }}>{n}</div>
            <div style={{ fontFamily: serif, fontSize: 40, marginTop: 8 }}>{title}</div>
            <p style={{ fontSize: 30, color: theme.muted }}>{body}</p>
          </div>
        ))}
      </div>
    </Chrome>
  ),
  () => (
    <Chrome n="03">
      <Title>What the app holds.</Title>
      <Table
        headers={["Surface", "What it holds", "What the person does"]}
        rows={[
          ["Today", "Latest sugar, pressure, adherence, next visit", "Reads the demo day"],
          ["Glucose", "mg/dL, time, context, source", "Keeps fasting separate"],
          ["Blood pressure", "mmHg, time, source, optional pulse", "Keeps home and clinic labeled"],
          ["Medicines", "Schedule and taken or not taken", "A miss queues a check-in"],
          ["Calendar", "Visits, labs, and dose times", "Sees the week"],
          ["Companion", "Language and queued check-ins", "Takes the call"],
          ["Data sources", "Synthetic, manual, device", "Sees where a row came from"],
          ["Demo", "Scripted scenarios for the clinic", "The operator starts it"],
        ]}
      />
    </Chrome>
  ),
  () => (
    <Chrome n="04">
      <Title>Today, 15 Nov 2026.</Title>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginTop: 28 }}>
        {[
          ["Glucose", "125", "mg/dL · fasting · glucometer · 7:20 am"],
          ["Blood pressure", "126/80", "mmHg · pulse 71 · home monitor · 8:10 am"],
          ["Taken", "2", "of 3 scheduled doses"],
          ["Unknown", "1", "Metformin 8:00 pm, not yet marked"],
        ].map(([label, value, detail]) => (
          <div key={label} style={{ background: theme.card, border: `1px solid ${theme.line}`, borderRadius: 16, padding: 28 }}>
            <div style={{ color: theme.sage, fontWeight: 700, letterSpacing: "0.08em" }}>{label.toUpperCase()}</div>
            <div style={{ fontFamily: serif, fontSize: 72, fontVariantNumeric: "tabular-nums" }}>{value}</div>
            <div style={{ fontSize: 28, color: theme.muted }}>{detail}</div>
          </div>
        ))}
      </div>
    </Chrome>
  ),
  () => (
    <Chrome n="05">
      <Title>Readings keep their origin.</Title>
      <Table
        headers={["When", "Measure", "Value", "Context", "Source"]}
        rows={[
          ["15 Nov, 7:20 am", "Glucose", "125 mg/dL", "Fasting", "Glucometer"],
          ["15 Nov, 8:10 am", "Blood pressure", "126/80", "Pulse 71", "Home monitor"],
          ["14 Nov", "Glucose", "—", "Fasting", "Not recorded"],
          ["13 Nov, 8:12 am", "Blood pressure", "136/88", "Pulse 72", "Home monitor"],
        ]}
      />
    </Chrome>
  ),
  () => (
    <Chrome n="06">
      <Title>Mark the dose. Or don’t.</Title>
      <Table
        headers={["Medicine", "When", "Status"]}
        rows={[
          ["Metformin 500 mg", "8:00 am", "Taken"],
          ["Telmisartan 40 mg", "8:00 am", "Taken"],
          ["Metformin 500 mg", "8:00 pm", "Not taken"],
        ]}
      />
      <p style={{ fontSize: 32, color: theme.muted, marginTop: 20 }}>
        Not recorded as taken. Missed on the dashboard, so a check-in is queued.
      </p>
    </Chrome>
  ),
  () => (
    <Chrome n="07">
      <div style={{ display: "grid", gridTemplateColumns: "1.1fr 0.9fr", gap: 28 }}>
        <div>
          <Title>The call has a reason.</Title>
          <p style={{ fontSize: 34, color: theme.muted }}>CareLoop calls about medicines, sugar checks, and the next visit.</p>
          <Table
            headers={["Language", "Use"]}
            rows={[
              ["Hindi", "Preferred for the demo profile"],
              ["English", "Available for the check-in"],
              ["Tamil", "Available for the check-in"],
              ["Kannada", "Available for the check-in"],
            ]}
          />
        </div>
        <Img src={staticFile("call.jpg")} style={{ width: "100%", height: 760, objectFit: "cover", borderRadius: 16, marginTop: 8 }} />
      </div>
    </Chrome>
  ),
  () => (
    <Chrome n="08">
      <Title>Three origins. No blended rows.</Title>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
        <Table
          headers={["Label", "Meaning"]}
          rows={[
            ["Synthetic", "Demo chart data, not a device"],
            ["Manual", "Entered by a person"],
            ["Device", "Reported by a connector such as Nightscout"],
          ]}
        />
        <Img src={staticFile("devices.jpg")} style={{ width: "100%", height: 520, objectFit: "cover", borderRadius: 16 }} />
      </div>
    </Chrome>
  ),
  () => (
    <Chrome n="09">
      <Title>The week, and the file drawer.</Title>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginTop: 28 }}>
        {[
          ["Calendar", "Consultations, laboratory visits, and the dose times already on the schedule."],
          ["Reports", "Synthetic prescription and lab file names. Previews are not stored charts."],
          ["Profile", "Name, conditions, language, and the phones the call may use."],
          ["Clinic demo", "The operator starts a scripted scenario. The patient does not press start."],
        ].map(([title, body]) => (
          <div key={title} style={{ background: theme.card, border: `1px solid ${theme.line}`, borderRadius: 16, padding: 28 }}>
            <div style={{ color: theme.sage, fontWeight: 700, letterSpacing: "0.08em" }}>{title.toUpperCase()}</div>
            <p style={{ fontSize: 32, color: theme.muted }}>{body}</p>
          </div>
        ))}
      </div>
    </Chrome>
  ),
  () => (
    <Chrome n="10">
      <Title>Who writes what.</Title>
      <Table
        headers={["Piece", "Job", "Does not"]}
        rows={[
          ["Patient app", "Shows the chart and the dose marks", "Invent a reading"],
          ["Flask", "Writes readings and the call context", "Diagnose"],
          ["Postgres", "Holds the clinical record", "Place the call"],
          ["Intelligence", "Names gaps and priorities", "Change a medicine"],
          ["Bolna", "Places and understands the check-in", "Become the chart"],
        ]}
      />
    </Chrome>
  ),
  () => (
    <Chrome n="11">
      <div style={{ marginTop: 120 }}>
        <div style={{ color: theme.sage, fontWeight: 700, letterSpacing: "0.08em" }}>THE RULE</div>
        <div style={{ fontFamily: serif, fontSize: 88, fontWeight: 600, letterSpacing: "-0.03em", lineHeight: 0.98 }}>
          A miss is why we call.
        </div>
        <p style={{ fontSize: 40, color: theme.muted, maxWidth: 1200 }}>
          Taken is recorded. Not taken is missed. The dashboard leaves it out of the taken count, and the companion queues the check-in.
        </p>
        <p style={{ fontSize: 28, color: theme.muted }}>Synthetic demo data. Not medical advice. This film does not place a phone call.</p>
      </div>
    </Chrome>
  ),
];

export const Deck = () => {
  return (
    <AbsoluteFill style={{ background: theme.canvas }}>
      {slides.map((Slide, index) => (
        <Sequence key={index} from={index * SLIDE} durationInFrames={SLIDE}>
          <Slide />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
