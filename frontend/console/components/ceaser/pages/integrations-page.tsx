"use client"

import type { ReactNode } from "react"
import { useEffect, useMemo, useState } from "react"
import { integrationsApi, type IntegrationRecord } from "@/lib/api/integrations"
import { cn } from "@/lib/utils"
import {
  Calendar,
  Check,
  ChevronRight,
  Database,
  FileText,
  Github,
  Inbox,
  KeyRound,
  Loader2,
  Lock,
  Mail,
  MessageSquare,
  MoreHorizontal,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  Tag,
  Unplug,
  Users,
} from "lucide-react"

type Filter = "all" | "connected" | "available" | "account" | "permissions"

const liveProviders = new Set(["google-calendar", "gmail", "google-drive", "google-tasks", "google-classroom"])

const fallbackProviders: IntegrationRecord[] = [
  providerStub("gmail", "Gmail", "Read inbox metadata, unread email, important email, and labels.", "not_connected"),
  providerStub("google-calendar", "Google Calendar", "Read calendars, events, upcoming schedule, and event details.", "not_connected"),
  providerStub("google-drive", "Google Drive", "Read Drive file metadata and supported document content.", "not_connected"),
  providerStub("google-tasks", "Google Tasks", "Read task lists, tasks, and due dates.", "not_connected"),
  providerStub("google-classroom", "Google Classroom", "Read courses, coursework, assignments, and due dates.", "not_connected"),
  providerStub("notion", "Notion", "Sync notes, docs and knowledge.", "available"),
  providerStub("slack", "Slack", "Send messages and get updates in Slack.", "coming_soon"),
  providerStub("microsoft-outlook", "Microsoft Outlook", "Sync emails, contacts and calendar.", "coming_soon"),
  providerStub("github", "GitHub", "Connect repos and track activity.", "coming_soon"),
  providerStub("microsoft-teams", "Microsoft Teams", "Collaborate and get updates in Teams.", "coming_soon"),
  providerStub("dropbox", "Dropbox", "Access and share your files in Dropbox.", "coming_soon"),
  providerStub("linear", "Linear", "Sync issues and project updates.", "coming_soon"),
]

