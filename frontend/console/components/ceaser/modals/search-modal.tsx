"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { Search, Bot, Brain, FileText, FolderKanban, MessageSquare, Workflow } from "lucide-react"
import { useApp } from "@/lib/app-context"
import type { AppPage } from "@/lib/ceaser"
import { agents } from "@/lib/data"
import { chatApi, type ConversationRecord } from "@/lib/api/chat"
import { documentsApi, type GeneratedDocument } from "@/lib/api/documents"
import { draftsApi, type DraftRecord } from "@/lib/api/drafts"
import { filesApi, type FileRecord } from "@/lib/api/files"
import { memoryApi, type MemoryRecord } from "@/lib/api/memory"
import { projectsApi, type ProjectRecord } from "@/lib/api/projects"
import { cn } from "@/lib/utils"

type SearchCategory = "all" | "agents" | "projects" | "memories" | "chats" | "files" | "workflows"
type SearchResult = {
  id: string
  type: SearchCategory
  title: string
  detail: string
  page: AppPage
  agentId?: string
}

const categories: { label: string; value: SearchCategory }[] = [
  { label: "All", value: "all" },
  { label: "Agents", value: "agents" },
  { label: "Projects", value: "projects" },
  { label: "Memories", value: "memories" },
  { label: "Chats", value: "chats" },
  { label: "Files", value: "files" },
  { label: "Workflows", value: "workflows" },
]

