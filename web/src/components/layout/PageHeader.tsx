import { cn } from "@/lib/utils"

type PageHeaderProps = {
  title: string
  lede?: string
  note?: string
  className?: string
}

export function PageHeader({ title, lede, note, className }: PageHeaderProps) {
  return (
    <header className={cn("flex max-w-3xl flex-col gap-3", className)}>
      <h1 className="font-serif text-3xl font-medium tracking-tight text-ink md:text-4xl md:leading-tight">
        {title}
      </h1>
      {lede ? <p className="max-w-prose text-base leading-7 text-muted">{lede}</p> : null}
      {note ? <p className="text-sm leading-6 text-muted">{note}</p> : null}
    </header>
  )
}
