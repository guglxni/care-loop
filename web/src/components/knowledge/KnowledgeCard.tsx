import { useEffect, useId, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { SectionHeading } from "@/components/layout/SectionHeading"
import {
  API_DOWN_MESSAGE,
  BOLNA_RAG_UPDATED,
  KNOWLEDGE_ON_REQUEST,
  KNOWLEDGE_REBUILT,
  KNOWLEDGE_ROUTE_MISSING,
  formatBuiltAt,
  loadKnowledge,
  mergeKnowledge,
  refreshKnowledge,
  type KnowledgeLoad,
  type KnowledgeRefresh,
} from "@/lib/knowledge"

const VOICE_AGENT_NOTICE = "The voice agent should read this page. It is not medical advice."

type Outcome =
  | { kind: "success"; bolnaId: string | null }
  | { kind: "error"; raw: string }

function statusCopy(load: Exclude<KnowledgeLoad, { state: "error" }>): string {
  if (load.state === "down") return API_DOWN_MESSAGE
  if (load.state === "missing") return KNOWLEDGE_ROUTE_MISSING
  if (load.builtAt) return `Last built ${formatBuiltAt(load.builtAt)}.`
  return KNOWLEDGE_ON_REQUEST
}

export function KnowledgeCard({ patientId }: { patientId: string }) {
  const headingId = useId()
  const [load, setLoad] = useState<KnowledgeLoad | null>(null)
  const [outcome, setOutcome] = useState<Outcome | null>(null)
  const [pending, setPending] = useState(false)
  const generation = useRef(0)

  useEffect(() => {
    const seq = generation.current + 1
    generation.current = seq
    setLoad(null)
    setOutcome(null)
    setPending(false)
    loadKnowledge(patientId)
      .then((result) => {
        if (generation.current !== seq) return
        setLoad(result)
      })
      .catch((error: unknown) => {
        if (generation.current !== seq) return
        const message = error instanceof Error && error.message.trim() ? error.message.trim() : "The knowledge request failed."
        setLoad({ state: "error", raw: message })
      })
    return () => {
      generation.current += 1
    }
  }, [patientId])

  async function onRebuild() {
    const seq = generation.current + 1
    generation.current = seq
    setPending(true)
    setOutcome(null)
    let refreshed: KnowledgeRefresh
    try {
      refreshed = await refreshKnowledge(patientId)
    } catch (error) {
      if (generation.current !== seq) return
      const message = error instanceof Error && error.message.trim() ? error.message.trim() : "The knowledge refresh failed."
      setOutcome({ kind: "error", raw: message })
      setPending(false)
      return
    }
    if (generation.current !== seq) return
    if (!refreshed.ok) {
      setOutcome({ kind: "error", raw: refreshed.raw })
      setPending(false)
      return
    }
    setOutcome({ kind: "success", bolnaId: refreshed.bolnaId })
    try {
      const next = await loadKnowledge(patientId)
      if (generation.current !== seq) return
      setLoad(mergeKnowledge(next, refreshed))
    } catch (error) {
      if (generation.current !== seq) return
      const message = error instanceof Error && error.message.trim() ? error.message.trim() : "The knowledge request failed."
      setLoad({ state: "error", raw: message })
    } finally {
      if (generation.current === seq) setPending(false)
    }
  }

  const markdown = load?.state === "ready" ? load.markdown : null

  return (
    <section className="flex flex-col gap-3" aria-labelledby={headingId}>
      <SectionHeading id={headingId} title="Knowledge" />
      <Card>
        <CardHeader>
          <CardTitle>Knowledge page</CardTitle>
          <CardDescription>{VOICE_AGENT_NOTICE}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4" aria-live="polite">
          {load === null ? <p className="text-sm leading-6 text-muted">Loading the knowledge page.</p> : null}
          {load?.state === "error" ? (
            <pre
              role="alert"
              className="max-h-80 overflow-auto whitespace-pre-wrap break-words font-sans text-sm leading-6 text-amber"
            >
              {load.raw}
            </pre>
          ) : null}
          {load && load.state !== "error" ? (
            <p className="text-sm leading-6 text-muted" role="status">
              {statusCopy(load)}
            </p>
          ) : null}
          {markdown ? (
            <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words border-t border-line pt-4 font-sans text-sm leading-6 text-ink">
              {markdown}
            </pre>
          ) : null}
          <div>
            <Button type="button" onClick={() => void onRebuild()} disabled={pending} aria-busy={pending}>
              {pending ? "Rebuilding knowledge page" : "Rebuild knowledge page"}
            </Button>
          </div>
          {outcome?.kind === "success" ? (
            <div role="status" className="flex flex-col gap-1">
              <p className="text-sm leading-6 text-ink">{KNOWLEDGE_REBUILT}</p>
              {outcome.bolnaId ? <p className="text-sm leading-6 text-ink">{BOLNA_RAG_UPDATED}</p> : null}
            </div>
          ) : null}
          {outcome?.kind === "error" ? (
            <pre
              role="alert"
              className="max-h-80 overflow-auto whitespace-pre-wrap break-words font-sans text-sm leading-6 text-amber"
            >
              {outcome.raw}
            </pre>
          ) : null}
        </CardContent>
      </Card>
    </section>
  )
}
