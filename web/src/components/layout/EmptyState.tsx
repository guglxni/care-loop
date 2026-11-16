import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

type EmptyStateProps = {
  title: string
  children?: ReactNode
  action?: ReactNode
  className?: string
}

export function EmptyState({ title, children, action, className }: EmptyStateProps) {
  return (
    <div className={cn("rounded-2xl bg-neutral-soft px-5 py-8", className)}>
      <p className="font-serif text-lg font-medium text-ink">{title}</p>
      {children ? <div className="mt-2 max-w-prose text-sm leading-6 text-muted">{children}</div> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  )
}
