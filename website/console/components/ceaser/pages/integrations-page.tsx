"use client"

import { useEffect, useMemo, useState } from "react"
import { Check, ChevronRight, Loader2, MoreHorizontal, Search, ShieldCheck, X } from "lucide-react"
import { integrationsApi, type IntegrationRecord } from "@/lib/api/integrations"
import { cn } from "@/lib/utils"
import { trackEvent } from "@/lib/analytics"

type Plugin = { id: string; name: string; description: string; category: string; icon: string; services?: string[] }
const live = new Set(["github", "notion", "gmail", "google-drive", "google-calendar", "google-tasks", "google-classroom"])
const plugins: Plugin[] = [
  { id: "gmail", name: "Gmail", description: "Read messages, manage drafts, and send email when you ask.", category: "Productivity", icon: "gmail" },
  { id: "google-drive", name: "Google Drive", description: "Search and read Drive files, including Docs and Sheets content.", category: "Productivity", icon: "googledrive", services: ["Google Drive", "Google Docs", "Google Sheets"] },
  { id: "google-calendar", name: "Google Calendar", description: "Read events and manage your schedule with CEASER.", category: "Productivity", icon: "googlecalendar" },
  { id: "google-tasks", name: "Google Tasks", description: "Read task lists, open tasks, and due dates.", category: "Productivity", icon: "googletasks" },
  { id: "google-classroom", name: "Google Classroom", description: "Read courses, coursework, assignments, and due dates.", category: "Productivity", icon: "googleclassroom" },
  { id: "slack", name: "Slack", description: "Get messages, send updates and automate workflows.", category: "Communication", icon: "slack" },
  { id: "spotify", name: "Spotify", description: "Play, search and control music right from CEASER.", category: "Entertainment", icon: "spotify" },
  { id: "telegram", name: "Telegram", description: "Send messages and manage conversations.", category: "Communication", icon: "telegram" },
  { id: "microsoft-365", name: "Microsoft 365", description: "Documents, mail and team productivity.", category: "Productivity", icon: "microsoft" },
  { id: "notion", name: "Notion", description: "Connect pages, databases and workspace knowledge.", category: "Productivity", icon: "notion" },
  { id: "dropbox", name: "Dropbox", description: "Cloud files and shared folders.", category: "Productivity", icon: "dropbox" },
  { id: "todoist", name: "Todoist", description: "Tasks, projects and productivity workflows.", category: "Productivity", icon: "todoist" },
  { id: "discord", name: "Discord", description: "Communities, messages and notifications.", category: "Communication", icon: "discord" },
  { id: "trello", name: "Trello", description: "Boards, cards and project workflows.", category: "Productivity", icon: "trello" },
  { id: "github", name: "GitHub", description: "Repositories, commits, issues and pull requests.", category: "Developer", icon: "github" },
  { id: "jira", name: "Jira", description: "Software planning and issue tracking.", category: "Developer", icon: "jira" },
  { id: "linear", name: "Linear", description: "Product planning and issue tracking.", category: "Developer", icon: "linear" },
  { id: "figma", name: "Figma", description: "Design files, components and collaboration.", category: "Developer", icon: "figma" },
  { id: "weather", name: "Weather", description: "Live forecasts and planning context.", category: "Utilities", icon: "weatherapi" },
  { id: "youtube", name: "YouTube", description: "Videos, channels and playback.", category: "Entertainment", icon: "youtube" },
  { id: "google-contacts", name: "Google Contacts", description: "Contacts and people management.", category: "Productivity", icon: "googlecontacts" },
  { id: "google-maps", name: "Google Maps", description: "Places, routes and location context.", category: "Utilities", icon: "googlemaps" },
  { id: "zoom", name: "Zoom", description: "Meetings and video collaboration.", category: "Communication", icon: "zoom" },
]
const categories = ["All", "Recommended", "Productivity", "Communication", "Developer", "Utilities", "Entertainment", "Smart Home"]

