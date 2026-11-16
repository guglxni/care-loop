import { forwardRef, type ButtonHTMLAttributes } from "react"
import { cn } from "@/lib/utils"

type ButtonVariant = "default" | "outline" | "ghost"
type ButtonSize = "sm" | "md"

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant
  size?: ButtonSize
}

const variants: Record<ButtonVariant, string> = {
  default: "bg-sage text-card hover:bg-sage-strong",
  outline: "border border-line bg-card text-ink hover:bg-neutral-soft",
  ghost: "bg-transparent text-ink hover:bg-neutral-soft",
}

const sizes: Record<ButtonSize, string> = {
  sm: "min-h-10 px-3 text-sm",
  md: "min-h-11 px-4 text-base",
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "default", size = "md", className, type = "button", ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cn(
        "inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg font-medium whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sage focus-visible:ring-offset-2 focus-visible:ring-offset-canvas disabled:cursor-not-allowed disabled:opacity-60",
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  )
})
