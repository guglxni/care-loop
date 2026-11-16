export const CHECK_INS = [
  {
    purpose: "medication_check",
    choice: "Medicine",
    followThrough: "Medicine check",
    asks: ["Whether you took today's medicine.", "If you missed a dose, what got in the way."],
  },
  {
    purpose: "glucose_check",
    choice: "Glucose",
    followThrough: "Glucose check",
    asks: [
      "Your latest glucose number.",
      "Whether you checked before eating or after a meal.",
      "Whether the number came from a meter, a sensor, or memory.",
    ],
  },
  {
    purpose: "bp_check",
    choice: "Blood pressure",
    followThrough: "Blood pressure",
    asks: ["Your blood pressure numbers.", "Whether you were sitting and still when you measured."],
  },
  {
    purpose: "appointment_reminder",
    choice: "Upcoming visit",
    followThrough: "Next visit",
    asks: ["Whether you can still make the next visit.", "A time that works better, if you need to move it."],
  },
] as const;

export type CheckInPurpose = (typeof CHECK_INS)[number]["purpose"];

export function isCheckInPurpose(value: string | null): value is CheckInPurpose {
  return CHECK_INS.some((item) => item.purpose === value);
}

export function checkInByPurpose(purpose: CheckInPurpose) {
  const match = CHECK_INS.find((item) => item.purpose === purpose);
  if (!match) {
    return CHECK_INS[0];
  }
  return match;
}
