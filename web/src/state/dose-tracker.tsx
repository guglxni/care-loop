import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react"
import { DEMO_TODAY, doseSlots, medications, type DoseStatus } from "@/data/demo"

type ReportedStatus = Extract<DoseStatus, "taken" | "missed">

export type TrackedDose = (typeof doseSlots)[number] & {
  confirmed: boolean
}

export type QueuedCheckIn = {
  id: string
  slotId: string
  medicationName: string
  dose: string
  date: string
  time: string
}

type DoseTrackerValue = {
  slots: TrackedDose[]
  setStatus: (slotId: string, status: ReportedStatus) => void
  todayAdherence: {
    taken: number
    missed: number
    unknown: number
    scheduled: number
  }
  doseAlerts: string[]
  queuedCheckIns: QueuedCheckIn[]
}

const DoseTrackerContext = createContext<DoseTrackerValue | null>(null)

function medicine(id: string) {
  return medications.find((item) => item.id === id)
}

function medicineName(id: string): string {
  return medicine(id)?.name ?? "Scheduled medicine"
}

export function DoseTrackerProvider({ children }: { children: ReactNode }) {
  const [overrides, setOverrides] = useState<Record<string, ReportedStatus>>({})

  const setStatus = useCallback((slotId: string, status: ReportedStatus) => {
    setOverrides((current) => {
      const slot = doseSlots.find((item) => item.id === slotId)
      if (!slot) return current
      if ((current[slotId] ?? slot.status) === status) return current
      return { ...current, [slotId]: status }
    })
  }, [])

  const value = useMemo<DoseTrackerValue>(() => {
    const slots: TrackedDose[] = doseSlots.map((slot) => ({
      ...slot,
      status: overrides[slot.id] ?? slot.status,
      confirmed: Object.prototype.hasOwnProperty.call(overrides, slot.id),
    }))
    const today = slots.filter((slot) => slot.date === DEMO_TODAY)
    const queuedCheckIns = slots.flatMap((slot) => {
      if (overrides[slot.id] !== "missed") return []
      const medication = medicine(slot.medicationId)
      return [
        {
          id: `check-in-${slot.id}`,
          slotId: slot.id,
          medicationName: medication?.name ?? "Scheduled medicine",
          dose: medication?.dose ?? "",
          date: slot.date,
          time: slot.time,
        },
      ]
    })
    const doseAlerts = [
      ...today
        .filter((slot) => slot.status === "unknown")
        .map(
          (slot) =>
            `The ${medicineName(slot.medicationId)} ${slot.time} slot for today is still unrecorded.`,
        ),
      ...today
        .filter((slot) => slot.status === "missed")
        .map((slot) => {
          const name = medicineName(slot.medicationId)
          if (overrides[slot.id] === "missed") {
            return `The ${name} ${slot.time} slot for today was marked not taken, so it is missed. A medication check-in is queued.`
          }
          return `The ${name} ${slot.time} slot for today is missed.`
        }),
      ...queuedCheckIns
        .filter((item) => item.date !== DEMO_TODAY)
        .map(
          (item) =>
            `${item.medicationName} ${item.time} on ${item.date} was marked not taken, so it is missed. A medication check-in is queued.`,
        ),
    ]

    return {
      slots,
      setStatus,
      todayAdherence: {
        taken: today.filter((slot) => slot.status === "taken").length,
        missed: today.filter((slot) => slot.status === "missed").length,
        unknown: today.filter((slot) => slot.status === "unknown").length,
        scheduled: today.length,
      },
      doseAlerts,
      queuedCheckIns,
    }
  }, [overrides, setStatus])

  return <DoseTrackerContext.Provider value={value}>{children}</DoseTrackerContext.Provider>
}

export function useDoseTracker(): DoseTrackerValue {
  const value = useContext(DoseTrackerContext)
  if (!value) {
    throw new Error("Dose tracker is missing.")
  }
  return value
}
