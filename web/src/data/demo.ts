// Synthetic demo, not medical advice, not clinical recommendations.
// Fixtures for the UI only. Not a real chart. Readings are not classified, and nothing here changes a dose.

export type GlucoseContext = "fasting" | "post_meal" | "other"
export type GlucoseSource = "manual" | "cgm" | "glucometer"
export type BpSource = "manual" | "home_monitor" | "clinic"
export type DoseStatus = "taken" | "missed" | "unknown"

export type GlucoseReading = {
  id: string
  measuredAt: string
  value: number
  unit: "mg/dL"
  context: GlucoseContext
  source: GlucoseSource
}

export type BloodPressureReading = {
  id: string
  measuredAt: string
  systolic: number
  diastolic: number
  pulse: number | null
  unit: "mmHg"
  source: BpSource
}

export type Medication = {
  id: string
  name: string
  dose: string
  frequency: string
  times: string[]
  start: string
  end: string | null
}

export type DoseSlot = {
  id: string
  medicationId: string
  date: string
  time: string
  status: DoseStatus
}

export type CalendarKind = "consultation" | "laboratory" | "medication" | "follow_up"
export type CalendarStatus = "upcoming" | "done"

export type CalendarItem = {
  id: string
  kind: CalendarKind
  title: string
  start: string
  location?: string
  status: CalendarStatus
}

export type ChartDocument = {
  id: string
  name: string
  uploadedAt: string
  kind: "prescription" | "lab_report"
  sizeLabel: string
}

export type CompanionCall = {
  id: string
  at: string
  language: string
  durationMin: number
  summary: string
  followUps: string[]
  status: "completed"
}

export type PendingActivity = {
  id: string
  title: string
  detail: string
  start?: string
}

export const DEMO_TODAY = "2026-11-15"
export const todayIso = DEMO_TODAY

export const demoPatient = {
  preferredName: "Meera Iyer",
  dateOfBirth: "1978-04-12",
  sex: "Female",
  phone: "+91 98400 11223",
  email: "meera.iyer.demo@example.com",
  city: "Indiranagar, Bengaluru",
  preferredLanguage: "hi" as const,
  languageLabel: "Hindi",
  conditions: [
    { name: "Type 2 diabetes", since: "2019-06-01", status: "Ongoing" },
    { name: "Hypertension", since: "2021-02-14", status: "Ongoing" },
  ],
  history: [
    { year: "2019", note: "Type 2 diabetes recorded after repeated high fasting glucose." },
    { year: "2021", note: "Hypertension recorded on repeated home readings." },
    { year: "2024", note: "Annual lab visit completed. No medication change is represented in this demo." },
  ],
  allergies: ["Penicillin"],
  emergencyContact: { name: "Arjun Iyer", relation: "Spouse", phone: "+91 98400 44556" },
  doctor: { name: "Dr. Anika Shah", specialty: "Endocrinology", clinic: "Care Loop Clinic, Bengaluru" },
}

export const languageOptions = [
  { code: "en", label: "English" },
  { code: "hi", label: "Hindi" },
  { code: "kn", label: "Kannada" },
  { code: "ta", label: "Tamil" },
]

export const glucoseReadings: GlucoseReading[] = [
  {
    id: "glc-20261102-fasting",
    measuredAt: "2026-11-02T07:12:00+05:30",
    value: 104,
    unit: "mg/dL",
    context: "fasting",
    source: "glucometer",
  },
  {
    id: "glc-20261103-fasting",
    measuredAt: "2026-11-03T07:08:00+05:30",
    value: 126,
    unit: "mg/dL",
    context: "fasting",
    source: "glucometer",
  },
  {
    id: "glc-20261104-fasting",
    measuredAt: "2026-11-04T07:15:00+05:30",
    value: 119,
    unit: "mg/dL",
    context: "fasting",
    source: "glucometer",
  },
  {
    id: "glc-20261104-post",
    measuredAt: "2026-11-04T14:05:00+05:30",
    value: 158,
    unit: "mg/dL",
    context: "post_meal",
    source: "glucometer",
  },
  {
    id: "glc-20261106-fasting",
    measuredAt: "2026-11-06T07:10:00+05:30",
    value: 182,
    unit: "mg/dL",
    context: "fasting",
    source: "glucometer",
  },
  {
    id: "glc-20261107-fasting",
    measuredAt: "2026-11-07T07:18:00+05:30",
    value: 134,
    unit: "mg/dL",
    context: "fasting",
    source: "glucometer",
  },
  {
    id: "glc-20261108-fasting",
    measuredAt: "2026-11-08T07:06:00+05:30",
    value: 117,
    unit: "mg/dL",
    context: "fasting",
    source: "cgm",
  },
  {
    id: "glc-20261109-fasting",
    measuredAt: "2026-11-09T07:11:00+05:30",
    value: 123,
    unit: "mg/dL",
    context: "fasting",
    source: "glucometer",
  },
  {
    id: "glc-20261110-fasting",
    measuredAt: "2026-11-10T07:09:00+05:30",
    value: 141,
    unit: "mg/dL",
    context: "fasting",
    source: "manual",
  },
  {
    id: "glc-20261111-fasting",
    measuredAt: "2026-11-11T07:14:00+05:30",
    value: 129,
    unit: "mg/dL",
    context: "fasting",
    source: "glucometer",
  },
  {
    id: "glc-20261112-fasting",
    measuredAt: "2026-11-12T07:07:00+05:30",
    value: 116,
    unit: "mg/dL",
    context: "fasting",
    source: "glucometer",
  },
  {
    id: "glc-20261113-fasting",
    measuredAt: "2026-11-13T07:16:00+05:30",
    value: 131,
    unit: "mg/dL",
    context: "fasting",
    source: "glucometer",
  },
  {
    id: "glc-20261113-post",
    measuredAt: "2026-11-13T13:40:00+05:30",
    value: 146,
    unit: "mg/dL",
    context: "post_meal",
    source: "glucometer",
  },
  {
    id: "glc-20261115-fasting",
    measuredAt: "2026-11-15T07:20:00+05:30",
    value: 125,
    unit: "mg/dL",
    context: "fasting",
    source: "glucometer",
  },
]

