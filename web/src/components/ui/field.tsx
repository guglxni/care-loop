import { forwardRef, type ComponentProps } from "react"
import { cn } from "@/lib/utils"

const controlClass =
  "w-full min-w-0 rounded-lg border border-line bg-card px-3 text-base text-ink placeholder:text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sage focus-visible:ring-offset-2 focus-visible:ring-offset-canvas disabled:cursor-not-allowed disabled:bg-neutral-soft aria-invalid:border-amber"

const readOnlyClass = "read-only:bg-neutral-soft"

export function Label({ className, ...props }: ComponentProps<"label">) {
  return <label className={cn("block text-sm font-medium text-ink", className)} {...props} />
}

export const Input = forwardRef<HTMLInputElement, ComponentProps<"input">>(function Input(
  { className, ...props },
  ref,
) {
  return <input ref={ref} className={cn(controlClass, readOnlyClass, "h-11", className)} {...props} />
})

export const Select = forwardRef<HTMLSelectElement, ComponentProps<"select">>(function Select(
  { className, ...props },
  ref,
) {
  return <select ref={ref} className={cn(controlClass, "h-11", className)} {...props} />
})

export const Textarea = forwardRef<HTMLTextAreaElement, ComponentProps<"textarea">>(function Textarea(
  { className, rows = 4, ...props },
  ref,
) {
  return <textarea ref={ref} rows={rows} className={cn(controlClass, readOnlyClass, "min-h-28 py-2", className)} {...props} />
})
