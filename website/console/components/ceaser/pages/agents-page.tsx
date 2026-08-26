"use client"

import { useEffect, useMemo, useState } from "react"
import type { ReactNode } from "react"
import { draftsApi, type AgentWorkbenchRecord, type DraftHistoryRecord, type DraftRecord } from "@/lib/api/drafts"
import { agentsApi } from "@/lib/api/agents"
import { agents, type Agent } from "@/lib/data"
import { useApp } from "@/lib/app-context"
import { useAgentStore } from "@/lib/stores/agent-store"
import { cn } from "@/lib/utils"
import { AgentAvatar } from "../agent-avatar"
import { CheckCircle2, Clock3, MessageSquare, Settings2 } from "lucide-react"

const capabilityMap: Record<string, string[]> = {
  nova: ["Research", "Reports", "Analysis"],
  zeus: ["Strategy", "Planning", "Business"],
  friday: ["Content", "Social", "Campaigns"],
  alex: ["Learning", "Notes", "Flashcards"],
  bolt: ["Tasks", "Roadmaps", "Execution"],
  atlas: ["Engineering", "Docs", "Architecture"],
}

const descriptions: Record<string, string> = {
  nova: "Research, analyze, and find insights from the web and your data.",
  zeus: "Business plans, pitch decks, strategy, GTM, and revenue models.",
  friday: "Content calendars, social posts, campaigns, scripts, and messaging.",
  alex: "Study plans, notes, MCQs, flashcards, goals, and exam preparation.",
  bolt: "Task plans, roadmaps, follow-ups, execution reviews, and deadlines.",
  atlas: "Technical docs, architecture, PRDs, code explanation, and project reports.",
}

const exampleCommands: Record<string, string[]> = {
  nova: ["Research healthtech startups in India", "Find competitors for Clinilocker", "Create a market research report"],
  zeus: ["Create a business plan for Clinilocker", "Create a pitch deck", "Build a go-to-market strategy"],
  friday: ["Create LinkedIn post ideas", "Plan a launch campaign", "Write a product announcement"],
  alex: ["Create study notes", "Make MCQs from this topic", "Prepare an exam revision plan"],
  bolt: ["Create a launch roadmap", "Break this project into tasks", "Plan follow-ups for this week"],
  atlas: ["Create technical architecture", "Write a PRD", "Explain this codebase"],
}

const statusLabel = (workbench?: AgentWorkbenchRecord) => {
  if (workbench?.drafts.some((draft) => draft.status !== "approved" && draft.status !== "archived")) return "Working"
  return "Active"
}