export function IntegrationsPage() {
  const [integrations, setIntegrations] = useState<IntegrationRecord[]>([])
  const [selectedId, setSelectedId] = useState("gmail")
  const [query, setQuery] = useState("")
  const [filter, setFilter] = useState<Filter>("all")
  const [isLoading, setIsLoading] = useState(true)
  const [busyProvider, setBusyProvider] = useState<string | null>(null)
  const [message, setMessage] = useState("")

  useEffect(() => {
    void loadIntegrations()
  }, [])

  useEffect(() => {
    const timer = window.setInterval(() => {
      void syncConnectedIntegrations()
    }, 5 * 60 * 1000)
    return () => window.clearInterval(timer)
  }, [integrations, busyProvider])

  async function loadIntegrations() {
    setIsLoading(true)
    setMessage("")
    try {
      const records = await integrationsApi.list()
      setIntegrations(records)
      if (!records.some((item) => item.id === selectedId)) setSelectedId(records[0]?.id || "gmail")
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not load integrations.")
    } finally {
      setIsLoading(false)
    }
  }

  async function connect(provider: string) {
    setBusyProvider(provider)
    setMessage("")
    try {
      const result = await integrationsApi.connect(provider)
      if (result.auth_url) {
        window.location.href = result.auth_url
        return
      }
      await loadIntegrations()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not connect integration.")
    } finally {
      setBusyProvider(null)
    }
  }

  async function disconnect(provider: string) {
    setBusyProvider(provider)
    setMessage("")
    setIntegrations((current) =>
      current.map((item) =>
        item.id === provider
          ? { ...item, connected: false, status: "not_connected", account_email: null, last_sync_at: null, provider_account_id: null, metadata: {} }
          : item,
      ),
    )
    try {
      await integrationsApi.disconnect(provider)
      await loadIntegrations()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not disconnect integration.")
      await loadIntegrations()
    } finally {
      setBusyProvider(null)
    }
  }

  async function sync(provider: string) {
    setBusyProvider(provider)
    setMessage("")
    try {
      await integrationsApi.sync(provider)
      await loadIntegrations()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not sync integration.")
    } finally {
      setBusyProvider(null)
    }
  }

  async function syncConnectedIntegrations() {
    if (busyProvider) return
    const connected = integrations.filter((item) => item.connected && liveProviders.has(item.id))
    if (!connected.length) return
    await Promise.allSettled(connected.map((item) => integrationsApi.sync(item.id)))
    await loadIntegrations()
  }

  const allIntegrations = useMemo(() => {
    const byId = new Map<string, IntegrationRecord>()
    for (const item of fallbackProviders) byId.set(item.id, item)
    for (const item of integrations) byId.set(item.id, item)
    return Array.from(byId.values())
  }, [integrations])

  const selected = allIntegrations.find((item) => item.id === selectedId) || allIntegrations[0]
  const connectedCount = allIntegrations.filter((item) => item.connected).length
  const availableCount = allIntegrations.filter((item) => liveProviders.has(item.id) && !item.connected).length

  const filtered = allIntegrations.filter((item) => {
    const matchesQuery = `${item.name} ${item.description}`.toLowerCase().includes(query.toLowerCase())
    const matchesFilter =
      filter === "all" ||
      (filter === "connected" && item.connected) ||
      (filter === "available" && !item.connected) ||
      filter === "account" ||
      filter === "permissions"
    return matchesQuery && matchesFilter
  })

  return (
    <div className="h-full overflow-y-auto bg-[radial-gradient(circle_at_top_left,rgba(124,58,237,0.13),transparent_34%),linear-gradient(135deg,#050812,#0b1020_52%,#070912)] p-6">
      <div className="mx-auto grid max-w-[1400px] gap-5 xl:grid-cols-[1fr_360px]">
        <main className="min-w-0">
          <header className="mb-8 flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-4xl font-bold tracking-tight">Integrations</h1>
              <p className="mt-2 text-muted-foreground">Connect your favorite tools and let CEASER work with everything you use.</p>
            </div>
            <div className="flex gap-3">
              <label className="flex h-12 w-[360px] max-w-full items-center gap-3 rounded-xl border border-white/10 bg-white/[0.045] px-4 text-sm shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
                <Search className="h-4 w-4 text-muted-foreground" />
                <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search integrations..." className="w-full bg-transparent outline-none placeholder:text-muted-foreground" />
              </label>
              <button onClick={() => void loadIntegrations()} disabled={isLoading} className="flex h-12 items-center gap-2 rounded-xl border border-white/10 bg-white/[0.045] px-5 text-sm font-semibold transition hover:bg-white/10 disabled:opacity-60">
                <RefreshCw className={cn("h-4 w-4", isLoading && "animate-spin")} />
                Refresh All
              </button>
            </div>
          </header>

          <div className="mb-7 flex gap-7 border-b border-white/10 text-sm font-medium">
            <Tab label="All Integrations" active={filter === "all"} onClick={() => setFilter("all")} />
            <Tab label={`Connected (${connectedCount})`} active={filter === "connected"} onClick={() => setFilter("connected")} />
            <Tab label={`Available (${availableCount})`} active={filter === "available"} onClick={() => setFilter("available")} />
            <Tab label="Account" active={filter === "account"} onClick={() => setFilter("account")} />
            <Tab label="Data & Permissions" active={filter === "permissions"} onClick={() => setFilter("permissions")} />
          </div>

          {message && <p className="mb-4 rounded-xl border border-primary/20 bg-primary/10 px-4 py-3 text-sm text-muted-foreground">{message}</p>}

          {isLoading ? (
            <div className="flex items-center justify-center py-24 text-muted-foreground">
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              Loading integrations...
            </div>
          ) : (
            <div className="grid gap-4 lg:grid-cols-2">
              {filtered.map((integration) => (
                <IntegrationCard
                  key={integration.id}
                  integration={integration}
                  selected={selected?.id === integration.id}
                  busy={busyProvider === integration.id}
                  onSelect={() => setSelectedId(integration.id)}
                  onConnect={() => void connect(integration.id)}
                  onDisconnect={() => void disconnect(integration.id)}
                  onSync={() => void sync(integration.id)}
                />
              ))}
            </div>
          )}

          <p className="mt-7 flex items-center justify-center gap-2 text-xs text-muted-foreground">
            <Lock className="h-3.5 w-3.5" />
            Your data is encrypted and secure. CEASER never shares your data with third parties.
          </p>
        </main>

        <aside className="sticky top-4 h-fit overflow-hidden rounded-2xl border border-white/10 bg-white/[0.045] shadow-[0_30px_100px_rgba(0,0,0,0.35)]">
          {selected && (
            <>
              <div className="p-6">
                <div className="flex items-start gap-4">
                  <IntegrationLogo id={selected.id} large />
                  <div className="min-w-0 flex-1">
                    <h2 className="text-xl font-bold">{selected.name}</h2>
                    <StatusPill integration={selected} />
                  </div>
                </div>
                <p className="mt-5 text-sm leading-relaxed text-muted-foreground">{selected.description}</p>
                <div className="mt-5">
                  <p className="text-sm text-muted-foreground">Connected account</p>
                  <p className="mt-1 font-medium">{selected.account_email || (selected.connected ? "Connected account" : "Not connected")}</p>
                </div>
                <div className="mt-6 flex gap-2">
                  {selected.connected ? (
                    <>
                      <button onClick={() => void sync(selected.id)} disabled={busyProvider === selected.id} className="flex items-center gap-2 rounded-xl border border-white/10 px-4 py-2 text-sm font-semibold transition hover:bg-white/10 disabled:opacity-60">
                        {busyProvider === selected.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                        Sync
                      </button>
                      <button onClick={() => void disconnect(selected.id)} disabled={busyProvider === selected.id} className="rounded-xl border border-red-500/70 px-4 py-2 text-sm font-semibold text-red-400 transition hover:bg-red-500/10 disabled:opacity-60">
                        Disconnect
                      </button>
                    </>
                  ) : (
                    <button onClick={() => void connect(selected.id)} disabled={!liveProviders.has(selected.id) || busyProvider === selected.id} className="rounded-xl bg-gradient-to-r from-blue-500 to-violet-600 px-5 py-2 text-sm font-semibold text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50">
                      {liveProviders.has(selected.id) ? "Connect" : "Future Update"}
                    </button>
                  )}
                </div>
              </div>

              <PanelSection title="Permissions">
                {permissionLabels(selected).map((permission) => (
                  <DetailRow key={permission} icon={<Check className="h-3.5 w-3.5" />} text={permission} />
                ))}
              </PanelSection>

              <PanelSection title="Features">
                {featureLabels(selected).map((feature) => (
                  <DetailRow key={feature.title} icon={feature.icon} text={feature.title} subtext={feature.detail} />
                ))}
              </PanelSection>

              <div className="border-t border-white/10 p-6 text-sm">
                <p className="text-muted-foreground">Last sync</p>
                <p className="mt-1 font-medium">{selected.last_sync_at ? formatDate(selected.last_sync_at) : selected.connected ? "Ready to sync" : "Not connected"}</p>
              </div>
            </>
          )}
        </aside>
      </div>
    </div>
  )
}

function IntegrationCard({ integration, selected, busy, onSelect, onConnect, onDisconnect, onSync }: {
  integration: IntegrationRecord
  selected: boolean
  busy: boolean
  onSelect: () => void
  onConnect: () => void
  onDisconnect: () => void
  onSync: () => void
}) {
  const live = liveProviders.has(integration.id)
  return (
    <article
      onClick={onSelect}
      className={cn(
        "group flex min-h-[150px] cursor-pointer flex-col justify-between rounded-xl border bg-white/[0.045] p-5 transition hover:-translate-y-0.5 hover:bg-white/[0.07]",
        selected ? "border-violet-500/70 shadow-[0_0_35px_rgba(124,58,237,0.16)]" : "border-white/10",
      )}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 gap-4">
          <IntegrationLogo id={integration.id} />
          <div className="min-w-0">
            <p className="font-semibold">{integration.name}</p>
            <p className="mt-1 max-w-[240px] text-sm leading-relaxed text-muted-foreground">{integration.description}</p>
          </div>
        </div>
        <StatusPill integration={integration} />
      </div>
      <div className="mt-5 flex items-center justify-between gap-3">
        <p className="flex min-w-0 items-center gap-2 truncate text-sm text-muted-foreground">
          <Users className="h-4 w-4 shrink-0" />
          <span className="truncate">{integration.account_email || (integration.connected ? "Connected account" : live ? "Available to connect" : "Coming soon")}</span>
        </p>
        <div className="flex items-center gap-2">
          {integration.connected ? (
            <>
              <button onClick={(event) => { event.stopPropagation(); onSync() }} disabled={busy} className="rounded-lg border border-white/10 px-3 py-2 text-xs font-medium text-muted-foreground hover:bg-white/10 disabled:opacity-60">
                {busy ? "Syncing" : "Sync"}
              </button>
              <button onClick={(event) => { event.stopPropagation(); onDisconnect() }} disabled={busy} className="rounded-lg border border-red-500/30 px-3 py-2 text-xs font-medium text-red-400 hover:bg-red-500/10 disabled:opacity-60">
                Disconnect
              </button>
            </>
          ) : (
            <button onClick={(event) => { event.stopPropagation(); onConnect() }} disabled={!live || busy} className="rounded-lg bg-gradient-to-r from-blue-500 to-violet-600 px-4 py-2 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:opacity-45">
              {busy ? "Opening" : live ? "Connect" : "Soon"}
            </button>
          )}
          <MoreHorizontal className="h-4 w-4 text-muted-foreground" />
        </div>
      </div>
    </article>
  )
}

function IntegrationLogo({ id, large = false }: { id: string; large?: boolean }) {
  const size = large ? "h-16 w-16 text-2xl" : "h-12 w-12 text-xl"
  const iconClass = large ? "h-8 w-8" : "h-6 w-6"
  const base = "flex shrink-0 items-center justify-center rounded-xl shadow-[inset_0_1px_0_rgba(255,255,255,0.22)]"
  if (id === "gmail") return <div className={cn(base, size, "bg-white text-red-500")}><Mail className={iconClass} /></div>
  if (id === "google-calendar") return <div className={cn(base, size, "bg-white text-blue-500")}><Calendar className={iconClass} /></div>
  if (id === "google-drive") return <div className={cn(base, size, "bg-gradient-to-br from-emerald-400 via-yellow-400 to-blue-500 text-white")}><FileText className={iconClass} /></div>
  if (id === "google-tasks") return <div className={cn(base, size, "bg-blue-500/20 text-blue-300")}><Check className={iconClass} /></div>
  if (id === "google-classroom") return <div className={cn(base, size, "bg-emerald-500/20 text-emerald-300")}><Users className={iconClass} /></div>
  if (id === "notion") return <div className={cn(base, size, "bg-white text-black")}><span className="font-black">N</span></div>
  if (id === "slack") return <div className={cn(base, size, "bg-[#171717] text-white")}><MessageSquare className={iconClass} /></div>
  if (id === "microsoft-outlook") return <div className={cn(base, size, "bg-blue-500 text-white")}><Inbox className={iconClass} /></div>
  if (id === "github") return <div className={cn(base, size, "bg-white text-black")}><Github className={iconClass} /></div>
  if (id === "microsoft-teams") return <div className={cn(base, size, "bg-violet-500 text-white")}><Users className={iconClass} /></div>
  if (id === "dropbox") return <div className={cn(base, size, "bg-blue-600 text-white")}><Database className={iconClass} /></div>
  if (id === "linear") return <div className={cn(base, size, "bg-violet-500 text-white")}><Sparkles className={iconClass} /></div>
  return <div className={cn(base, size, "bg-primary/20 text-primary")}><KeyRound className={iconClass} /></div>
}

function StatusPill({ integration }: { integration: IntegrationRecord }) {
  const live = liveProviders.has(integration.id)
  const label = !live ? "Available" : integration.connected ? "Connected" : integration.status === "credentials_required" ? "Setup needed" : "Available"
  return (
    <span className={cn(
      "shrink-0 rounded-lg px-3 py-1 text-xs font-semibold",
      integration.connected ? "bg-emerald-500/18 text-emerald-300" : integration.status === "credentials_required" ? "bg-amber-500/15 text-amber-300" : "bg-white/10 text-muted-foreground",
    )}>
      {label}
    </span>
  )
}

function Tab({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} className={cn("relative pb-4 text-muted-foreground transition hover:text-foreground", active && "text-violet-300")}>
      {label}
      {active && <span className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-violet-500" />}
    </button>
  )
}

function PanelSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="border-t border-white/10 p-6">
      <h3 className="mb-4 font-semibold">{title}</h3>
      <div className="space-y-3">{children}</div>
    </section>
  )
}

