"use client"

import { useEffect, useState } from "react"
import { CheckCircle2, CircleDashed, Server, ShieldCheck, Sparkles, Unplug, Mic } from "lucide-react"
import { getAccessToken, getApiBaseUrl } from "@/lib/api/client"
import { integrationsApi } from "@/lib/api/integrations"
import { cn } from "@/lib/utils"

type StatusState = "ready" | "attention" | "not-connected"

type StatusItem = {
  label: string
  detail: string
  status: StatusState
  icon: typeof CheckCircle2
}

const API_BASE_URL = getApiBaseUrl()

export function SystemStatusCard({ compact = false }: { compact?: boolean }) {
  const [apiReady, setApiReady] = useState<boolean | null>(null)
  const [voiceReady, setVoiceReady] = useState(false)
  const [connectedIntegrations, setConnectedIntegrations] = useState<number | null>(null)
  const signedIn = Boolean(getAccessToken())

  useEffect(() => {
    let cancelled = false
    fetch(`${API_BASE_URL}/health`)
      .then((response) => {
        if (!cancelled) setApiReady(response.ok)
      })
      .catch(() => {
        if (!cancelled) setApiReady(false)
      })
    setVoiceReady(typeof window !== "undefined" && "speechSynthesis" in window)
    void integrationsApi.list()
      .then((records) => {
        if (!cancelled) setConnectedIntegrations(records.filter((integration) => integration.connected).length)
      })
      .catch(() => {
        if (!cancelled) setConnectedIntegrations(0)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const items: StatusItem[] = [
    {
      label: "CEASER API",
      detail: apiReady === null ? "Checking" : apiReady ? "Ready" : "Start backend to continue",
      status: apiReady ? "ready" : apiReady === null ? "attention" : "attention",
      icon: Server,
    },
    {
      label: "Account",
      detail: signedIn ? "Signed in" : "Sign in required",
      status: signedIn ? "ready" : "attention",
      icon: ShieldCheck,
    },
    {
      label: "Voice",
      detail: voiceReady ? "Browser voice ready" : "Voice unavailable in this browser",
      status: voiceReady ? "ready" : "attention",
      icon: Mic,
    },
    {
      label: "AI Provider",
      detail: apiReady ? "AI routed through backend" : "Connecting to CEASER services",
      status: apiReady ? "ready" : "attention",
      icon: Sparkles,
    },
    {
      label: "Integrations",
      detail: connectedIntegrations === null ? "Checking" : `${connectedIntegrations} connected`,
      status: connectedIntegrations && connectedIntegrations > 0 ? "ready" : "attention",
      icon: Unplug,
    },
  ]

  return (
    <section className={cn("rounded-2xl border border-border bg-card/70 p-4", !compact && "shadow-[0_22px_80px_rgba(0,0,0,0.16)]")}>
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.24em] text-primary">System Status</p>
          {!compact && <h3 className="mt-1 text-lg font-semibold">Launch readiness</h3>}
        </div>
        <span className="rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">Standard Mode</span>
      </div>
      <div className={cn("grid gap-2", compact ? "grid-cols-1" : "md:grid-cols-2")}>
        {items.map((item) => {
          const Icon = item.icon
          const ready = item.status === "ready"
          return (
            <div key={item.label} className="flex items-center gap-3 rounded-xl border border-border bg-secondary/45 p-3">
              <div className={cn("flex h-9 w-9 items-center justify-center rounded-xl", ready ? "bg-emerald-500/10 text-emerald-300" : "bg-amber-500/10 text-amber-300")}>
                <Icon className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">{item.label}</p>
                <p className="truncate text-xs text-muted-foreground">{item.detail}</p>
              </div>
              {ready ? <CheckCircle2 className="h-4 w-4 text-emerald-300" /> : <CircleDashed className="h-4 w-4 text-amber-300" />}
            </div>
          )
        })}
      </div>
    </section>
  )
}
