export const API_DOWN_MESSAGE = "The CareLoop API is not running. The dev proxy targets http://127.0.0.1:5055."
export const KNOWLEDGE_ROUTE_MISSING = "The knowledge route is not on this API yet."
export const KNOWLEDGE_ON_REQUEST = "The page is generated from the current chart when requested."
export const KNOWLEDGE_REBUILT = "The knowledge page was rebuilt."
export const BOLNA_RAG_UPDATED = "The Bolna RAG index updated."

const BUILT_KEYS = [
  "last_built_at",
  "lastBuiltAt",
  "built_at",
  "builtAt",
  "rebuilt_at",
  "rebuiltAt",
  "generated_at",
  "generatedAt",
  "last_built",
  "lastBuilt",
] as const

const MARKDOWN_KEYS = ["markdown", "md", "content", "body", "text", "facts"] as const
const WRAPPER_KEYS = ["knowledge", "data", "result", "page"] as const
const BOLNA_ID_KEYS = [
  "bolna_id",
  "bolnaId",
  "bolna_knowledgebase_id",
  "bolnaKnowledgebaseId",
  "bolna_knowledge_base_id",
  "bolnaKnowledgeBaseId",
  "bolna_kb_id",
  "bolnaKbId",
  "bolna_rag_id",
  "bolnaRagId",
  "bolna_vector_id",
  "bolnaVectorId",
] as const

export type KnowledgeLoad =
  | { state: "down" }
  | { state: "missing" }
  | { state: "error"; raw: string }
  | { state: "ready"; builtAt: string | null; markdown: string | null }

export type KnowledgeRefresh =
  | { ok: true; builtAt: string | null; markdown: string | null; bolnaId: string | null }
  | { ok: false; raw: string }

type HttpResult = {
  status: number
  path: string
  text: string
  json: unknown
  lastModified: string | null
}

export function knowledgePath(patientId: string): string {
  return `/api/v1/patients/${encodeURIComponent(patientId)}/knowledge`
}

export function knowledgeRefreshPath(patientId: string): string {
  return `${knowledgePath(patientId)}/refresh`
}

export function formatBuiltAt(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date)
}