export function IntegrationsPage() {
  const [records, setRecords] = useState<IntegrationRecord[]>([])
  const [selected, setSelected] = useState<Plugin | null>(null)
  const [category, setCategory] = useState("All")
  const [query, setQuery] = useState("")
  const [busy, setBusy] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    integrationsApi.list().then((nextRecords) => {
      setRecords(nextRecords)
      const pending = window.sessionStorage.getItem("ceaser_pending_plugin")
      if (pending && nextRecords.some((record) => record.id === pending && record.connected)) {
        trackEvent("plugin_connected", { plugin_name: pending })
        window.sessionStorage.removeItem("ceaser_pending_plugin")
      }
    }).catch(() => setRecords([])).finally(() => setLoading(false))
  }, [])
  const status = (id: string) => records.find((record) => record.id === id)
  const connectedCount = records.filter((record) => record.connected).length
  const filtered = useMemo(() => plugins.filter((plugin) => (category === "All" || category === "Recommended" && plugins.indexOf(plugin) < 4 || plugin.category === category) && `${plugin.name} ${plugin.description}`.toLowerCase().includes(query.toLowerCase())), [category, query])
  async function connect(plugin: Plugin) { if (!live.has(plugin.id)) return setSelected(plugin); trackEvent("plugin_connect_started", { plugin_name: plugin.id }); window.sessionStorage.setItem("ceaser_pending_plugin", plugin.id); setBusy(plugin.id); try { const result = await integrationsApi.connect(plugin.id); if (result.auth_url) window.location.href = result.auth_url; else { trackEvent("plugin_connected", { plugin_name: plugin.id }); window.sessionStorage.removeItem("ceaser_pending_plugin"); setRecords(await integrationsApi.list()) } } finally { setBusy(null) } }
  async function disconnect(plugin: Plugin) { setBusy(plugin.id); try { await integrationsApi.disconnect(plugin.id); setRecords(await integrationsApi.list()) } finally { setBusy(null) } }

  return <div className="h-full overflow-y-auto bg-[#03060d] text-white">
    <div className="mx-auto max-w-[1500px] px-8 py-9">
      <section className="relative grid min-h-[270px] grid-cols-[1fr_1.1fr] items-center overflow-hidden border-b border-white/[0.07] pb-7">
        <div><p className="text-xs font-semibold uppercase tracking-[0.18em] text-violet-400">Plugins</p><h1 className="mt-4 text-5xl font-semibold leading-[1.02]">One Command.<br/><span className="bg-gradient-to-r from-cyan-400 to-violet-500 bg-clip-text text-transparent">Every App.</span></h1><p className="mt-4 max-w-md text-base leading-7 text-white/60">Connect your favorite apps and services to let CEASER do more, together.</p><label className="mt-6 flex h-12 max-w-md items-center gap-3 rounded-xl border border-white/10 bg-white/[0.045] px-4"><Search className="h-4 w-4 text-white/40"/><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search plugins..." className="w-full bg-transparent text-sm outline-none placeholder:text-white/35"/></label></div>
        <div className="hidden lg:block" aria-hidden="true" />
      </section>
      <div className="mt-5 flex items-center gap-2 overflow-x-auto border-b border-white/[0.07] pb-4">{categories.map((item) => <button key={item} onClick={() => setCategory(item)} className={cn("shrink-0 rounded-lg px-4 py-2 text-xs text-white/55 hover:text-white", category === item && "bg-gradient-to-r from-blue-600 to-violet-600 text-white")}>{item}</button>)}</div>
      <div className="mt-5 rounded-xl border border-cyan-400/20 bg-cyan-400/[0.06] px-4 py-3"><p className="text-sm font-semibold text-white">CEASER Integrations <span className="ml-2 rounded-md bg-cyan-400/15 px-2 py-1 text-[10px] uppercase tracking-[0.14em] text-cyan-300">Beta</span></p><p className="mt-1 text-xs text-white/55">Connect the tools you already use. More integrations are coming soon.</p></div>
      <div className="mt-7 grid grid-cols-[190px_1fr] gap-7">
        <aside><p className="mb-3 text-[10px] uppercase tracking-[0.14em] text-white/42">Categories</p>{categories.filter((item) => item !== "Recommended").map((item) => <button key={item} onClick={() => setCategory(item)} className={cn("flex h-9 w-full items-center justify-between rounded-lg px-3 text-left text-xs text-white/58 hover:bg-white/[0.05]", category === item && "bg-violet-500/15 text-violet-300")}><span>{item === "All" ? "All Plugins" : item}</span><span>{item === "All" ? plugins.length : plugins.filter((p) => p.category === item).length}</span></button>)}<p className="mb-3 mt-8 text-[10px] uppercase tracking-[0.14em] text-white/42">Status</p><p className="px-3 text-xs text-emerald-400">Connected <span className="float-right">{connectedCount}</span></p><p className="mt-3 px-3 text-xs text-white/45">Available <span className="float-right">{plugins.length}</span></p></aside>
        <main>{loading ? <div className="flex h-48 items-center justify-center text-white/45"><Loader2 className="mr-2 h-5 w-5 animate-spin"/>Loading plugins</div> : <><div className="mb-3 flex items-center justify-between"><h2 className="text-sm font-semibold">Recommended for you</h2><button className="text-xs text-blue-300">View all</button></div><div className="grid grid-cols-2 gap-3 xl:grid-cols-4">{filtered.slice(0,4).map((plugin) => <FeaturedCard key={plugin.id} plugin={plugin} record={status(plugin.id)} busy={busy === plugin.id} onOpen={() => setSelected(plugin)} onConnect={() => void connect(plugin)} />)}</div><div className="mb-3 mt-7 flex items-center justify-between"><h2 className="text-sm font-semibold">All Plugins</h2><span className="text-xs text-white/40">{filtered.length} plugins</span></div><div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-5">{filtered.map((plugin) => <CompactCard key={plugin.id} plugin={plugin} connected={Boolean(status(plugin.id)?.connected)} onClick={() => setSelected(plugin)} />)}</div></>}</main>
      </div>
    </div>
    {selected && <PluginModal plugin={selected} record={status(selected.id)} busy={busy === selected.id} onClose={() => setSelected(null)} onConnect={() => void connect(selected)} onDisconnect={() => void disconnect(selected)} />}
  </div>
}

