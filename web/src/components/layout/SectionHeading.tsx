import { cn } from "@/lib/utils"

type SectionHeadingProps = {
  id?: string
  title: string
  lede?: string
  className?: string
}

export function SectionHeading({ id, title, lede, className }: SectionHeadingProps) {
  return (
    <div className={cn("flex max-w-3xl flex-col gap-2", className)}>
      <h2 id={id} className="font-serif text-xl font-medium tracking-tight text-ink md:text-2xl">
        {title}
      </h2>
      {lede ? <p className="max-w-prose text-sm leading-6 text-muted">{lede}</p> : null}
    </div>
  )
}