export const glucoseSchedule = [
  { context: "fasting" as const, expectation: "One fasting reading each morning" },
  { context: "post_meal" as const, expectation: "One post-meal reading on Monday, Wednesday, and Friday" },
]

export const bpReadings: BloodPressureReading[] = [
  {
    id: "bp-20261104",
    measuredAt: "2026-11-04T08:20:00+05:30",
    systolic: 128,
    diastolic: 82,
    pulse: 74,
    unit: "mmHg",
    source: "home_monitor",
  },
  {
    id: "bp-20261106",
    measuredAt: "2026-11-06T08:15:00+05:30",
    systolic: 134,
    diastolic: 86,
    pulse: 78,
    unit: "mmHg",
    source: "home_monitor",
  },
  {
    id: "bp-20261108",
    measuredAt: "2026-11-08T08:28:00+05:30",
    systolic: 122,
    diastolic: 78,
    pulse: 70,
    unit: "mmHg",
    source: "home_monitor",
  },
  {
    id: "bp-20261109",
    measuredAt: "2026-11-09T11:05:00+05:30",
    systolic: 148,
    diastolic: 92,
    pulse: 80,
    unit: "mmHg",
    source: "clinic",
  },
  {
    id: "bp-20261111",
    measuredAt: "2026-11-11T08:18:00+05:30",
    systolic: 130,
    diastolic: 84,
    pulse: 76,
    unit: "mmHg",
    source: "home_monitor",
  },
  {
    id: "bp-20261112",
    measuredAt: "2026-11-12T20:05:00+05:30",
    systolic: 118,
    diastolic: 76,
    pulse: null,
    unit: "mmHg",
    source: "home_monitor",
  },
  {
    id: "bp-20261113",
    measuredAt: "2026-11-13T08:12:00+05:30",
    systolic: 136,
    diastolic: 88,
    pulse: 72,
    unit: "mmHg",
    source: "home_monitor",
  },
  {
    id: "bp-20261115",
    measuredAt: "2026-11-15T08:10:00+05:30",
    systolic: 126,
    diastolic: 80,
    pulse: 71,
    unit: "mmHg",
    source: "home_monitor",
  },
]

export const medications: Medication[] = [
  {
    id: "med-metformin",
    name: "Metformin",
    dose: "500 mg",
    frequency: "Twice daily",
    times: ["08:00", "20:00"],
    start: "2019-06-15",
    end: null,
  },
  {
    id: "med-telmisartan",
    name: "Telmisartan",
    dose: "40 mg",
    frequency: "Once daily",
    times: ["08:00"],
    start: "2021-02-20",
    end: null,
  },
  {
    id: "med-vitamin-d",
    name: "Vitamin D",
    dose: "60000 IU",
    frequency: "Weekly",
    times: ["08:00"],
    start: "2025-01-06",
    end: "2025-03-31",
  },
]