export function SearchModal() {
  const { isSearchOpen, setIsSearchOpen, setCurrentPage, setSelectedAgentId } = useApp()
  const [query, setQuery] = useState("")
  const [selectedCategory, setSelectedCategory] = useState<SearchCategory>("all")
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [projects, setProjects] = useState<ProjectRecord[]>([])
  const [memories, setMemories] = useState<MemoryRecord[]>([])
  const [conversations, setConversations] = useState<ConversationRecord[]>([])
  const [files, setFiles] = useState<FileRecord[]>([])
  const [drafts, setDrafts] = useState<DraftRecord[]>([])
  const [documents, setDocuments] = useState<GeneratedDocument[]>([])
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (isSearchOpen) {
      inputRef.current?.focus()
      void loadSearchData()
    } else {
      setQuery("")
      setSelectedIndex(0)
    }
  }, [isSearchOpen])

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault()
        setIsSearchOpen(!isSearchOpen)
      }
      if (event.key === "Escape") setIsSearchOpen(false)
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [isSearchOpen, setIsSearchOpen])

  async function loadSearchData() {
    const [projectResult, memoryResult, chatResult, fileResult, draftResult, documentResult] = await Promise.allSettled([
      projectsApi.list(),
      memoryApi.list(),
      chatApi.listConversations(false),
      filesApi.list(),
      draftsApi.list(),
      documentsApi.list(),
    ])
    if (projectResult.status === "fulfilled") setProjects(projectResult.value)
    if (memoryResult.status === "fulfilled") setMemories(memoryResult.value)
    if (chatResult.status === "fulfilled") setConversations(chatResult.value)
    if (fileResult.status === "fulfilled") setFiles(fileResult.value)
    if (draftResult.status === "fulfilled") setDrafts(draftResult.value)
    if (documentResult.status === "fulfilled") setDocuments(documentResult.value)
  }

  const allResults = useMemo(() => {
    const results: SearchResult[] = [
      ...agents.map((agent) => ({
        id: `agent-${agent.id}`,
        type: "agents" as const,
        title: agent.name,
        detail: agent.role,
        page: "agents" as AppPage,
        agentId: agent.id,
      })),
      ...projects.map((project) => ({
        id: `project-${project.id}`,
        type: "projects" as const,
        title: project.name,
        detail: project.description || project.status,
        page: "projects" as AppPage,
      })),
      ...memories.map((memory) => ({
        id: `memory-${memory.id}`,
        type: "memories" as const,
        title: getMemoryTitle(memory),
        detail: memory.memory_type,
        page: "memory" as AppPage,
      })),
      ...conversations.map((conversation) => ({
        id: `chat-${conversation.id}`,
        type: "chats" as const,
        title: conversation.title,
        detail: conversation.archived ? "Archived conversation" : "Conversation",
        page: "chat" as AppPage,
      })),
      ...files.map((file) => ({
        id: `file-${file.id}`,
        type: "files" as const,
        title: file.name,
        detail: file.file_type,
        page: "files" as AppPage,
      })),
      ...drafts.map((draft) => ({
        id: `draft-${draft.id}`,
        type: "workflows" as const,
        title: draft.title,
        detail: `${draft.draft_type.replaceAll("_", " ")} / ${draft.status}`,
        page: "drafts" as AppPage,
      })),
      ...documents.map((document) => ({
        id: `document-${document.id}`,
        type: "workflows" as const,
        title: document.file_name || document.source_prompt,
        detail: `Generated ${document.export_format.toUpperCase()}`,
        page: "drafts" as AppPage,
      })),
    ]
    const lowerQuery = query.trim().toLowerCase()
    return results
      .filter((result) => selectedCategory === "all" || result.type === selectedCategory)
      .filter((result) => !lowerQuery || `${result.title} ${result.detail}`.toLowerCase().includes(lowerQuery))
      .slice(0, 50)
  }, [conversations, documents, drafts, files, memories, projects, query, selectedCategory])

  useEffect(() => setSelectedIndex(0), [query, selectedCategory])

  useEffect(() => {
    if (!isSearchOpen) return
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "ArrowDown") {
        event.preventDefault()
        setSelectedIndex((index) => Math.min(index + 1, allResults.length - 1))
      } else if (event.key === "ArrowUp") {
        event.preventDefault()
        setSelectedIndex((index) => Math.max(index - 1, 0))
      } else if (event.key === "Enter" && allResults[selectedIndex]) {
        event.preventDefault()
        handleSelect(allResults[selectedIndex])
      }
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [allResults, isSearchOpen, selectedIndex])

  const handleSelect = (result: SearchResult) => {
    if (result.agentId) setSelectedAgentId(result.agentId)
    setCurrentPage(result.page)
    setIsSearchOpen(false)
  }

  const recentResults = allResults.slice(0, 6)

  return (
    <AnimatePresence>
      {isSearchOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-start justify-center bg-background/80 pt-[15vh] backdrop-blur-sm"
          onClick={() => setIsSearchOpen(false)}
        >
          <motion.div
            initial={{ scale: 0.96, opacity: 0, y: -18 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.96, opacity: 0, y: -18 }}
            className="w-full max-w-2xl overflow-hidden rounded-2xl border border-border bg-card shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-center gap-3 border-b border-border px-4 py-3">
              <Search className="h-5 w-5 text-muted-foreground" />
              <input
                ref={inputRef}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search live CEASER data..."
                className="flex-1 bg-transparent text-lg outline-none placeholder:text-muted-foreground"
              />
              <kbd className="rounded border border-border bg-background px-2 py-1 text-xs text-muted-foreground">ESC</kbd>
            </div>

            <div className="flex gap-1 overflow-x-auto border-b border-border px-4 py-2">
              {categories.map((category) => (
                <button
                  key={category.value}
                  onClick={() => setSelectedCategory(category.value)}
                  className={cn(
                    "whitespace-nowrap rounded-lg px-3 py-1.5 text-sm transition-colors",
                    selectedCategory === category.value ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-secondary",
                  )}
                >
                  {category.label}
                </button>
              ))}
            </div>

            <div className="max-h-[50vh] overflow-y-auto p-2">
              {!query && recentResults.length > 0 && (
                <p className="px-3 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Recent CEASER Data</p>
              )}
              {!query && !recentResults.length && (
                <p className="p-5 text-center text-sm text-muted-foreground">No searchable data yet. Create chats, projects, files, memories, or workflows first.</p>
              )}
              {query && !allResults.length && (
                <p className="p-5 text-center text-sm text-muted-foreground">No results found for &quot;{query}&quot;.</p>
              )}
              {(query ? allResults : recentResults).map((result, index) => (
                <button
                  key={result.id}
                  onClick={() => handleSelect(result)}
                  className={cn("flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left transition-colors", index === selectedIndex ? "bg-primary/15" : "hover:bg-secondary")}
                >
                  <ResultIcon type={result.type} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">{result.title}</span>
                    <span className="block truncate text-xs text-muted-foreground">{result.detail}</span>
                  </span>
                  <span className="text-xs capitalize text-muted-foreground">{result.type}</span>
                </button>
              ))}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

function ResultIcon({ type }: { type: SearchCategory }) {
  const iconClass = "h-4 w-4"
  if (type === "agents") return <Bot className={iconClass} />
  if (type === "projects") return <FolderKanban className={iconClass} />
  if (type === "memories") return <Brain className={iconClass} />
  if (type === "chats") return <MessageSquare className={iconClass} />
  if (type === "workflows") return <Workflow className={iconClass} />
  return <FileText className={iconClass} />
}

function getMemoryTitle(memory: MemoryRecord) {
  const metadata = (memory.metadata ?? memory.extra_metadata ?? {}) as { title?: string }
  return metadata.title || memory.content.split("\n")[0]?.replace(/^#+\s*/, "").slice(0, 90) || "Memory"
}