function Logo({ plugin, size="md" }: { plugin: Plugin; size?: "sm"|"md"|"lg" }) {
  const [failed, setFailed] = useState(false)
  const box = size === "sm" ? "h-9 w-9" : size === "lg" ? "h-14 w-14" : "h-12 w-12"
  return <span className={cn("flex shrink-0 items-center justify-center overflow-hidden rounded-xl bg-white", box)}>
    {failed ? <span className="text-sm font-bold text-slate-700">{plugin.name.charAt(0)}</span> : <img src={`https://cdn.simpleicons.org/${plugin.icon}`} alt={`${plugin.name} icon`} onError={() => setFailed(true)} className={cn("object-contain", size === "sm" ? "h-6 w-6" : "h-8 w-8")} />}
  </span>
}
function FeaturedCard({ plugin, record, busy, onOpen, onConnect }: { plugin: Plugin; record?: IntegrationRecord; busy: boolean; onOpen: () => void; onConnect: () => void }) { return <article className="flex min-h-[210px] flex-col rounded-xl border border-white/[0.09] bg-[#0a0f1c] p-4"><div className="flex items-start justify-between"><Logo plugin={plugin}/>{record?.connected && <span className="rounded-md bg-emerald-500/12 px-2 py-1 text-[10px] text-emerald-400">Connected</span>}</div><h3 className="mt-3 text-sm font-semibold">{plugin.name}</h3><p className="mt-2 flex-1 text-xs leading-5 text-white/48">{plugin.description}</p><div className="mt-4 flex gap-2"><button onClick={record?.connected ? onOpen : onConnect} disabled={busy} className="h-8 flex-1 rounded-lg bg-white/[0.07] text-xs hover:bg-white/[0.11]">{busy ? "Opening..." : record?.connected ? "Manage" : live.has(plugin.id) ? "Connect" : "View"}</button><button onClick={onOpen} className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/[0.07]"><MoreHorizontal className="h-4 w-4"/></button></div></article> }
function CompactCard({ plugin, connected, onClick }: { plugin: Plugin; connected: boolean; onClick: () => void }) { return <button onClick={onClick} className="flex min-h-[76px] items-center gap-3 rounded-xl border border-white/[0.08] bg-[#0a0f1c] p-3 text-left hover:border-violet-400/30"><Logo plugin={plugin} size="sm"/><span className="min-w-0"><span className="block truncate text-xs font-medium">{plugin.name}</span><span className={cn("mt-1 block text-[10px]", connected ? "text-emerald-400" : live.has(plugin.id) ? "text-cyan-300" : "text-white/45")}>{connected ? "Connected" : live.has(plugin.id) ? "Beta" : "Coming Soon"}</span></span></button> }
function PluginModal({ plugin, record, busy, onClose, onConnect, onDisconnect }: { plugin: Plugin; record?: IntegrationRecord; busy: boolean; onClose: () => void; onConnect: () => void; onDisconnect: () => void }) { const services=plugin.services || [plugin.name]; return <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/70 p-6 backdrop-blur-sm" onMouseDown={(e) => e.target === e.currentTarget && onClose()}><section className="max-h-[86vh] w-full max-w-[650px] overflow-y-auto rounded-2xl border border-white/10 bg-[#0b111d] p-6 shadow-2xl"><header className="flex items-start gap-4"><Logo plugin={plugin} size="lg"/><div className="min-w-0 flex-1"><div className="flex items-center gap-2"><h2 className="text-xl font-semibold">{plugin.name}</h2>{record?.connected && <span className="rounded-md bg-emerald-500/12 px-2 py-1 text-[10px] text-emerald-400">Connected</span>}</div><p className="mt-1 text-xs text-white/48">{record?.account_email || (record?.connected ? "Connected to CEASER" : "Not connected")}</p></div><button onClick={onClose} className="flex h-9 w-9 items-center justify-center rounded-full bg-white/[0.06]"><X className="h-4 w-4"/></button></header><nav className="mt-6 flex gap-7 border-b border-white/10 text-xs text-white/55"><button className="border-b-2 border-violet-500 pb-3 text-white">Overview</button><button className="pb-3">Permissions</button><button className="pb-3">Connected Services</button><button className="pb-3">Activity</button><button className="pb-3">Settings</button></nav><div className="mt-4 flex gap-3 rounded-xl border border-white/10 bg-white/[0.025] p-4"><ShieldCheck className="h-5 w-5 text-violet-400"/><p className="text-xs leading-5 text-white/65">CEASER accesses {plugin.name} data only when you ask. You remain in control and can revoke access at any time.</p></div><div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">{services.map((service) => <div key={service} className="rounded-xl border border-white/10 bg-white/[0.025] p-4"><h3 className="text-sm font-medium">{service}</h3><p className="mt-2 text-xs leading-5 text-white/45">Access and manage supported {service} content.</p><p className={cn("mt-3 flex items-center gap-1 text-xs", record?.connected ? "text-emerald-400" : "text-white/35")}>{record?.connected && <Check className="h-3 w-3"/>}{record?.connected ? "Connected" : "Not connected"}<ChevronRight className="ml-auto h-3 w-3"/></p></div>)}</div><h3 className="mb-2 mt-5 text-sm font-medium">Permissions Summary</h3><div className="grid grid-cols-3 rounded-xl border border-white/10 bg-white/[0.025] p-4 text-center"><div><ShieldCheck className="mx-auto h-5 w-5 text-emerald-400"/><strong className="mt-2 block text-xl">{record?.permissions?.length || 0}</strong><span className="text-[10px] text-white/40">Granted</span></div><div><strong className="mt-7 block text-base">{record?.last_sync_at ? "Recently" : "Never"}</strong><span className="text-[10px] text-white/40">Last access</span></div><div><strong className="mt-7 block text-base">{record?.token_expires_at ? "Active" : "N/A"}</strong><span className="text-[10px] text-white/40">Token</span></div></div><div className="mt-5 flex justify-end">{record?.connected ? <button onClick={onDisconnect} disabled={busy} className="rounded-lg border border-red-500/40 px-4 py-2 text-xs text-red-400">Disconnect {plugin.name}</button> : <button onClick={onConnect} disabled={busy || !live.has(plugin.id)} className="rounded-lg bg-violet-600 px-5 py-2 text-xs font-semibold disabled:opacity-45">{live.has(plugin.id) ? "Connect" : "Coming soon"}</button>}</div></section></div> }
