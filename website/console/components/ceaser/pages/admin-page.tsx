"use client"

import { useEffect, useMemo, useState, type ReactNode } from "react"
import { adminApi, type AdminOverview } from "@/lib/api/admin"
import { AlertTriangle, Download, IndianRupee, RefreshCw, ShieldCheck, Users, Wallet, Activity, FolderKanban, FileText } from "lucide-react"
import type { LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"

const metricMeta: Record<string, { label: string; icon: LucideIcon }> = {
  users: { label: "Total Users", icon: Users },
  new_users_7d: { label: "New Users 7d", icon: Users },
  downloads: { label: "Downloads", icon: Download },
  downloads_24h: { label: "Downloads 24h", icon: Download },
  waitlist: { label: "Waitlist", icon: Activity },
  projects: { label: "Projects", icon: FolderKanban },
  files: { label: "Files", icon: FileText },
  conversations: { label: "Conversations", icon: Activity },
  messages: { label: "Messages", icon: Activity },
  active_subscriptions: { label: "Active Subs", icon: Wallet },
  payments: { label: "Payments", icon: IndianRupee },
}

export function AdminPage() {
  const [overview, setOverview] = useState<AdminOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  async function load() {
    setLoading(true)
    setError("")
    try {
      setOverview(await adminApi.overview())
    } catch (err) {
      setError(err instanceof Error ? err.message : "Admin overview could not be loaded.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const revenue = useMemo(() => formatMoney(overview?.totals?.revenue_paise || 0), [overview])
  const visibleMetrics = ["users", "new_users_7d", "downloads", "downloads_24h", "waitlist", "active_subscriptions", "payments", "projects", "files", "conversations", "messages"]

  return (
    <div className="space-y-5 p-5 lg:p-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-xs font-semibold text-emerald-200">
            <ShieldCheck className="h-3.5 w-3.5" />
            Founder Admin
          </div>
          <h1 className="mt-4 text-3xl font-bold text-foreground">CEASER Admin Panel</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            Real launch tracker for users, downloads, subscriptions, revenue, usage, files, projects, and recent activity.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          disabled={loading}
          className="inline-flex h-11 items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-4 text-sm font-semibold transition hover:bg-white/10 disabled:opacity-60"
        >
          <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-3 rounded-2xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-100">
          <AlertTriangle className="h-4 w-4" />
          {error}
        </div>
      )}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Revenue" value={revenue} icon={IndianRupee} accent />
        {visibleMetrics.map((key) => {
          const meta = metricMeta[key]
          if (!meta) return null
          return <MetricCard key={key} label={meta.label} value={formatNumber(overview?.totals?.[key] || 0)} icon={meta.icon} />
        })}
      </section>

      <div className="grid gap-5 xl:grid-cols-[1fr_1fr]">
        <Panel title="Downloads By Source">
          <Table
            empty="No downloads tracked yet."
            rows={(overview?.downloads_by_source || []).map((item) => [item.source, item.platform, formatNumber(item.count)])}
            headers={["Source", "Platform", "Count"]}
          />
        </Panel>
        <Panel title="Active Plans">
          <Table
            empty="No plan data yet."
            rows={(overview?.plans || []).map((item) => [item.code, item.name, formatNumber(item.subscriptions)])}
            headers={["Code", "Plan", "Subscriptions"]}
          />
        </Panel>
        <Panel title="Recent Users">
          <Table
            empty="No users yet."
            rows={(overview?.recent_users || []).map((item) => [item.email, formatDate(item.created_at)])}
            headers={["Email", "Created"]}
          />
        </Panel>
        <Panel title="Recent Payments">
          <Table
            empty="No payments yet."
            rows={(overview?.recent_payments || []).map((item) => [
              item.email || "Unknown",
              formatMoney(item.amount),
              item.status,
              formatDate(item.created_at),
            ])}
            headers={["User", "Amount", "Status", "Created"]}
          />
        </Panel>
        <Panel title="Recent Downloads">
          <Table
            empty="No downloads yet."
            rows={(overview?.recent_downloads || []).map((item) => [item.source, item.platform, item.version || "v1", formatDate(item.created_at)])}
            headers={["Source", "Platform", "Version", "Created"]}
          />
        </Panel>
        <Panel title="Usage Last 7 Days">
          <Table
            empty="No usage recorded yet."
            rows={(overview?.usage_7d || []).map((item) => [item.action_type, formatNumber(item.quantity), formatNumber(item.tokens)])}
            headers={["Action", "Quantity", "Tokens"]}
          />
        </Panel>
      </div>
    </div>
  )
}

function MetricCard({ label, value, icon: Icon, accent = false }: { label: string; value: string; icon: LucideIcon; accent?: boolean }) {
  return (
    <article className={cn("rounded-3xl border border-white/10 bg-white/[0.045] p-5 shadow-[0_22px_70px_rgba(0,0,0,.16)]", accent && "border-primary/35 bg-primary/10")}>
      <div className="mb-4 flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">{label}</span>
        <span className="grid h-9 w-9 place-items-center rounded-2xl bg-white/8 text-primary"><Icon className="h-4 w-4" /></span>
      </div>
      <p className="text-2xl font-bold text-foreground">{value}</p>
    </article>
  )
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-3xl border border-white/10 bg-white/[0.04] p-5">
      <h2 className="mb-4 text-lg font-semibold">{title}</h2>
      {children}
    </section>
  )
}

function Table({ headers, rows, empty }: { headers: string[]; rows: string[][]; empty: string }) {
  if (!rows.length) return <p className="rounded-2xl border border-dashed border-white/10 p-4 text-sm text-muted-foreground">{empty}</p>
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-white/10 text-xs uppercase tracking-[0.14em] text-muted-foreground">
            {headers.map((header) => <th key={header} className="pb-3 pr-4 font-medium">{header}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index} className="border-b border-white/5 last:border-0">
              {row.map((cell, cellIndex) => <td key={`${index}-${cellIndex}`} className="py-3 pr-4 text-muted-foreground first:text-foreground">{cell}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-IN").format(value)
}

function formatMoney(paise: number) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format((paise || 0) / 100)
}

function formatDate(value: string) {
  try {
    return new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value))
  } catch {
    return value
  }
}
