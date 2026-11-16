import type { HTMLAttributes } from "react"
import { cn } from "@/lib/utils"

const tones = {
  neutral: "border border-line bg-neutral-soft text-ink",
  green: "bg-sage-soft text-sage",
  blue: "bg-calm-soft text-calm",
  amber: "bg-amber-soft text-amber",
} as const

export type BadgeTone = keyof typeof tones

type BadgeProps = HTMLAttributes<HTMLSpanElement> & {
  tone?: BadgeTone
}

export function Badge({ tone = "neutral", className, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-1 text-sm font-medium leading-none",
        tones[tone],
        className,
      )}
      {...props}
    />
  )
}
