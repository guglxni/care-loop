import { useEffect, useId, useState, type FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { Input, Label } from "@/components/ui/field"
import { SectionHeading } from "@/components/layout/SectionHeading"
import {
  PHONE_LINKING_UNAVAILABLE,
  createPhoneLink,
  e164Error,
  formatLinkedPhone,
  loadPhoneLinks,
  normalizeE164,
  visiblePhoneLinks,
  type PhoneLink,
  type PhoneLinksLoad,
} from "@/lib/phoneLinks"

type LinkedPhonesSectionProps = {
  patientId: string
  patientName: string
}

function sameLink(left: PhoneLink, right: PhoneLink): boolean {
  return left.phoneE164 === right.phoneE164
}

function withLink(links: PhoneLink[], link: PhoneLink): PhoneLink[] {
  const rest = links.filter((item) => !sameLink(item, link))
  return [...rest, link]
}

export function LinkedPhonesSection({ patientId, patientName }: LinkedPhonesSectionProps) {
  const phoneId = useId()
  const labelId = useId()
  const errorId = useId()
  const [load, setLoad] = useState<PhoneLinksLoad | null>(null)
  const [phone, setPhone] = useState("")
  const [label, setLabel] = useState("")
  const [formError, setFormError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoad(null)
    loadPhoneLinks(patientId)
      .then((result) => {
        if (!cancelled) setLoad(result)
      })
      .catch((error: unknown) => {
        if (cancelled) return
        const message = error instanceof Error && error.message.trim() ? error.message.trim() : "The phone links request failed."
        setLoad({ state: "failed", message })
      })
    return () => {
      cancelled = true
    }
  }, [patientId])

  const links = load?.state === "ready" ? visiblePhoneLinks(patientId, load.links) : []

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const phoneProblem = e164Error(phone)
    if (phoneProblem) {
      setFormError(phoneProblem)
      return
    }
    const nextLabel = label.trim()
    if (!nextLabel) {
      setFormError("Enter a label for this number.")
      return
    }
    const phoneE164 = normalizeE164(phone)
    if (links.some((link) => link.phoneE164 === phoneE164)) {
      setFormError("That number is already linked.")
      return
    }
    setFormError(null)
    setPending(true)
    try {
      const created = await createPhoneLink(patientId, { phoneE164, label: nextLabel })
      const refreshed = await loadPhoneLinks(patientId)
      if (refreshed.state === "ready") {
        const present = refreshed.links.some((link) => link.phoneE164 === created.phoneE164)
        setLoad(present ? refreshed : { state: "ready", links: withLink(refreshed.links, created) })
      } else {
        setLoad({ state: "ready", links: withLink(links, created) })
      }
      setPhone("")
      setLabel("")
    } catch (error) {
      const message = error instanceof Error && error.message.trim() ? error.message.trim() : "The phone link could not be saved."
      if (message === PHONE_LINKING_UNAVAILABLE) {
        setLoad({ state: "unavailable", message })
        setFormError(null)
      } else {
        setFormError(message)
      }
    } finally {
      setPending(false)
    }
  }

  return (
    <section className="flex flex-col gap-4" aria-labelledby="linked-phones-heading">
      <SectionHeading
        id="linked-phones-heading"
        title="Linked phones"
        lede={`Numbers CareLoop uses to recognize ${patientName} when a call is placed to or from that phone.`}
      />

      {load === null ? <p className="text-sm leading-6 text-muted">Loading linked phones.</p> : null}

      {load?.state === "unavailable" ? (
        <p role="status" className="text-sm leading-6 text-muted">
          {load.message}
        </p>
      ) : null}

      {load?.state === "failed" ? (
        <p role="alert" className="text-sm leading-6 text-amber">
          {load.message}
        </p>
      ) : null}

      {load?.state === "ready" && links.length === 0 ? (
        <p className="text-sm leading-6 text-muted">No phone is linked for this patient yet.</p>
      ) : null}

      {links.length > 0 ? (
        <ul className="border-t border-line">
          {links.map((link) => (
            <li key={link.phoneE164} className="border-b border-line py-4">
              <p className="font-medium text-ink">{formatLinkedPhone(link.phoneE164)}</p>
              {link.label ? <p className="mt-1 text-sm leading-6 text-muted">{link.label}</p> : null}
            </li>
          ))}
        </ul>
      ) : null}

      <form className="flex max-w-xl flex-col gap-4" onSubmit={(event) => void onSubmit(event)}>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={phoneId}>Phone number</Label>
          <Input
            id={phoneId}
            name="phone_e164"
            type="tel"
            inputMode="tel"
            autoComplete="off"
            spellCheck={false}
            value={phone}
            aria-invalid={formError ? true : undefined}
            aria-describedby={errorId}
            disabled={pending}
            onChange={(event) => {
              setPhone(event.target.value)
              setFormError(null)
            }}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={labelId}>Label</Label>
          <Input
            id={labelId}
            name="label"
            type="text"
            autoComplete="off"
            value={label}
            aria-invalid={formError ? true : undefined}
            aria-describedby={errorId}
            disabled={pending}
            onChange={(event) => {
              setLabel(event.target.value)
              setFormError(null)
            }}
          />
        </div>
        <p id={errorId} className={formError ? "text-sm leading-6 text-amber" : "text-sm leading-6 text-muted"} role={formError ? "alert" : undefined}>
          {formError ?? "Adds another E.164 number for this patient. This does not place a call."}
        </p>
        <div>
          <Button type="submit" disabled={pending} aria-busy={pending}>
            {pending ? "Saving number" : "Add number"}
          </Button>
        </div>
      </form>
    </section>
  )
}