const metforminWeek: ReadonlyArray<readonly [string, string, DoseStatus]> = [
  ["2026-11-09", "08:00", "taken"],
  ["2026-11-09", "20:00", "taken"],
  ["2026-11-10", "08:00", "taken"],
  ["2026-11-10", "20:00", "missed"],
  ["2026-11-11", "08:00", "taken"],
  ["2026-11-11", "20:00", "unknown"],
  ["2026-11-12", "08:00", "taken"],
  ["2026-11-12", "20:00", "taken"],
  ["2026-11-13", "08:00", "taken"],
  ["2026-11-13", "20:00", "taken"],
  ["2026-11-14", "08:00", "taken"],
  ["2026-11-14", "20:00", "missed"],
  ["2026-11-15", "08:00", "taken"],
  ["2026-11-15", "20:00", "unknown"],
]

const telmisartanWeek: ReadonlyArray<readonly [string, string, DoseStatus]> = [
  ["2026-11-09", "08:00", "taken"],
  ["2026-11-10", "08:00", "taken"],
  ["2026-11-11", "08:00", "taken"],
  ["2026-11-12", "08:00", "unknown"],
  ["2026-11-13", "08:00", "taken"],
  ["2026-11-14", "08:00", "taken"],
  ["2026-11-15", "08:00", "taken"],
]

const vitaminDCourse: ReadonlyArray<readonly [string, string, DoseStatus]> = [
  ["2025-01-06", "08:00", "taken"],
  ["2025-01-13", "08:00", "taken"],
  ["2025-01-20", "08:00", "taken"],
  ["2025-01-27", "08:00", "taken"],
  ["2025-02-03", "08:00", "taken"],
  ["2025-02-10", "08:00", "missed"],
  ["2025-02-17", "08:00", "taken"],
  ["2025-02-24", "08:00", "taken"],
  ["2025-03-03", "08:00", "taken"],
  ["2025-03-10", "08:00", "unknown"],
  ["2025-03-17", "08:00", "taken"],
  ["2025-03-24", "08:00", "taken"],
  ["2025-03-31", "08:00", "taken"],
]

function slotsFrom(
  medicationId: string,
  rows: ReadonlyArray<readonly [string, string, DoseStatus]>,
): DoseSlot[] {
  return rows.map(([date, time, status]) => ({
    id: `${medicationId}-${date}-${time.replace(":", "")}`,
    medicationId,
    date,
    time,
    status,
  }))
}

export const doseSlots: DoseSlot[] = [
  ...slotsFrom("med-metformin", metforminWeek),
  ...slotsFrom("med-telmisartan", telmisartanWeek),
  ...slotsFrom("med-vitamin-d", vitaminDCourse),
]

export const calendarItems: CalendarItem[] = [
  {
    id: "cal-consult-2026-10-20",
    kind: "consultation",
    title: "Endocrinology consultation",
    start: "2026-10-20T10:30:00+05:30",
    location: "Care Loop Clinic, Bengaluru",
    status: "done",
  },
  {
    id: "cal-lab-2026-09-18",
    kind: "laboratory",
    title: "Laboratory visit",
    start: "2026-09-18T09:00:00+05:30",
    location: "Care Loop Clinic, Bengaluru",
    status: "done",
  },
  {
    id: "cal-med-2026-11-15-0800",
    kind: "medication",
    title: "Metformin 500 mg and Telmisartan 40 mg",
    start: "2026-11-15T08:00:00+05:30",
    status: "done",
  },
  {
    id: "cal-med-2026-11-15-2000",
    kind: "medication",
    title: "Metformin 500 mg",
    start: "2026-11-15T20:00:00+05:30",
    status: "upcoming",
  },
  {
    id: "cal-follow-2026-11-18",
    kind: "follow_up",
    title: "Confirm Friday laboratory visit",
    start: "2026-11-18T17:00:00+05:30",
    status: "upcoming",
  },
  {
    id: "cal-lab-2026-11-20",
    kind: "laboratory",
    title: "Laboratory visit",
    start: "2026-11-20T09:30:00+05:30",
    location: "Care Loop Clinic, Bengaluru",
    status: "upcoming",
  },
  {
    id: "cal-consult-2026-11-24",
    kind: "consultation",
    title: "Endocrinology consultation",
    start: "2026-11-24T11:00:00+05:30",
    location: "Care Loop Clinic, Bengaluru",
    status: "upcoming",
  },
]

export const appointments = calendarItems

export const documentsPlaceholderNote =
  "Placeholder rows only. These names do not refer to stored files, and no document bytes are included."

export const documents: ChartDocument[] = [
  {
    id: "doc-rx-2026-10-20",
    name: "demo-prescription-2026-10-20.pdf",
    uploadedAt: "2026-10-20T16:10:00+05:30",
    kind: "prescription",
    sizeLabel: "184 KB",
  },
  {
    id: "doc-lab-2026-09-18",
    name: "demo-lab-report-2026-09-18.pdf",
    uploadedAt: "2026-09-18T15:20:00+05:30",
    kind: "lab_report",
    sizeLabel: "242 KB",
  },
  {
    id: "doc-rx-2025-03-31",
    name: "demo-prescription-2025-03-31.pdf",
    uploadedAt: "2025-03-31T12:00:00+05:30",
    kind: "prescription",
    sizeLabel: "156 KB",
  },
]

