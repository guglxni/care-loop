import {
  Activity,
  CalendarDays,
  ClipboardList,
  Database,
  Droplet,
  FileText,
  House,
  Phone,
  Pill,
  ScrollText,
  UserRound,
  type LucideIcon,
} from "lucide-react"
import { useEffect, useState } from "react"
import { NavLink, Outlet, useLocation } from "react-router-dom"
import { DemoBanner } from "@/components/layout/DemoBanner"
import { demoPatient } from "@/data/demo"
import { cn } from "@/lib/utils"

const RAVI_ID = "a52a0000-0000-4000-8000-000000000052"

type ShellPerson = {
  name: string
  detail: string
}

function useDemoShellPerson(active: boolean): ShellPerson | null {
  const [person, setPerson] = useState<ShellPerson | null>(null)

  useEffect(() => {
    if (!active) return
    let cancelled = false
    fetch("/api/v1/demo/ravi", { headers: { Accept: "application/json" }, cache: "no-store" })
      .then(async (response) => (response.ok ? response.json() : null))
      .then((body: unknown) => {
        if (cancelled || !body || typeof body !== "object") return
        const profile = (body as { profile?: unknown }).profile
        if (!profile || typeof profile !== "object") return
        const record = profile as { id?: unknown; preferred_name?: unknown; clinic?: unknown }
        const name = typeof record.preferred_name === "string" ? record.preferred_name.replace(/\s+/g, " ").trim() : ""
        if (record.id !== RAVI_ID || name !== "Ravi Sharma") return
        const clinic = typeof record.clinic === "string" ? record.clinic.trim() : ""
        setPerson({ name, detail: clinic })
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [active])

  return person
}

type NavItem = {
  to: string
  label: string
  icon: LucideIcon
  end?: boolean
}

const navItems: NavItem[] = [
  { to: "/", label: "Today", icon: House, end: true },
  { to: "/profile", label: "Profile", icon: UserRound },
  { to: "/glucose", label: "Glucose", icon: Droplet },
  { to: "/blood-pressure", label: "Blood pressure", icon: Activity },
  { to: "/ingest", label: "Data sources", icon: Database },
  { to: "/medications", label: "Medicines", icon: Pill },
  { to: "/calendar", label: "Calendar", icon: CalendarDays },
  { to: "/reports", label: "Reports", icon: FileText },
  { to: "/companion", label: "Companion", icon: Phone },
  { to: "/demo", label: "Demo", icon: ClipboardList },
  { to: "/showcase", label: "Showcase", icon: ScrollText },
]

const focusLink =
  "no-underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sage focus-visible:ring-offset-2"

function initials(name: string): string {
  const letters = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
  return letters.join("") || "CL"
}

function navClass(isActive: boolean, compact: boolean) {
  return cn(
    "flex min-h-11 items-center gap-2.5 font-medium",
    focusLink,
    compact
      ? "shrink-0 rounded-full px-3.5 text-sm whitespace-nowrap ring-offset-canvas"
      : "rounded-lg px-3 text-base ring-offset-sidebar",
    isActive ? "bg-sage-soft text-ink" : "text-muted hover:bg-neutral-soft hover:text-ink",
  )
}

function ShellLink({ item, compact }: { item: NavItem; compact: boolean }) {
  const Icon = item.icon
  return (
    <NavLink to={item.to} end={item.end} className={({ isActive }) => navClass(isActive, compact)}>
      <Icon aria-hidden="true" className="size-5 shrink-0" strokeWidth={1.75} />
      <span>{item.label}</span>
    </NavLink>
  )
}

export function AppShell() {
  const onDemo = useLocation().pathname === "/demo"
  const demoPerson = useDemoShellPerson(onDemo)
  const shellName = onDemo ? (demoPerson?.name ?? "") : demoPatient.preferredName
  const shellDetail = onDemo ? (demoPerson?.detail ?? "") : demoPatient.city

  return (
    <div className="relative flex h-dvh flex-col overflow-hidden bg-canvas text-ink">
      <a
        href="#main"
        className="absolute top-2 left-4 z-50 -translate-y-24 rounded-lg bg-card px-3 py-2 text-sm font-medium text-ink focus:translate-y-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sage focus-visible:ring-offset-2 focus-visible:ring-offset-canvas"
      >
        Skip to content
      </a>
      <DemoBanner />
      <div className="flex min-h-0 flex-1">
        <aside className="hidden min-h-0 w-64 shrink-0 flex-col border-r border-line bg-sidebar md:flex">
          <div className="px-6 pt-8">
            <NavLink
              to="/"
              end
              className={cn(
                focusLink,
                "inline-flex min-h-11 items-center font-serif text-2xl font-medium tracking-tight text-ink ring-offset-sidebar",
              )}
            >
              Care Loop
            </NavLink>
            <p className="mt-1 text-sm text-muted">Personal chart</p>
          </div>
          <NavLink
            to="/profile"
            className={cn(
              focusLink,
              "mx-3 mt-8 flex min-h-11 items-center gap-3 rounded-xl px-3 py-2.5 ring-offset-sidebar hover:bg-neutral-soft",
            )}
          >
            <span
              aria-hidden="true"
              className="flex size-10 shrink-0 items-center justify-center rounded-full bg-sage-soft font-serif text-sm text-sage"
            >
              {initials(shellName)}
            </span>
            <span className="min-w-0 text-left">
              <span className="block truncate font-serif text-base font-medium leading-tight text-ink">
                {shellName || "Loading chart"}
              </span>
              {shellDetail ? (
                <span className="mt-0.5 block truncate text-sm text-muted">{shellDetail}</span>
              ) : null}
            </span>
          </NavLink>
          <nav aria-label="Primary" className="mt-6 flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto px-3 pb-8">
            {navItems.map((item) => (
              <ShellLink key={item.to} item={item} compact={false} />
            ))}
          </nav>
        </aside>
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <div className="shrink-0 border-b border-line md:hidden">
            <header className="flex items-center justify-between gap-3 px-4 pt-2">
              <NavLink
                to="/"
                end
                className={cn(
                  focusLink,
                  "inline-flex min-h-11 items-center font-serif text-2xl font-medium tracking-tight text-ink ring-offset-canvas",
                )}
              >
                Care Loop
              </NavLink>
              <NavLink
                to="/profile"
                className={cn(focusLink, "inline-flex min-h-11 max-w-[46%] items-center ring-offset-canvas")}
              >
                <span className="truncate text-sm font-medium text-muted">{shellName || "Loading chart"}</span>
              </NavLink>
            </header>
            <nav
              aria-label="Primary"
              className="flex gap-1.5 overflow-x-auto overscroll-x-contain px-4 pt-1 pb-3"
            >
              {navItems.map((item) => (
                <ShellLink key={item.to} item={item} compact />
              ))}
            </nav>
          </div>
          <main id="main" tabIndex={-1} className="min-h-0 min-w-0 flex-1 overflow-auto outline-none">
            <div className="mx-auto w-full max-w-5xl px-4 py-8 md:px-8 md:py-12">
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </div>
  )
}