export function formatKnowledgeError(result: Pick<HttpResult, "status" | "path" | "text">): string {
  return `HTTP ${result.status} ${result.path}\n${rawBody(result.text)}`
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function isTimeout(error: unknown): boolean {
  return error instanceof DOMException && (error.name === "TimeoutError" || error.name === "AbortError")
}

function isApiDownText(text: string): boolean {
  const normalized = text.toLowerCase()
  return (
    text.includes("The CareLoop API is not running") ||
    normalized.includes("econnrefused") ||
    normalized.includes("http proxy error") ||
    normalized.includes("connect econnrefused")
  )
}

function parseJson(text: string): unknown {
  if (!text.trim()) return null
  try {
    return JSON.parse(text) as unknown
  } catch {
    return null
  }
}

function rawBody(text: string): string {
  const trimmed = text.trim()
  if (!trimmed) return "(empty body)"
  if (trimmed.length > 8000) return `${trimmed.slice(0, 8000)}\n…`
  return trimmed
}

function blankToNull(value: string | null | undefined): string | null {
  if (!value) return null
  const trimmed = value.trim()
  if (!trimmed || trimmed === "null") return null
  return trimmed
}

function readText(record: Record<string, unknown>, keys: readonly string[]): string | null {
  for (const key of keys) {
    const value = record[key]
    if (typeof value === "string" && value.trim() && value.trim() !== "null") return value.trim()
  }
  return null
}

function readString(record: Record<string, unknown>, keys: readonly string[]): string | null {
  const text = readText(record, keys)
  if (text) return text
  for (const key of keys) {
    const value = record[key]
    if (typeof value === "number" && Number.isFinite(value)) return String(value)
  }
  return null
}

function readMarkdown(value: unknown, depth = 0): string | null {
  if (typeof value === "string") return blankToNull(value)
  if (!isRecord(value) || depth > 3) return null
  const direct = readText(value, MARKDOWN_KEYS)
  if (direct) return direct
  for (const key of WRAPPER_KEYS) {
    if (!(key in value)) continue
    const nested = readMarkdown(value[key], depth + 1)
    if (nested) return nested
  }
  return null
}

function readBuiltAt(value: unknown, depth = 0): string | null {
  if (!isRecord(value) || depth > 3) return null
  const direct = readString(value, BUILT_KEYS)
  if (direct) return direct
  for (const key of WRAPPER_KEYS) {
    if (!(key in value)) continue
    const nested = readBuiltAt(value[key], depth + 1)
    if (nested) return nested
  }
  return null
}

function isBolnaContainer(key: string): boolean {
  const normalized = key.toLowerCase().replace(/[_-]/g, "")
  return (
    normalized === "bolna" ||
    normalized === "bolnaknowledgebase" ||
    normalized === "bolnaknowledge" ||
    normalized === "bolnarag" ||
    normalized === "bolnavector"
  )
}

export function readBolnaId(value: unknown, depth = 0): string | null {
  if (!isRecord(value) || depth > 3) return null
  const direct = readString(value, BOLNA_ID_KEYS)
  if (direct) return direct
  for (const [key, child] of Object.entries(value)) {
    if (!isBolnaContainer(key) || !isRecord(child)) continue
    const nestedId = readString(child, ["id", "knowledgebase_id", "knowledgebaseId", "rag_id", "vector_id"])
    if (nestedId) return nestedId
  }
  for (const key of WRAPPER_KEYS) {
    if (!(key in value)) continue
    const nested = readBolnaId(value[key], depth + 1)
    if (nested) return nested
  }
  return null
}

function parsePage(result: HttpResult): { builtAt: string | null; markdown: string | null; bolnaId: string | null } {
  const markdown = readMarkdown(result.json) ?? (result.json == null ? blankToNull(result.text) : null)
  return {
    builtAt: readBuiltAt(result.json) ?? blankToNull(result.lastModified),
    markdown,
    bolnaId: readBolnaId(result.json),
  }
}

async function request(path: string, init: RequestInit): Promise<HttpResult> {
  let response: Response
  try {
    response = await fetch(path, {
      ...init,
      cache: "no-store",
      headers: {
        Accept: "application/json, text/markdown;q=0.9, text/plain;q=0.8",
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...init.headers,
      },
      signal: init.signal ?? AbortSignal.timeout(25000),
    })
  } catch (error) {
    if (isTimeout(error)) throw new Error(`The request to ${path} timed out.`)
    throw new Error(API_DOWN_MESSAGE)
  }

  const text = await response.text()
  if (isApiDownText(text)) throw new Error(API_DOWN_MESSAGE)
  return {
    status: response.status,
    path,
    text,
    json: parseJson(text),
    lastModified: response.headers.get("Last-Modified"),
  }
}

export async function loadKnowledge(patientId: string): Promise<KnowledgeLoad> {
  const path = knowledgePath(patientId)
  let result: HttpResult
  try {
    result = await request(path, { method: "GET" })
  } catch (error) {
    if (error instanceof Error && error.message === API_DOWN_MESSAGE) return { state: "down" }
    const message = error instanceof Error && error.message.trim() ? error.message.trim() : "The knowledge request failed."
    return { state: "error", raw: message }
  }

  if (result.status === 404) return { state: "missing" }
  if (result.status < 200 || result.status >= 300) {
    return { state: "error", raw: formatKnowledgeError(result) }
  }
  const page = parsePage(result)
  return { state: "ready", builtAt: page.builtAt, markdown: page.markdown }
}

export async function refreshKnowledge(patientId: string): Promise<KnowledgeRefresh> {
  const path = knowledgeRefreshPath(patientId)
  try {
    const result = await request(path, { method: "POST", body: "{}" })
    if (result.status < 200 || result.status >= 300) {
      return { ok: false, raw: formatKnowledgeError(result) }
    }
    const page = parsePage(result)
    return { ok: true, builtAt: page.builtAt, markdown: page.markdown, bolnaId: page.bolnaId }
  } catch (error) {
    const message = error instanceof Error && error.message.trim() ? error.message.trim() : "The knowledge refresh failed."
    return { ok: false, raw: message }
  }
}

export function mergeKnowledge(loaded: KnowledgeLoad, refreshed: Extract<KnowledgeRefresh, { ok: true }>): KnowledgeLoad {
  if (loaded.state === "missing") return loaded
  if (loaded.state !== "ready") {
    if (!refreshed.builtAt && !refreshed.markdown) return loaded
    return { state: "ready", builtAt: refreshed.builtAt, markdown: refreshed.markdown }
  }
  return {
    state: "ready",
    builtAt: refreshed.builtAt ?? loaded.builtAt,
    markdown: loaded.markdown ?? refreshed.markdown,
  }
}