/** Synthetic demo calls for the companion screen. Not from Bolna, and not real conversations. */
export const calls: CompanionCall[] = [
  {
    id: "demo-call-2026-11-10",
    at: "2026-11-10T18:40:00+05:30",
    language: "Hindi",
    durationMin: 6,
    summary:
      "Demo check-in, not a Bolna call. The synthetic script records that morning medicines were already marked and that a fasting glucose value was already on the chart.",
    followUps: ["Confirm Friday lab visit"],
    status: "completed",
  },
  {
    id: "demo-call-2026-11-07",
    at: "2026-11-07T18:10:00+05:30",
    language: "Hindi",
    durationMin: 4,
    summary:
      "Demo check-in, not a Bolna call. The synthetic script records that a home blood-pressure reading was already entered. No treatment advice is included.",
    followUps: ["Bring the home reading log to the 24 November consultation"],
    status: "completed",
  },
]

function calendarDate(isoTimestamp: string): string {
  return isoTimestamp.slice(0, 10)
}

function shiftIsoDate(isoDate: string, days: number): string {
  const [year, month, day] = isoDate.split("-").map(Number)
  return new Date(Date.UTC(year, month - 1, day) + days * 86_400_000).toISOString().slice(0, 10)
}

function lastIsoDates(endIso: string, count: number): string[] {
  const dates: string[] = []
  for (let offset = count - 1; offset >= 0; offset -= 1) {
    dates.push(shiftIsoDate(endIso, -offset))
  }
  return dates
}

function latestByMeasuredAt<T extends { measuredAt: string }>(rows: readonly T[]): T {
  const latest = rows.reduce<T | null>((current, row) => {
    if (!current || row.measuredAt > current.measuredAt) return row
    return current
  }, null)
  if (!latest) {
    throw new Error("Demo readings are empty.")
  }
  return latest
}

/** ISO dates in the seven days ending on DEMO_TODAY with no fasting row. Data gap only. */
export function missingGlucoseDays(
  readings: readonly { measuredAt: string; context: GlucoseContext }[],
): string[] {
  const covered = new Set(
    readings
      .filter((reading) => reading.context === "fasting")
      .map((reading) => calendarDate(reading.measuredAt)),
  )
  return lastIsoDates(DEMO_TODAY, 7).filter((date) => !covered.has(date))
}

const missingFastingDates = missingGlucoseDays(glucoseReadings)
const yesterday = shiftIsoDate(DEMO_TODAY, -1)
const todaySlots = doseSlots.filter((slot) => slot.date === todayIso)

export const latestGlucose: GlucoseReading = latestByMeasuredAt(glucoseReadings)
export const latestBp: BloodPressureReading = latestByMeasuredAt(bpReadings)

export const todayAdherence: {
  taken: number
  missed: number
  unknown: number
  scheduled: number
} = {
  taken: todaySlots.filter((slot) => slot.status === "taken").length,
  missed: todaySlots.filter((slot) => slot.status === "missed").length,
  unknown: todaySlots.filter((slot) => slot.status === "unknown").length,
  scheduled: todaySlots.length,
}

export const nextConsultation: CalendarItem | null =
  calendarItems
    .filter((item) => item.kind === "consultation" && item.status === "upcoming")
    .sort((a, b) => (a.start < b.start ? -1 : a.start > b.start ? 1 : 0))[0] ?? null

export const pendingActivities: PendingActivity[] = [
  ...missingFastingDates.map((date) => ({
    id: `fasting-gap-${date}`,
    title: "Fasting glucose not recorded",
    detail: date,
  })),
  ...calendarItems
    .filter((item) => item.kind === "laboratory" && item.status === "upcoming")
    .map((item) => ({
      id: item.id,
      title: item.title,
      detail: item.location ?? item.start,
      start: item.start,
    })),
]

export const measurementAlerts: string[] = missingFastingDates.map((date) =>
  date === yesterday
    ? "No fasting glucose recorded yesterday."
    : `No fasting glucose recorded on ${date}.`,
)

export const recentAlerts: string[] = [
  ...measurementAlerts,
  ...todaySlots
    .filter((slot) => slot.status === "unknown")
    .map((slot) => {
      const name =
        medications.find((medication) => medication.id === slot.medicationId)?.name ?? "Scheduled medicine"
      return `The ${name} ${slot.time} slot for today is still unrecorded.`
    }),
]