export function AgentsPage() {
  const { selectedAgentId, setSelectedAgentId, setCurrentPage, setConfigAgentId, setIsAgentConfigOpen } = useApp()
  const { initializeAgent, isAgentEnabled, setAgentEnabled } = useAgentStore()
  const [agentData, setAgentData] = useState<Record<string, AgentWorkbenchRecord>>({})
  const [backendAgentIds, setBackendAgentIds] = useState<Record<string, string>>({})
  const [syncingAgentId, setSyncingAgentId] = useState<string | null>(null)
  const [filter, setFilter] = useState<"all" | "active" | "recent">("all")
  const selectedAgent = agents.find((agent) => agent.id === selectedAgentId) ?? agents[0]
  const selectedWorkbench = agentData[selectedAgent.id]

  useEffect(() => {
    agents.forEach((agent) => initializeAgent(agent.id))
    const load = async () => {
      const [agentResults, workbenchResults] = await Promise.all([
        agentsApi.list().catch(() => []),
        Promise.allSettled(agents.map(async (agent) => [agent.id, await draftsApi.agentWorkbench(agent.id)] as const)),
      ])
      const idMap: Record<string, string> = {}
      agentResults.forEach((record) => {
        const uiAgentId = record.name.toLowerCase()
        idMap[uiAgentId] = record.id
        setAgentEnabled(uiAgentId, record.enabled)
      })
      setBackendAgentIds(idMap)
      setAgentData(Object.fromEntries(workbenchResults.flatMap((result) => (result.status === "fulfilled" ? [result.value] : []))))
    }
    void load()
  }, [initializeAgent, setAgentEnabled])

  const syncAgentEnabled = async (agentId: string, enabled: boolean) => {
    setSyncingAgentId(agentId)
    setAgentEnabled(agentId, enabled)
    try {
      const backendId = backendAgentIds[agentId]
      if (backendId) {
        const updated = enabled ? await agentsApi.enable(backendId) : await agentsApi.disable(backendId)
        setAgentEnabled(agentId, updated.enabled)
      }
    } catch {
      setAgentEnabled(agentId, !enabled)
    } finally {
      setSyncingAgentId(null)
    }
  }

  const filteredAgents = useMemo(() => {
    return agents.filter((agent) => {
      const workbench = agentData[agent.id]
      const matchesFilter =
        filter === "all" ||
        (filter === "active" && agent.status === "active" && isAgentEnabled(agent.id)) ||
        (filter === "recent" && Boolean(workbench?.activity.length || workbench?.drafts.length))
      return matchesFilter
    })
  }, [agentData, filter, isAgentEnabled])

  const recentActivity = useMemo(() => Object.values(agentData).flatMap((item) => item.activity).sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()), [agentData])

  const askInChat = (agent: Agent, seed?: string) => {
    setSelectedAgentId(agent.id)
    if (typeof window !== "undefined") {
      window.localStorage.setItem("ceaser_chat_agent_context", agent.id)
      if (seed) window.localStorage.setItem("ceaser_chat_seed", seed)
    }
    setCurrentPage("chat")
  }

  return (
    <div className="h-full overflow-hidden bg-[#050914] text-foreground">
      <div className="grid h-full grid-cols-[minmax(0,1fr)_360px]">
        <main className="overflow-y-auto border-r border-white/10 px-8 py-7">
          <div className="mb-7">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-violet-300">AI Workforce</p>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight">AI Workforce</h1>
              <p className="mt-2 max-w-xl text-sm text-slate-400">Specialized agents that help CEASER complete work. Creation happens in Chat; this screen shows what each agent does.</p>
            </div>
          </div>

          <div className="mb-6 flex gap-2">
            {[
              ["all", "All Agents"],
              ["active", "Active"],
              ["recent", "Recently Used"],
            ].map(([value, label]) => (
              <button key={value} onClick={() => setFilter(value as typeof filter)} className={cn("rounded-xl px-4 py-2 text-xs font-medium transition", filter === value ? "bg-violet-600 text-white shadow-[0_0_24px_rgba(124,58,237,0.35)]" : "border border-white/10 bg-white/[0.04] text-slate-400 hover:text-white")}>
                {label}
              </button>
            ))}
          </div>

          <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
            {filteredAgents.map((agent) => (
              <AgentCard
                key={agent.id}
                agent={agent}
                workbench={agentData[agent.id]}
                active={agent.id === selectedAgent.id}
                enabled={isAgentEnabled(agent.id)}
                onSelect={() => setSelectedAgentId(agent.id)}
                onAsk={() => askInChat(agent, exampleCommands[agent.id]?.[0])}
                onToggle={() => void syncAgentEnabled(agent.id, !isAgentEnabled(agent.id))}
                syncing={syncingAgentId === agent.id}
                onSettings={() => {
                  setConfigAgentId(agent.id)
                  setIsAgentConfigOpen(true)
                }}
              />
            ))}
          </div>

        </main>

        <aside className="overflow-y-auto bg-[#070c18]/90 p-6">
          <div className="rounded-3xl border border-white/10 bg-white/[0.045] p-5 shadow-[0_24px_80px_rgba(0,0,0,0.28)]">
            <div className="flex items-start gap-4">
              <AgentAvatar agent={selectedAgent} size="lg" showStatus showGlow enabled={isAgentEnabled(selectedAgent.id)} />
              <div>
                <h2 className="text-xl font-semibold">{selectedAgent.name}</h2>
                <p className="text-sm text-slate-400">{selectedAgent.role.replace(" Agent", "")}</p>
              <StatusPill status={isAgentEnabled(selectedAgent.id) ? statusLabel(selectedWorkbench) : "Disabled"} />
              </div>
            </div>
            <p className="mt-5 text-sm leading-6 text-slate-300">{descriptions[selectedAgent.id] ?? selectedAgent.description}</p>

            <Section title="Best At">
              <div className="flex flex-wrap gap-2">
                {(capabilityMap[selectedAgent.id] ?? selectedAgent.capabilities).map((capability) => (
                  <span key={capability} className="rounded-lg border border-white/10 bg-white/[0.05] px-2.5 py-1 text-xs text-slate-300">{capability}</span>
                ))}
              </div>
            </Section>

            <Section title="Example Commands">
              <div className="space-y-2">
                {(exampleCommands[selectedAgent.id] ?? []).map((command) => (
                  <button key={command} onClick={() => askInChat(selectedAgent, command)} className="w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-left text-xs text-slate-300 transition hover:border-violet-400/40 hover:text-white">
                    {command}
                  </button>
                ))}
              </div>
            </Section>

            <Section title="Recent Work">
              <div className="space-y-2">
                {(selectedWorkbench?.drafts ?? []).slice(0, 4).map((draft) => <DraftLine key={draft.id} draft={draft} />)}
                {!selectedWorkbench?.drafts?.length && <p className="rounded-xl border border-white/10 bg-black/20 p-3 text-xs text-slate-400">{selectedAgent.name} has not created anything yet. Ask {selectedAgent.name} in Chat to start.</p>}
              </div>
            </Section>

            <button onClick={() => askInChat(selectedAgent, exampleCommands[selectedAgent.id]?.[0])} className="mt-5 flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-violet-600 text-sm font-semibold text-white shadow-[0_0_28px_rgba(124,58,237,0.35)] transition hover:bg-violet-500">
              <MessageSquare className="h-4 w-4" />
              Ask {selectedAgent.name} in Chat
            </button>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <button onClick={() => void syncAgentEnabled(selectedAgent.id, !isAgentEnabled(selectedAgent.id))} disabled={syncingAgentId === selectedAgent.id} className="rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm font-semibold text-slate-200 transition hover:bg-white/10 disabled:opacity-50">
                {syncingAgentId === selectedAgent.id ? "Saving" : isAgentEnabled(selectedAgent.id) ? "Disable" : "Enable"}
              </button>
              <button onClick={() => { setConfigAgentId(selectedAgent.id); setIsAgentConfigOpen(true) }} className="rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm font-semibold text-slate-200 transition hover:bg-white/10">
                Settings
              </button>
            </div>
          </div>

          <div className="mt-4 rounded-3xl border border-white/10 bg-white/[0.035] p-5">
            <p className="mb-3 text-sm font-semibold">Live Activity</p>
            <div className="space-y-2">
              {recentActivity.slice(0, 5).map((activity) => <ActivityLine key={activity.id} activity={activity} />)}
              {!recentActivity.length && <p className="text-xs text-slate-500">No agent activity yet.</p>}
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}

