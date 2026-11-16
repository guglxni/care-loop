export const MEERA_PATIENT_ID = "11111111-1111-4111-8111-111111111111"
export const RAVI_PATIENT_NAME = "Ravi Sharma"
export const RAVI_RECOGNIZED_PHONE = "+919372501954"
export const RAVI_RECOGNIZED_PHONE_DISPLAY = "+91 93725 01954"
export const RAVI_CALL_RECOGNITION = "CareLoop uses this number to recognize him on calls."
export const EXPECTED_LINK_LABEL = "expected link, API not ready"
export const PHONE_LINKING_UNAVAILABLE = "Phone linking is not available yet."

const E164 = /^\+[1-9]\d{1,14}$/
const LIST_KEYS = ["phone_links", "phoneLinks", "links", "phones", "items", "results"] as const
const PHONE_KEYS = ["phone_e164", "phoneE164", "e164", "phone", "number"] as const
const LABEL_KEYS = ["label", "name"] as const

export type PhoneLink = {
  phoneE164: string
  label: string
}

export type PhoneLinksLoad =
  | { state: "ready"; links: PhoneLink[] }
  | { state: "unavailable"; message: string }
  | { state: "failed"; message: string }

export function normalizeE164(input: string): string {
  return input.trim().replace(/[\s().-]/g, "")
}

export function e164Error(input: string): string | null {
  const value = normalizeE164(input)
  if (!value) return "Enter a phone number in E.164, starting with + and the country code."
  if (!E164.test(value)) return "Use an E.164 number, starting with + and the country code."
  return null
}

export function formatLinkedPhone(phoneE164: string): string {
  const value = normalizeE164(phoneE164)
  if (value === RAVI_RECOGNIZED_PHONE) return RAVI_RECOGNIZED_PHONE_DISPLAY
  return value
}

export function visiblePhoneLinks(patientId: string, links: readonly PhoneLink[]): PhoneLink[] {
  if (patientId !== MEERA_PATIENT_ID) return [...links]
  return links.filter((link) => link.phoneE164 !== RAVI_RECOGNIZED_PHONE)
}

export function raviRecognizedLinkPending(load: PhoneLinksLoad): boolean {
  if (load.state === "ready") {
    return !load.links.some((link) => link.phoneE164 === RAVI_RECOGNIZED_PHONE)
  }
  return true
}

export function demoPhoneRecognition(input: string): string | null {
  if (normalizeE164(input) !== RAVI_RECOGNIZED_PHONE) return null
  return `This number is registered to ${RAVI_PATIENT_NAME}, so call results attach to his chart.`
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function readString(record: Record<string, unknown>, keys: readonly string[]): string | null {
  for (const key of keys) {
    const value = record[key]
    if (typeof value === "string" && value.trim()) return value.trim()
  }
  return null
}

function parseLink(value: unknown): PhoneLink | null {
  if (!isRecord(value)) return null
  const raw = readString(value, PHONE_KEYS)
  if (!raw) return null
  const phoneE164 = normalizeE164(raw)
  if (!E164.test(phoneE164)) return null
  return { phoneE164, label: readString(value, LABEL_KEYS) ?? "" }
}

function dedupe(links: PhoneLink[]): PhoneLink[] {
  const seen = new Set<string>()
  const unique: PhoneLink[] = []
  for (const link of links) {
    if (seen.has(link.phoneE164)) continue
    seen.add(link.phoneE164)
    unique.push(link)
  }
  return unique
}

export function readPhoneLinks(body: unknown): PhoneLink[] | null {
  if (Array.isArray(body)) {
    return dedupe(body.flatMap((item) => {
      const link = parseLink(item)
      return link ? [link] : []
    }))
  }
  if (!isRecord(body)) return null
  for (const key of LIST_KEYS) {
    if (!(key in body)) continue
    const value = body[key]
    if (value == null) return []
    if (!Array.isArray(value)) return null
    return dedupe(value.flatMap((item) => {
      const link = parseLink(item)
      return link ? [link] : []
    }))
  }
  if ("data" in body) return readPhoneLinks(body.data)
  const single = parseLink(body)
  return single ? [single] : null
}

function apiDownMessage(text: string): boolean {
  const normalized = text.toLowerCase()
  return (
    text.includes("The CareLoop API is not running") ||
    normalized.includes("econnrefused") ||
    normalized.includes("http proxy error")
  )
}

function errorMessage(body: unknown, fallback: string): string {
  if (!isRecord(body)) return fallback
  const error = body.error
  if (isRecord(error) && typeof error.message === "string" && error.message.trim()) {
    const details = Array.isArray(error.details)
      ? error.details.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
      : []
    return [error.message.trim(), ...details].join(" ")
  }
  if (typeof body.message === "string" && body.message.trim()) return body.message.trim()
  return fallback
}

function phoneLinksPath(patientId: string): string {
  return `/api/v1/patients/${encodeURIComponent(patientId)}/phone-links`
}

type HttpResult = {
  status: number
  text: string
  json: unknown
}

async function request(path: string, init: RequestInit): Promise<HttpResult> {
  let response: Response
  try {
    response = await fetch(path, {
      ...init,
      cache: "no-store",
      headers: {
        Accept: "application/json",
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...init.headers,
      },
      signal: init.signal ?? AbortSignal.timeout(25000),
    })
  } catch {
    throw new Error("The CareLoop API is not running. The dev proxy targets http://127.0.0.1:5055.")
  }
  const text = await response.text()
  if (apiDownMessage(text)) {
    throw new Error("The CareLoop API is not running. The dev proxy targets http://127.0.0.1:5055.")
  }
  let json: unknown = null
  if (text.trim()) {
    try {
      json = JSON.parse(text) as unknown
    } catch {
      json = null
    }
  }
  return { status: response.status, text, json }
}

export async function loadPhoneLinks(patientId: string): Promise<PhoneLinksLoad> {
  const path = phoneLinksPath(patientId)
  let result: HttpResult
  try {
    result = await request(path, { method: "GET" })
  } catch (error) {
    const message = error instanceof Error && error.message.trim() ? error.message.trim() : "The phone links request failed."
    return { state: "failed", message }
  }
  if (result.status === 404) return { state: "unavailable", message: PHONE_LINKING_UNAVAILABLE }
  if (result.status < 200 || result.status >= 300) {
    return {
      state: "failed",
      message: errorMessage(result.json, `GET ${path} returned HTTP ${result.status}.`),
    }
  }
  const links = readPhoneLinks(result.json)
  if (!links) {
    return { state: "failed", message: `GET ${path} did not return a list of phone links.` }
  }
  return { state: "ready", links }
}

export async function createPhoneLink(
  patientId: string,
  input: { phoneE164: string; label: string },
): Promise<PhoneLink> {
  const phoneE164 = normalizeE164(input.phoneE164)
  const problem = e164Error(phoneE164)
  if (problem) throw new Error(problem)
  const label = input.label.trim()
  if (!label) throw new Error("Enter a label for this number.")
  const path = phoneLinksPath(patientId)
  const result = await request(path, {
    method: "POST",
    body: JSON.stringify({ phone_e164: phoneE164, label }),
  })
  if (result.status === 404) throw new Error(PHONE_LINKING_UNAVAILABLE)
  if (result.status < 200 || result.status >= 300) {
    throw new Error(errorMessage(result.json, `POST ${path} returned HTTP ${result.status}.`))
  }
  const links = readPhoneLinks(result.json)
  const created = links?.find((link) => link.phoneE164 === phoneE164) ?? links?.[0]
  if (created) return created
  return { phoneE164, label }
}