function DetailRow({ icon, text, subtext }: { icon: ReactNode; text: string; subtext?: string }) {
  return (
    <div className="flex gap-3 text-sm">
      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-300">{icon}</span>
      <span>
        <span className="block text-foreground">{text}</span>
        {subtext && <span className="text-xs text-muted-foreground">{subtext}</span>}
      </span>
    </div>
  )
}

function permissionLabels(integration: IntegrationRecord) {
  if (integration.id === "gmail") return ["Read emails", "Read labels", "Access profile info"]
  if (integration.id === "google-calendar") return ["Read calendars", "Read calendar events", "Access profile info"]
  if (integration.id === "google-drive") return ["Read Drive metadata", "Read supported document content", "Access profile info"]
  if (integration.id === "google-tasks") return ["Read task lists", "Read tasks and due dates", "Access profile info"]
  if (integration.id === "google-classroom") return ["Read courses", "Read coursework", "Read assignments and due dates"]
  return ["Read account metadata", "Use connection status", "Access profile info"]
}

function featureLabels(integration: IntegrationRecord) {
  if (integration.id === "gmail") {
    return [
      { title: "AI Email Assistant", detail: "Summaries and important inbox signals", icon: <Sparkles className="h-3.5 w-3.5" /> },
      { title: "Email Search", detail: "Search across your inbox", icon: <Search className="h-3.5 w-3.5" /> },
      { title: "Label Awareness", detail: "Understand inbox organization", icon: <Tag className="h-3.5 w-3.5" /> },
    ]
  }
  if (integration.id === "google-calendar") {
    return [
      { title: "Daily Agenda", detail: "Ask CEASER what is on your schedule", icon: <Calendar className="h-3.5 w-3.5" /> },
      { title: "Meeting Context", detail: "Use events in briefings and planning", icon: <Sparkles className="h-3.5 w-3.5" /> },
    ]
  }
  return [
    { title: "Agent Context", detail: "Let CEASER use this source when relevant", icon: <Sparkles className="h-3.5 w-3.5" /> },
    { title: "Secure Read Mode", detail: "V1 reads data only, no destructive writes", icon: <ShieldCheck className="h-3.5 w-3.5" /> },
  ]
}

function providerStub(id: string, name: string, description: string, status: string): IntegrationRecord {
  return {
    id,
    name,
    category: "productivity",
    description,
    scopes: [],
    permissions: [],
    read_only: true,
    status,
    connected: false,
    metadata: {},
  }
}

function formatDate(value?: string | null) {
  if (!value) return "Never"
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value))
}