function AgentCard({
  agent,
  workbench,
  active,
  enabled,
  onSelect,
  onAsk,
  onToggle,
  syncing,
  onSettings,
}: {
  agent: Agent
  workbench?: AgentWorkbenchRecord
  active: boolean
  enabled: boolean
  onSelect: () => void
  onAsk: () => void
  onToggle: () => void
  syncing: boolean
  onSettings: () => void
}) {
  const status = statusLabel(workbench)
  const outputs = workbench?.drafts.length ?? 0
  return (
    <article onClick={onSelect} className={cn("group rounded-3xl border bg-white/[0.04] p-5 transition", active ? "border-violet-400/70 shadow-[0_0_35px_rgba(124,58,237,0.22)]" : "border-white/10 hover:border-white/20", !enabled && "opacity-55")}>
      <div className="mb-5 flex items-start justify-between">
        <div className="flex items-center gap-3">
          <AgentAvatar agent={agent} size="md" showGlow />
          <div>
            <h3 className="text-lg font-semibold">{agent.name}</h3>
            <p className="text-xs text-slate-400">{agent.role.replace(" Agent", "")}</p>
          </div>
        </div>
        {enabled && agent.status === "active" && <span className="h-2 w-2 rounded-full bg-emerald-400" />}
      </div>
      <p className="min-h-[72px] text-sm leading-6 text-slate-300">{descriptions[agent.id] ?? agent.description}</p>
      <div className="mt-5 flex items-center justify-between border-t border-white/10 pt-4 text-xs text-slate-400">
        <span>Recent Work</span>
        <span className="text-slate-200">{outputs} outputs</span>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {(capabilityMap[agent.id] ?? agent.capabilities).slice(0, 3).map((capability) => <span key={capability} className="rounded-lg bg-white/[0.06] px-2 py-1 text-[11px] text-slate-300">{capability}</span>)}
      </div>
      <div className="mt-5 grid grid-cols-[1fr_auto_auto] gap-2">
        <button onClick={(event) => { event.stopPropagation(); onAsk() }} disabled={!enabled} className="flex h-10 items-center justify-center gap-2 rounded-xl border border-violet-400/40 text-sm font-medium text-violet-200 transition hover:bg-violet-500/15 disabled:cursor-not-allowed disabled:opacity-45">
          <MessageSquare className="h-4 w-4" />
          Ask in Chat
        </button>
        <button disabled={syncing} onClick={(event) => { event.stopPropagation(); onToggle() }} className={cn("h-10 rounded-xl border px-3 text-xs font-semibold transition disabled:opacity-50", enabled ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-200 hover:bg-emerald-500/16" : "border-slate-400/20 bg-slate-500/10 text-slate-300 hover:bg-slate-500/16")}>
          {syncing ? "Saving" : enabled ? "Disable" : "Enable"}
        </button>
        <button onClick={(event) => { event.stopPropagation(); onSettings() }} className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 text-slate-300 transition hover:bg-white/10">
          <Settings2 className="h-4 w-4" />
        </button>
      </div>
    </article>
  )
}

function StatusPill({ status }: { status: string }) {
  return <span className={cn("mt-2 inline-flex rounded-full px-2.5 py-1 text-xs font-medium", status === "Disabled" ? "bg-slate-500/15 text-slate-300" : "bg-emerald-500/15 text-emerald-300")}>{status}</span>
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mt-5 border-t border-white/10 pt-4">
      <p className="mb-3 text-sm font-semibold">{title}</p>
      {children}
    </div>
  )
}

function DraftLine({ draft }: { draft: DraftRecord }) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/20 p-3">
      <div className="flex items-center justify-between gap-3">
        <p className="truncate text-sm font-medium">{draft.title}</p>
        <span className="text-xs text-slate-500">{draft.progress}%</span>
      </div>
      <p className="mt-1 text-xs capitalize text-slate-500">{draft.draft_type.replaceAll("_", " ")}</p>
    </div>
  )
}

function ActivityLine({ activity }: { activity: DraftHistoryRecord }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-white/10 bg-black/20 p-3">
      <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-300" />
      <div className="min-w-0">
        <p className="truncate text-sm font-medium capitalize">{activity.action}</p>
        <p className="truncate text-xs text-slate-500">{activity.detail}</p>
      </div>
      <Clock3 className="ml-auto h-3.5 w-3.5 shrink-0 text-slate-600" />
    </div>
  )
}


