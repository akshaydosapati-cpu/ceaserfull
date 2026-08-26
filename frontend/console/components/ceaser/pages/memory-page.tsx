"use client"

import { useEffect, useMemo, useState } from "react"
import { agents } from "@/lib/data"
import { memoryApi, type MemoryRecord } from "@/lib/api/memory"
import { useApp } from "@/lib/app-context"
import { AgentAvatar } from "../agent-avatar"
import { CeaserSelect } from "../ceaser-select"
import { GlowCard } from "../glow-card"
import { cn } from "@/lib/utils"
import {
  ChevronRight,
  FileText,
  Filter,
  FolderKanban,
  Loader2,
  MessageSquare,
  Plus,
  Search,
  StickyNote,
  Target,
  Trash2,
  Users,
  X,
} from "lucide-react"

type BackendMemoryType = "conversation" | "goal" | "project" | "decision" | "file" | "research"

const memoryFilters: { label: string; value: BackendMemoryType | "all" }[] = [
  { label: "All", value: "all" },
  { label: "Conversations", value: "conversation" },
  { label: "Projects", value: "project" },
  { label: "Goals", value: "goal" },
  { label: "Files", value: "file" },
  { label: "Decisions", value: "decision" },
  { label: "Research", value: "research" },
]

const memoryViews = ["Timeline", "Search", "Linked Memories"] as const

function getMemoryTitle(memory: MemoryRecord) {
  const metadataTitle = memory.metadata?.title ?? memory.extra_metadata?.title
  if (typeof metadataTitle === "string" && metadataTitle.trim()) return metadataTitle
  return memory.content.split("\n")[0]?.slice(0, 80) || "Untitled memory"
}

function getAgentId(memory: MemoryRecord) {
  const agentId = memory.metadata?.agent_id ?? memory.extra_metadata?.agent_id
  return typeof agentId === "string" ? agentId : undefined
}

function formatDate(value?: string) {
  if (!value) return "Recently"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "Recently"
  return date.toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })
}

