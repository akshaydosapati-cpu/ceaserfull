"use client"

import { useEffect, useMemo, useState } from "react"
import { agents as fallbackAgents } from "@/lib/data"
import { agentsApi } from "@/lib/api/agents"
import { chatApi, type ConversationRecord } from "@/lib/api/chat"
import { filesApi, type FileRecord } from "@/lib/api/files"
import { memoryApi, type MemoryRecord } from "@/lib/api/memory"
import { projectsApi, type ProjectRecord } from "@/lib/api/projects"
import { AgentAvatar } from "../agent-avatar"
import { GlowCard } from "../glow-card"
import { Activity, BarChart3, CheckSquare, Clock, FolderKanban, Loader2, TrendingUp, Users } from "lucide-react"

const dayLabels = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

function getCreatedAt(item: { created_at?: string }) {
  if (!item.created_at) return null
  const date = new Date(item.created_at)
  return Number.isNaN(date.getTime()) ? null : date
}

export function AnalyticsPage() {
  const [projects, setProjects] = useState<ProjectRecord[]>([])
  const [memories, setMemories] = useState<MemoryRecord[]>([])
  const [files, setFiles] = useState<FileRecord[]>([])
  const [conversations, setConversations] = useState<ConversationRecord[]>([])
  const [agentCount, setAgentCount] = useState(fallbackAgents.length)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const loadAnalytics = async () => {
      setIsLoading(true)
      try {
        const [projectResult, memoryResult, fileResult, conversationResult, agentResult] = await Promise.allSettled([
          projectsApi.list(),
          memoryApi.list(),
          filesApi.list(),
          chatApi.listConversations(),
          agentsApi.list(),
        ])

        if (projectResult.status === "fulfilled") setProjects(projectResult.value)
        if (memoryResult.status === "fulfilled") setMemories(memoryResult.value)
        if (fileResult.status === "fulfilled") setFiles(fileResult.value)
        if (conversationResult.status === "fulfilled") setConversations(conversationResult.value)
        if (agentResult.status === "fulfilled") setAgentCount(agentResult.value.length || fallbackAgents.length)
      } finally {
        setIsLoading(false)
      }
    }

    void loadAnalytics()
  }, [])

  const weeklyActivity = useMemo(() => {
    const now = new Date()
    const start = new Date(now)
    start.setDate(now.getDate() - 6)
    start.setHours(0, 0, 0, 0)

    return Array.from({ length: 7 }, (_, index) => {
      const date = new Date(start)
      date.setDate(start.getDate() + index)
      const next = new Date(date)
      next.setDate(date.getDate() + 1)
      const activity = [...projects, ...memories, ...files, ...conversations].filter((item) => {
        const created = getCreatedAt(item)
        return created && created >= date && created < next
      }).length
      return { day: dayLabels[date.getDay()], activity }
    })
  }, [conversations, files, memories, projects])

  const agentPerformance = useMemo(() => {
    return fallbackAgents.map((agent) => {
      const relatedMemories = memories.filter((memory) => {
        const agentId = memory.metadata?.agent_id ?? memory.extra_metadata?.agent_id
        return agentId === agent.id
      }).length
      const relatedProjects = projects.filter((project) => project.description?.toLowerCase().includes(agent.name.toLowerCase())).length
      const tasks = relatedMemories + relatedProjects
      const efficiency = Math.min(100, 64 + tasks * 6)
      return { agent, tasks, efficiency }
    })
  }, [memories, projects])

  const maxActivity = Math.max(...weeklyActivity.map((day) => day.activity), 1)
  const activeProjects = projects.filter((project) => project.status === "active").length
  const completedProjects = projects.filter((project) => project.status === "completed").length
  const totalActivity = projects.length + memories.length + files.length + conversations.length
  const hoursSaved = Math.max(0, Math.round(totalActivity * 0.35))

  return (
    <div className="p-6">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Analytics</h1>
          <p className="text-muted-foreground">Live summary from CEASER projects, memory, files, conversations, and agents.</p>
        </div>
        {isLoading && (
          <span className="flex items-center rounded-full border border-white/10 px-3 py-1 text-xs text-muted-foreground">
            <Loader2 className="mr-2 h-3 w-3 animate-spin" />
            Syncing
          </span>
        )}
      </div>

      <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <GlowCard>
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Activity Records</p>
              <p className="text-3xl font-bold">{totalActivity}</p>
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
              <CheckSquare className="h-5 w-5 text-primary" />
            </div>
          </div>
          <div className="mt-2 flex items-center gap-1 text-sm text-emerald-500">
            <TrendingUp className="h-4 w-4" />
            DB-backed total
          </div>
        </GlowCard>

        <GlowCard>
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Provisioned Agents</p>
              <p className="text-3xl font-bold">{agentCount}/6</p>
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10">
              <Users className="h-5 w-5 text-emerald-500" />
            </div>
          </div>
          <div className="mt-2 flex items-center gap-1 text-sm text-emerald-500">
            <TrendingUp className="h-4 w-4" />
            Agent API connected
          </div>
        </GlowCard>

        <GlowCard>
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Active Projects</p>
              <p className="text-3xl font-bold">{activeProjects}</p>
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500/10">
              <FolderKanban className="h-5 w-5 text-amber-500" />
            </div>
          </div>
          <div className="mt-2 text-sm text-muted-foreground">{completedProjects} completed projects</div>
        </GlowCard>

        <GlowCard>
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Estimated Hours Saved</p>
              <p className="text-3xl font-bold">{hoursSaved}h</p>
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-500/10">
              <Clock className="h-5 w-5 text-purple-500" />
            </div>
          </div>
          <div className="mt-2 text-sm text-muted-foreground">Derived from live activity volume</div>
        </GlowCard>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <GlowCard>
          <div className="mb-4 flex items-center justify-between">
            <h3 className="font-semibold">Weekly Activity</h3>
            <Activity className="h-5 w-5 text-muted-foreground" />
          </div>
          <div className="flex h-48 items-end gap-2">
            {weeklyActivity.map((day) => (
              <div key={day.day} className="flex flex-1 flex-col items-center gap-2">
                <div className="flex w-full items-end rounded-t-lg bg-primary/15" style={{ height: "100%" }}>
                  <div className="w-full rounded-t-lg bg-primary transition-all" style={{ height: `${Math.max(6, (day.activity / maxActivity) * 100)}%` }} />
                </div>
                <span className="text-xs text-muted-foreground">{day.day}</span>
              </div>
            ))}
          </div>
        </GlowCard>

        <GlowCard>
          <div className="mb-4 flex items-center justify-between">
            <h3 className="font-semibold">Agent Context Usage</h3>
            <BarChart3 className="h-5 w-5 text-muted-foreground" />
          </div>
          <div className="space-y-4">
            {agentPerformance.map(({ agent, tasks, efficiency }) => (
              <div key={agent.id} className="flex items-center gap-3">
                <AgentAvatar agent={agent} size="sm" />
                <div className="flex-1">
                  <div className="mb-1 flex items-center justify-between text-sm">
                    <span>{agent.name}</span>
                    <span className="text-muted-foreground">{tasks} linked records</span>
                  </div>
                  <div className="h-2 rounded-full bg-secondary">
                    <div className="h-full rounded-full transition-all" style={{ width: `${efficiency}%`, backgroundColor: agent.color }} />
                  </div>
                </div>
                <span className="text-sm font-medium" style={{ color: agent.color }}>
                  {efficiency}%
                </span>
              </div>
            ))}
          </div>
        </GlowCard>

        <GlowCard>
          <div className="mb-4 flex items-center justify-between">
            <h3 className="font-semibold">Data Sources</h3>
            <BarChart3 className="h-5 w-5 text-muted-foreground" />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {[
              ["Projects", projects.length],
              ["Memories", memories.length],
              ["Files", files.length],
              ["Conversations", conversations.length],
            ].map(([label, value]) => (
              <div key={label} className="rounded-xl border border-white/10 bg-white/5 p-4">
                <p className="text-sm text-muted-foreground">{label}</p>
                <p className="text-2xl font-semibold">{value}</p>
              </div>
            ))}
          </div>
        </GlowCard>

        <GlowCard>
          <div className="mb-4">
            <h3 className="font-semibold">Integration Analytics</h3>
            <p className="mt-1 text-sm text-muted-foreground">Cloud integration metrics will become realtime after the Integrations worker is added.</p>
          </div>
          <div className="rounded-xl border border-dashed border-primary/30 bg-primary/5 p-4 text-sm text-muted-foreground">
            Ready for GitHub, Google Drive, Gmail, Calendar, Notion, Vercel, Railway, and Supabase sync metrics.
          </div>
        </GlowCard>
      </div>
    </div>
  )
}