export function MemoryPage() {
  const { confirmDialog, currentPage } = useApp()
  const [memories, setMemories] = useState<MemoryRecord[]>([])
  const [searchQuery, setSearchQuery] = useState("")
  const [filterType, setFilterType] = useState<BackendMemoryType | "all">("all")
  const [isLoading, setIsLoading] = useState(true)
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const [selectedMemory, setSelectedMemory] = useState<MemoryRecord | null>(null)
  const [activeView, setActiveView] = useState<(typeof memoryViews)[number]>("Timeline")
  const [newMemory, setNewMemory] = useState({
    title: "",
    description: "",
    type: "decision" as BackendMemoryType,
    agentId: "",
  })

  const loadMemories = async () => {
    setIsLoading(true)
    try {
      const records = await memoryApi.list()
      setMemories(records)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (currentPage === "memory") void loadMemories()
  }, [currentPage])

  useEffect(() => {
    const refresh = () => {
      if (document.visibilityState === "visible") void loadMemories()
    }
    document.addEventListener("visibilitychange", refresh)
    window.addEventListener("focus", refresh)
    return () => {
      document.removeEventListener("visibilitychange", refresh)
      window.removeEventListener("focus", refresh)
    }
  }, [])

  const filteredMemories = useMemo(() => {
    const query = searchQuery.trim().toLowerCase()
    return memories.filter((memory) => {
      const matchesType = filterType === "all" || memory.memory_type === filterType
      const title = getMemoryTitle(memory).toLowerCase()
      const content = memory.content.toLowerCase()
      const matchesSearch = !query || title.includes(query) || content.includes(query)
      return matchesType && matchesSearch
    })
  }, [filterType, memories, searchQuery])

  const getMemoryIcon = (type: string) => {
    switch (type) {
      case "goal":
        return <Target className="h-5 w-5 text-primary" />
      case "conversation":
        return <MessageSquare className="h-5 w-5 text-muted-foreground" />
      case "project":
        return <FolderKanban className="h-5 w-5 text-muted-foreground" />
      case "research":
        return <Search className="h-5 w-5 text-muted-foreground" />
      case "file":
        return <FileText className="h-5 w-5 text-muted-foreground" />
      case "decision":
        return <StickyNote className="h-5 w-5 text-muted-foreground" />
      default:
        return <Users className="h-5 w-5 text-muted-foreground" />
    }
  }

  const handleAddMemory = async () => {
    if (!newMemory.title.trim()) return
    const content = [newMemory.title.trim(), newMemory.description.trim()].filter(Boolean).join("\n\n")
    const created = await memoryApi.create({
      memory_type: newMemory.type,
      content,
      metadata: {
        title: newMemory.title.trim(),
        agent_id: newMemory.agentId || undefined,
        source: "memory_page",
      },
    })
    setMemories((current) => [created, ...current])
    setNewMemory({ title: "", description: "", type: "decision", agentId: "" })
    setIsAddModalOpen(false)
  }

  const handleDeleteMemory = async (memory: MemoryRecord) => {
    const confirmed = await confirmDialog({
      title: `Delete "${getMemoryTitle(memory)}"?`,
      description: "This memory will be removed from CEASER and will no longer be used as context.",
      confirmLabel: "Delete",
      tone: "danger",
    })
    if (!confirmed) return
    await memoryApi.delete(memory.id)
    setMemories((current) => current.filter((item) => item.id !== memory.id))
    setSelectedMemory((current) => (current?.id === memory.id ? null : current))
  }

  return (
    <div className="flex h-full flex-col p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Memory</h1>
          <p className="text-sm text-muted-foreground">Encrypted memories from conversations, projects, files, and research.</p>
        </div>
        <button
          onClick={() => setIsAddModalOpen(true)}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          Add Memory
        </button>
      </div>

      <div className="mb-6 flex flex-wrap gap-2">
        {memoryViews.map((view) => (
          <button
            key={view}
            onClick={() => setActiveView(view)}
            className={cn(
              "rounded-lg px-4 py-2 text-sm transition-colors",
              activeView === view ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground hover:text-foreground",
            )}
          >
            {view}
          </button>
        ))}
      </div>

      <>
          <div className="mb-6 flex items-center gap-4">
            <div className="flex flex-1 items-center gap-2 rounded-lg border border-border bg-secondary/30 px-4 py-2">
              <Search className="h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="Search memories..."
                className="flex-1 bg-transparent outline-none placeholder:text-muted-foreground"
              />
              {searchQuery && (
                <button onClick={() => setSearchQuery("")} className="text-muted-foreground hover:text-foreground">
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
            <button className="flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm text-muted-foreground">
              <Filter className="h-4 w-4" />
            </button>
          </div>

          <div className="mb-6 flex flex-wrap gap-2">
            {memoryFilters.map((filter) => (
              <button
                key={filter.value}
                onClick={() => setFilterType(filter.value)}
                className={cn(
                  "rounded-lg px-4 py-2 text-sm transition-colors",
                  filterType === filter.value ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground hover:text-foreground",
                )}
              >
                {filter.label}
              </button>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto">
            {isLoading ? (
              <div className="flex items-center justify-center py-16 text-sm text-muted-foreground">
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Loading memory...
              </div>
            ) : (
              <div className="space-y-3">
                {filteredMemories.length > 0 ? (
                  filteredMemories.map((memory) => {
                    const agent = agents.find((item) => item.id === getAgentId(memory))
                    const title = getMemoryTitle(memory)

                    return (
                      <GlowCard key={memory.id} hover className="group cursor-pointer" onClick={() => setSelectedMemory(memory)}>
                        <div className="flex items-start gap-4">
                          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-secondary/50">{getMemoryIcon(memory.memory_type)}</div>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <h3 className="font-medium">{title}</h3>
                              {agent && <AgentAvatar agent={agent} size="sm" />}
                            </div>
                            <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{memory.content.replace(title, "").trim() || memory.content}</p>
                            <p className="mt-2 text-xs text-muted-foreground">
                              <span className="capitalize">{memory.memory_type}</span> · {formatDate(memory.created_at)}
                            </p>
                          </div>
                          <div className="flex items-center gap-2">
                            <button
                              onClick={(event) => {
                                event.stopPropagation()
                                void handleDeleteMemory(memory)
                              }}
                              className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground opacity-0 transition-all hover:bg-red-500/10 hover:text-red-400 group-hover:opacity-100"
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                            <ChevronRight className="h-5 w-5 text-muted-foreground" />
                          </div>
                        </div>
                      </GlowCard>
                    )
                  })
                ) : (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-secondary">
                      <Search className="h-8 w-8 text-muted-foreground" />
                    </div>
                    <p className="text-lg font-medium">No memories found</p>
                    <p className="text-sm text-muted-foreground">Memory is synced securely with your CEASER account.</p>
                  </div>
                )}
              </div>
            )}
          </div>
      </>

      {isAddModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4 backdrop-blur-sm" onClick={() => setIsAddModalOpen(false)}>
          <section className="w-full max-w-md overflow-hidden rounded-xl border border-border bg-card shadow-2xl" onClick={(event) => event.stopPropagation()}>
            <div className="flex items-center justify-between border-b border-border px-6 py-4">
              <h2 className="text-lg font-semibold">Add Memory</h2>
              <button onClick={() => setIsAddModalOpen(false)} className="text-muted-foreground hover:text-foreground">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-4 p-6">
              <div>
                <label className="mb-2 block text-sm font-medium">Title</label>
                <input
                  type="text"
                  value={newMemory.title}
                  onChange={(event) => setNewMemory((current) => ({ ...current, title: event.target.value }))}
                  placeholder="Memory title..."
                  className="w-full rounded-lg border border-border bg-background px-4 py-2 outline-none focus:border-primary"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium">Description</label>
                <textarea
                  value={newMemory.description}
                  onChange={(event) => setNewMemory((current) => ({ ...current, description: event.target.value }))}
                  placeholder="Add details..."
                  rows={3}
                  className="w-full resize-none rounded-lg border border-border bg-background px-4 py-2 outline-none focus:border-primary"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium">Type</label>
                <CeaserSelect
                  value={newMemory.type}
                  onValueChange={(value) => setNewMemory((current) => ({ ...current, type: value as BackendMemoryType }))}
                  options={[
                    { value: "decision", label: "Decision" },
                    { value: "goal", label: "Goal" },
                    { value: "file", label: "File" },
                    { value: "research", label: "Research" },
                    { value: "conversation", label: "Conversation" },
                    { value: "project", label: "Project" },
                  ]}
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium">Assign to Agent</label>
                <CeaserSelect
                  value={newMemory.agentId || "none"}
                  onValueChange={(value) => setNewMemory((current) => ({ ...current, agentId: value === "none" ? "" : value }))}
                  options={[
                    { value: "none", label: "No agent" },
                    ...agents.map((agent) => ({ value: agent.id, label: agent.name, description: agent.role })),
                  ]}
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 border-t border-border px-6 py-4">
              <button onClick={() => setIsAddModalOpen(false)} className="rounded-lg border border-border px-4 py-2 text-sm transition-colors hover:bg-secondary">
                Cancel
              </button>
              <button onClick={() => void handleAddMemory()} disabled={!newMemory.title.trim()} className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50">
                Add Memory
              </button>
            </div>
          </section>
        </div>
      )}

      {selectedMemory && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4 backdrop-blur-sm" onClick={() => setSelectedMemory(null)}>
          <section className="w-full max-w-2xl overflow-hidden rounded-2xl border border-border bg-card shadow-2xl" onClick={(event) => event.stopPropagation()}>
            <div className="flex items-start justify-between gap-4 border-b border-border px-6 py-5">
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">Memory Detail</p>
                <h2 className="mt-2 truncate text-xl font-semibold">{getMemoryTitle(selectedMemory)}</h2>
                <p className="mt-1 text-sm capitalize text-muted-foreground">{selectedMemory.memory_type} · {formatDate(selectedMemory.created_at)}</p>
              </div>
              <button onClick={() => setSelectedMemory(null)} className="rounded-xl p-2 text-muted-foreground transition hover:bg-secondary hover:text-foreground">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="max-h-[60vh] overflow-y-auto px-6 py-5">
              <pre className="whitespace-pre-wrap rounded-2xl border border-border bg-secondary/30 p-4 text-sm leading-7 text-foreground">{selectedMemory.content}</pre>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <DetailItem label="Memory ID" value={selectedMemory.id} />
                <DetailItem label="Agent" value={getAgentId(selectedMemory) || "Not assigned"} />
                <DetailItem label="Created" value={formatDate(selectedMemory.created_at)} />
                <DetailItem label="Type" value={selectedMemory.memory_type} />
              </div>
            </div>
            <div className="flex justify-end gap-2 border-t border-border px-6 py-4">
              <button onClick={() => void handleDeleteMemory(selectedMemory)} className="rounded-xl border border-red-400/20 px-4 py-2 text-sm font-semibold text-red-300 transition hover:bg-red-500/10">
                Delete
              </button>
              <button onClick={() => setSelectedMemory(null)} className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground">
                Done
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  )
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-secondary/30 p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 break-all text-sm font-medium">{value}</p>
    </div>
  )
}
