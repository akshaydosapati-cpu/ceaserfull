"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import type { ChangeEvent, ReactNode } from "react"
import { chatApi, type AgentContribution, type CeaserChatResponse, type ChatMessage, type ConversationRecord, type MessageMetadata, type RankedMemory, type ResearchResult, type WorkflowResult } from "@/lib/api/chat"
import { documentsApi, type DocumentKind, type GeneratedDocument } from "@/lib/api/documents"
import { filesApi, type FileRecord } from "@/lib/api/files"
import { useApp } from "@/lib/app-context"
import { recordStartupMetric } from "@/lib/api/client"
import { trackEvent } from "@/lib/analytics"
import { getUserDisplayName, readUserProfile } from "@/lib/user-profile"
import { cn } from "@/lib/utils"
import { DropdownMenu, DropdownMenuContent, DropdownMenuRadioGroup, DropdownMenuRadioItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { CeaserLogo } from "../ceaser-logo"
import { RichResponseRenderer } from "../rich-response-renderer"
import { FOOTER_VOICE_EVENT } from "../command-bar"
import { navigationItems } from "@/lib/ceaser"
import type { VoiceRespondResponse } from "@/lib/api/voice"
import { Archive, BarChart3, Bookmark, CalendarPlus, Check, CheckCircle2, ChevronLeft, Code2, Copy, Download, Edit3, ExternalLink, FileText, Lightbulb, Loader2, Mail, MessageSquare, MoreHorizontal, Paperclip, PenLine, Pin, PinOff, Plus, Presentation, RefreshCw, RotateCcw, Search, Send, Share2, Sparkles, Square, Star, ThumbsDown, ThumbsUp, Trash2, X } from "lucide-react"
import type { LucideIcon } from "lucide-react"

interface Message {
  id: string
  role: "user" | "assistant" | "system"
  content: string
  timestamp: string
  metadata?: MessageMetadata
  agentIds?: string[]
  highlights?: string[]
  memoriesUsed?: RankedMemory[]
  contributions?: AgentContribution[]
  contributionSummary?: string
  research?: ResearchResult | null
  workflow?: WorkflowResult | null
  documentRequest?: DocumentRequest
  artifact?: GeneratedArtifact
  richResponse?: CeaserChatResponse["rich_response"]
  isTyping?: boolean
  isStreaming?: boolean
  statusLabel?: string
}

const ACTIVE_CONVERSATION_KEY = "ceaser_active_conversation_id"
const SAVED_RESPONSES_KEY = "ceaser_saved_responses"
const SAVED_RESPONSE_EVENT = "ceaser_saved_response"
const ENABLE_CHAT_SUGGESTIONS = false
type ConversationFilter = "all" | "pinned" | "today" | "week"

interface SavedResponse {
  id: string
  title: string
  content: string
  createdAt: string
}

type DocumentRequest = {
  kind: DocumentKind
  label: string
  agentId: string
}

const creationActions = [
  { title: "Create Document", subtitle: "Write anything", prompt: "Create a document about " },
  { title: "Create Pitch Deck", subtitle: "Slide by slide", prompt: "Create a pitch deck for " },
  { title: "Create Business Plan", subtitle: "Strategy & growth", prompt: "Create a business plan for " },
  { title: "Create Report", subtitle: "Research & insights", prompt: "Create a report about " },
  { title: "Create Study Notes", subtitle: "Notes, MCQs, more", prompt: "Create study notes for " },
  { title: "Create Excel Sheet", subtitle: "Tables & trackers", prompt: "Create an Excel tracker for " },
]

interface LaunchTask {
  title: string
  subtitle: string
  icon: LucideIcon
  color: string
  instruction: string
  output: string
  requiresFile?: boolean
}

const launchActions: LaunchTask[] = [
  { title: "Create Presentation", subtitle: "Generate a downloadable PPTX", icon: Presentation, color: "text-fuchsia-300 bg-fuchsia-500/12", instruction: "Create a presentation with speaker notes about", output: "PPTX presentation" },
  { title: "Write Document", subtitle: "Generate a downloadable DOCX", icon: FileText, color: "text-blue-300 bg-blue-500/12", instruction: "Create a structured document about", output: "DOCX document" },
  { title: "Analyze Data", subtitle: "Parse an attached dataset", icon: BarChart3, color: "text-emerald-300 bg-emerald-500/12", instruction: "Analyze the attached data and create a report with verified insights and charts for", output: "data analysis report", requiresFile: true },
  { title: "Code Something", subtitle: "Build files in a project workspace", icon: Code2, color: "text-orange-300 bg-orange-500/12", instruction: "Build a working software project for", output: "code project" },
  { title: "Brainstorm Ideas", subtitle: "Create a structured idea board", icon: Lightbulb, color: "text-amber-300 bg-amber-500/12", instruction: "Create a structured document containing a brainstorm and action board for", output: "idea board document" },
]

const launchAgents = [
  { name: "Researcher", subtitle: "Find & analyze information", icon: Search, color: "text-violet-300 bg-violet-500/12" },
  { name: "Writer", subtitle: "Write content & copy", icon: PenLine, color: "text-blue-300 bg-blue-500/12" },
  { name: "Analyst", subtitle: "Analyze data & trends", icon: BarChart3, color: "text-emerald-300 bg-emerald-500/12" },
  { name: "Developer", subtitle: "Code & build", icon: Code2, color: "text-orange-300 bg-orange-500/12" },
  { name: "Designer", subtitle: "Design & creative", icon: Lightbulb, color: "text-amber-300 bg-amber-500/12" },
]

const studentWorkflowShortcuts: LaunchTask[] = [
  { title: "Exam Prep", subtitle: "Notes and revision plan", icon: FileText, color: "text-cyan-300 bg-cyan-500/12", instruction: "Create study notes and a revision sheet for", output: "exam preparation document" },
  { title: "Research & Report", subtitle: "Current sources and report", icon: Search, color: "text-violet-300 bg-violet-500/12", instruction: "Research current sources and create a verified report about", output: "research report" },
  { title: "Presentation Prep", subtitle: "Slides and speaker notes", icon: Presentation, color: "text-fuchsia-300 bg-fuchsia-500/12", instruction: "Research and create a presentation with speaker notes about", output: "PPTX presentation" },
  { title: "Weekly Study Plan", subtitle: "Subjects and deadlines", icon: CalendarPlus, color: "text-blue-300 bg-blue-500/12", instruction: "Create a practical weekly study plan for", output: "study plan document" },
  { title: "Internship Prep", subtitle: "Resume and interview kit", icon: FileText, color: "text-emerald-300 bg-emerald-500/12", instruction: "Create a resume and interview kit for", output: "internship preparation document" },
  { title: "Project Demo Prep", subtitle: "Report, slides and outline", icon: Presentation, color: "text-orange-300 bg-orange-500/12", instruction: "Create a report and presentation with a speaking outline for", output: "project demo kit" },
  { title: "Lecture Notes to Revision Kit", subtitle: "Transform attached notes", icon: FileText, color: "text-cyan-300 bg-cyan-500/12", instruction: "Turn the attached lecture notes into study notes, key questions, and a study plan for", output: "revision kit document", requiresFile: true },
]

const hfTextModelOptions = [
  { id: "auto", label: "Auto" },
  { id: "nvidia-nemotron-3-ultra-550b-a55b", label: "Nemotron 3 Ultra 550B" },
  { id: "openai-primary", label: "OpenAI" },
  { id: "groq-primary", label: "Groq" },
  { id: "gemini-primary", label: "Gemini" },
]

const isImageGenerationRequest = (message: string) => {
  const normalized = message.toLowerCase().replace(/\s+/g, " ").trim()
  return /\b(create|generate|make|design|draw|illustrate)\b/.test(normalized)
    && /\b(image|picture|photo|illustration|artwork|poster|wallpaper|logo|thumbnail)\b/.test(normalized)
}

const agentNameToId = (name: string) => name.toLowerCase()

const stripSandboxArtifactLinks = (content: string) =>
  content
    .replace(/\[([^\]]+)\]\((?:sandbox:|https?:\/\/[^)]+\/(?:download|files\/[^)]+\/download)[^)]+)\)/gi, "$1")
    .trim()

const detectDocumentRequest = (message: string): DocumentRequest | null => {
  const normalized = message.toLowerCase()
  if (!/\b(create|write|draft|generate|make|prepare)\b/.test(normalized)) return null
  if (/\b(pitch deck|deck|slides|presentation|ppt|pptx)\b/.test(normalized)) return { kind: "pptx", label: "PowerPoint deck", agentId: "zeus" }
  if (/\b(excel|spreadsheet|sheet|tracker|xlsx|table)\b/.test(normalized)) return { kind: "xlsx", label: "Excel sheet", agentId: "bolt" }
  if (/\b(pdf)\b/.test(normalized)) return { kind: "pdf", label: "PDF document", agentId: "friday" }
  if (/\b(document|doc|docx|report|business plan|proposal|brief|article|essay|writeup|write-up|marketing plan|startup plan)\b/.test(normalized)) {
    const agentId = /\b(report)\b/.test(normalized)
      ? /\b(research|market|competitor|source|citation)\b/.test(normalized)
        ? "nova"
        : /\b(business|startup|strategy|revenue|growth|investor)\b/.test(normalized)
          ? "zeus"
          : "atlas"
      : /\b(business plan|startup plan|strategy|revenue|growth|investor)\b/.test(normalized)
        ? "zeus"
        : "friday"
    return { kind: "docx", label: "Word document", agentId }
  }
  return null
}

const formatTime = (value?: string) => {
  const date = value ? new Date(value) : new Date()
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
}

const safeArray = <T,>(value: T[] | null | undefined) => (Array.isArray(value) ? value : [])

const buildHighlights = (metadata: MessageMetadata) =>
  [
    metadata.scope ? `Scope: ${metadata.scope}` : null,
    metadata.selected_agents?.length ? `Selected Agents: ${metadata.selected_agents.join(", ")}` : null,
    metadata.workflow ? `Workflow: ${metadata.workflow.type}` : null,
    `Memories Used: ${safeArray(metadata.memories_used).length}`,
    `Sources: ${metadata.research?.sources?.length ?? 0}`,
  ].filter(Boolean) as string[]

const normalizeChatResponse = (response: CeaserChatResponse): CeaserChatResponse => ({
  ...response,
  selected_agents: safeArray(response.selected_agents),
  contributions: safeArray(response.contributions),
  memories_used: safeArray(response.memories_used),
  suggestions: safeArray(response.suggestions),
  research: response.research
    ? {
        ...response.research,
        key_findings: safeArray(response.research.key_findings),
        sources: safeArray(response.research.sources),
        citations: safeArray(response.research.citations),
        images: safeArray(response.research.images),
      }
    : null,
  workflow: response.workflow
    ? {
        ...response.workflow,
        steps: safeArray(response.workflow.steps),
      }
    : null,
})

const normalizeMessage = (message: ChatMessage): Message => ({
  id: message.id,
  role: message.role,
  content: message.content ?? "",
  timestamp: formatTime(message.created_at),
  metadata: metadataFromRecord(message),
  ...richMessageFields(message),
})

const responseToMessage = (messageId: string, response: CeaserChatResponse): Message => {
  const normalized = normalizeChatResponse(response)
  const metadata: MessageMetadata = {
    scope: normalized.scope,
    selected_agents: normalized.selected_agents,
    contributions: normalized.contributions,
    contribution_summary: normalized.contribution_summary,
    memories_used: normalized.memories_used,
    research: normalized.research,
    workflow: normalized.workflow,
    context_summary: normalized.context_summary,
    suggestions: normalized.suggestions,
    rich_response: normalized.rich_response,
  }

  return {
    id: messageId,
    role: "assistant",
    content: normalized.response ?? "",
    timestamp: formatTime(),
    metadata,
    agentIds: normalized.selected_agents.map(agentNameToId),
    memoriesUsed: normalized.memories_used,
    contributions: normalized.contributions,
    contributionSummary: normalized.contribution_summary,
    research: normalized.research,
    workflow: normalized.workflow,
    highlights: buildHighlights(metadata),
    richResponse: normalized.rich_response,
  }
}

const hasStructuredRichContent = (response: CeaserChatResponse["rich_response"]) => {
  if (!response?.blocks?.length) return false
  const structuredTypes = new Set(["code", "table", "chart", "image", "generated_image", "image_group", "file", "project"])
  return response.blocks.some((block) => structuredTypes.has(String(block.type ?? "").toLowerCase()))
}

type GeneratedArtifact = {
  id: string
  fileId: string
  title: string
  format: DocumentKind
  status: "ready" | "failed"
  filename: string
  preview: string
  metadata: Record<string, unknown>
}

function artifactFromDocument(document: GeneratedDocument, preview = ""): GeneratedArtifact {
  return {
    id: document.id,
    fileId: document.file_id,
    title: document.file_name || document.source_prompt,
    format: document.export_format,
    status: "ready",
    filename: document.file_name || `ceaser-artifact.${document.export_format}`,
    preview,
    metadata: {},
  }
}

function extractCodeArtifact(content: string): { language: string; code: string; filename: string } | null {
  const match = content.match(/```([\w+#.-]*)\s*\n([\s\S]*?)```/)
  if (!match || match[2].trim().length < 240) return null
  const language = match[1].toLowerCase() || "text"
  const filename = language === "html" ? "index.html" : language === "css" ? "styles.css" : language === "javascript" || language === "js" ? "script.js" : language === "python" ? "main.py" : "code.txt"
  return { language, code: match[2].replace(/^\n+|\n+$/g, ""), filename }
}

function CodeArtifactCard({ artifact }: { artifact: { language: string; code: string; filename: string } }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    await navigator.clipboard?.writeText(artifact.code)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1400)
  }
  const download = () => {
    const blob = new Blob([artifact.code], { type: artifact.language === "html" ? "text/html" : "text/plain" })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = artifact.filename
    anchor.click()
    URL.revokeObjectURL(url)
  }
  const preview = artifact.language === "html" ? () => {
    const url = URL.createObjectURL(new Blob([artifact.code], { type: "text/html" }))
    window.open(url, "_blank", "noopener,noreferrer")
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
  } : undefined
  return <section className="overflow-hidden rounded-xl border border-cyan-300/20 bg-[#050914] shadow-[0_18px_50px_rgba(0,0,0,.18)]">
    <header className="flex flex-wrap items-center gap-2 border-b border-white/10 px-4 py-3">
      <Code2 className="h-4 w-4 text-cyan-300" /><span className="min-w-0 flex-1 truncate text-sm font-semibold text-white">{artifact.filename}</span><span className="rounded-full bg-emerald-400/10 px-2 py-1 text-[10px] font-medium text-emerald-300">Ready</span>
      <button onClick={() => void copy()} className="inline-flex items-center gap-1.5 rounded-md border border-white/10 px-2.5 py-1.5 text-xs text-white/65 hover:bg-white/[0.06]">{copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}{copied ? "Copied" : "Copy"}</button>
      <button onClick={download} className="inline-flex items-center gap-1.5 rounded-md border border-white/10 px-2.5 py-1.5 text-xs text-white/65 hover:bg-white/[0.06]"><Download className="h-3.5 w-3.5" />Download</button>
      {preview && <button onClick={preview} className="inline-flex items-center gap-1.5 rounded-md border border-cyan-300/20 px-2.5 py-1.5 text-xs text-cyan-200 hover:bg-cyan-300/[0.08]"><ExternalLink className="h-3.5 w-3.5" />Preview</button>}
    </header>
    <pre className="max-h-[34rem] overflow-auto p-4 text-xs leading-6 text-slate-200"><code>{artifact.code}</code></pre>
  </section>
}

function GeneratedArtifactCard({ artifact }: { artifact: GeneratedArtifact }) {
  const [open, setOpen] = useState(false)
  const [downloadError, setDownloadError] = useState(false)
  const kindLabel = artifact.format.toUpperCase()
  const download = async () => {
    setDownloadError(false)
    try {
      await filesApi.download({ id: artifact.fileId, name: artifact.filename } as FileRecord)
    } catch {
      setDownloadError(true)
    }
  }
  if (artifact.status === "failed") return <section className="rounded-xl border border-rose-400/20 bg-rose-400/[0.06] p-4"><p className="text-sm font-semibold text-rose-100">Couldn&apos;t finish this {kindLabel} artifact.</p><p className="mt-1 text-xs text-rose-100/60">The response is still available, but file creation failed.</p></section>
  return <section className="min-w-0 overflow-hidden rounded-xl border border-cyan-300/20 bg-[#080d1b] shadow-[0_18px_50px_rgba(0,0,0,.18)]">
    <header className="flex flex-wrap items-center gap-3 border-b border-white/10 px-4 py-3"><FileText className="h-5 w-5 text-cyan-300" /><div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold text-white">{artifact.title}</p><p className="mt-0.5 text-xs text-white/45">{kindLabel} · {String(artifact.metadata.pages || artifact.metadata.sheets || artifact.metadata.sections || "Generated artifact")}</p></div><span className="rounded-full bg-emerald-400/10 px-2 py-1 text-[10px] font-medium text-emerald-300">Ready</span></header>
    <div className="flex flex-wrap gap-2 px-4 py-3"><button onClick={() => setOpen((value) => !value)} className="rounded-md border border-white/10 px-3 py-1.5 text-xs text-white/70 hover:bg-white/[0.06]">{open ? "Close preview" : "Open"}</button><button onClick={() => void download()} className="inline-flex items-center gap-1.5 rounded-md border border-cyan-300/20 px-3 py-1.5 text-xs text-cyan-200 hover:bg-cyan-300/[0.08]"><Download className="h-3.5 w-3.5" />Download {kindLabel}</button>{downloadError && <span className="self-center text-xs text-rose-300">Download unavailable</span>}</div>
    {open && <div className="max-h-72 overflow-auto border-t border-white/10 p-4 text-sm leading-6 text-white/70 whitespace-pre-wrap">{artifact.preview || "Preview unavailable. The generated file is still available to download."}</div>}
  </section>
}

const metadataFromRecord = (message: ChatMessage): MessageMetadata => {
  const recordWithAlias = message as ChatMessage & { extra_metadata?: MessageMetadata }
  const metadata = message.metadata ?? recordWithAlias.extra_metadata ?? {}
  if (Object.keys(metadata).length || message.role !== "assistant") return metadata

  const coordinated = message.content.match(/CEASER coordinated \d+ specialist agents?: ([^.]+)\./i)
  if (!coordinated) return {}

  const selectedAgents = coordinated[1]
    .split(",")
    .map((agent) => agent.replace(/\([^)]*\)/g, "").trim())
    .filter(Boolean)

  return {
    selected_agents: selectedAgents,
    contribution_summary: coordinated[0],
  }
}

const richMessageFields = (message: ChatMessage): Partial<Message> => {
  const metadata = metadataFromRecord(message)
  const selectedAgents = safeArray(metadata.selected_agents)
  const memoriesUsed = safeArray(metadata.memories_used)
  const highlights =
    message.role === "assistant" && (selectedAgents.length || metadata.scope || memoriesUsed.length)
      ? buildHighlights(metadata).filter((item) => !item.startsWith("Sources:") && !item.startsWith("Workflow:"))
      : undefined

  return {
    metadata,
    agentIds: selectedAgents.length ? selectedAgents.map(agentNameToId) : undefined,
    highlights,
    memoriesUsed,
    contributions: safeArray(metadata.contributions),
    contributionSummary: metadata.contribution_summary,
    research: metadata.research,
    workflow: metadata.workflow,
    richResponse: metadata.rich_response,
  }
}

function greetingForHour(hour: number) {
  if (hour < 12) return "Good morning"
  if (hour < 17) return "Good afternoon"
  return "Good evening"
}

const rotatingWelcomePrompts = [
  "How can I help you today?",
  "What would you like to create?",
  "What can we solve together?",
  "Where should we begin?",
]

export function ChatPage() {
  const { setCurrentPage, confirmDialog, promptDialog, pendingChatRequest, clearPendingChatRequest } = useApp()
  const [displayName, setDisplayName] = useState("there")
  // Keep the server and first client render deterministic; update to local
  // time after hydration in the existing interval effect below.
  const [timeGreeting, setTimeGreeting] = useState("Good afternoon")
  const [welcomePromptIndex, setWelcomePromptIndex] = useState(0)
  const [typedWelcomePrompt, setTypedWelcomePrompt] = useState("")
  const [isDeletingWelcomePrompt, setIsDeletingWelcomePrompt] = useState(false)
  const [conversations, setConversations] = useState<ConversationRecord[]>([])
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [searchQuery, setSearchQuery] = useState("")
  const [conversationFilter, setConversationFilter] = useState<ConversationFilter>("all")
  const [isLoading, setIsLoading] = useState(false)
  const [isUploadingFile, setIsUploadingFile] = useState(false)
  const [attachedFiles, setAttachedFiles] = useState<FileRecord[]>([])
  const [isBooting, setIsBooting] = useState(true)
  const [openConversationMenuId, setOpenConversationMenuId] = useState<string | null>(null)
  const [seededProjectFileIds, setSeededProjectFileIds] = useState<string[]>([])
  const [showArchivedChats, setShowArchivedChats] = useState(false)
  const [showSavedResponses, setShowSavedResponses] = useState(false)
  const [savedResponses, setSavedResponses] = useState<SavedResponse[]>([])
  const [chatSidebarCollapsed, setChatSidebarCollapsed] = useState(false)
  const [modelPreference, setModelPreference] = useState("auto")
  const [activeLaunchTask, setActiveLaunchTask] = useState<LaunchTask | null>(null)
  const [launchTaskTopic, setLaunchTaskTopic] = useState("")
  const [loadError, setLoadError] = useState<string | null>(null)
  const [isConversationLoading, setIsConversationLoading] = useState(false)
  const chatScrollRef = useRef<HTMLDivElement>(null)
  const shouldFollowStreamRef = useRef(true)
  const chatFileInputRef = useRef<HTMLInputElement>(null)
  const chatComposerRef = useRef<HTMLInputElement>(null)
  const preferredConversationRef = useRef<string | null>(null)
  const conversationCacheRef = useRef(new Map<string, Message[]>())
  const conversationRequestCacheRef = useRef(new Map<string, Promise<Message[]>>())
  const conversationsRequestRef = useRef<Promise<ConversationRecord[]> | null>(null)
  const hasBootedRef = useRef(false)
  const loadRequestRef = useRef(0)
  const streamAbortRef = useRef<AbortController | null>(null)
  const streamSessionRef = useRef(0)
  const autoSendSeedRef = useRef(false)
  const processedChatRequestRef = useRef<string | null>(null)
  const isProgrammaticScrollRef = useRef(false)
  const userInitial = useMemo(() => {
    const initial = displayName.trim().charAt(0).toUpperCase()
    return initial || "U"
  }, [displayName])

  useEffect(() => {
    const refreshGreeting = () => setTimeGreeting(greetingForHour(new Date().getHours()))
    refreshGreeting()
    const timer = window.setInterval(refreshGreeting, 60_000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    const phrase = rotatingWelcomePrompts[welcomePromptIndex]
    const isComplete = typedWelcomePrompt === phrase
    const isEmpty = typedWelcomePrompt.length === 0
    const delay = isComplete && !isDeletingWelcomePrompt ? 1800 : isEmpty && isDeletingWelcomePrompt ? 350 : isDeletingWelcomePrompt ? 32 : 58
    const timer = window.setTimeout(() => {
      if (isComplete && !isDeletingWelcomePrompt) {
        setIsDeletingWelcomePrompt(true)
        return
      }
      if (isEmpty && isDeletingWelcomePrompt) {
        setIsDeletingWelcomePrompt(false)
        setWelcomePromptIndex((current) => (current + 1) % rotatingWelcomePrompts.length)
        return
      }
      setTypedWelcomePrompt(phrase.slice(0, typedWelcomePrompt.length + (isDeletingWelcomePrompt ? -1 : 1)))
    }, delay)
    return () => window.clearTimeout(timer)
  }, [isDeletingWelcomePrompt, typedWelcomePrompt, welcomePromptIndex])

  const captureScrollPosition = useCallback(() => {
    const container = chatScrollRef.current
    if (!container || isProgrammaticScrollRef.current) return
    shouldFollowStreamRef.current = container.scrollHeight - container.scrollTop - container.clientHeight < 120
  }, [])

  const stopFollowingStream = useCallback(() => {
    shouldFollowStreamRef.current = false
  }, [])

  const latestAssistantIntel = useMemo(
    () => [...messages].reverse().find((message) => message.role === "assistant" && (message.workflow || message.research || message.memoriesUsed?.length || message.contributions?.length)),
    [messages],
  )

  const filteredConversations = useMemo(() => {
    const query = searchQuery.toLowerCase().trim()
    const now = new Date()
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
    const startOfWeek = new Date(startOfToday)
    startOfWeek.setDate(startOfWeek.getDate() - ((startOfWeek.getDay() + 6) % 7))
    return conversations.filter((conversation) => {
      const createdAt = new Date(conversation.created_at).getTime()
      const matchesFilter = conversationFilter === "all"
        || (conversationFilter === "pinned" && conversation.pinned)
        || (conversationFilter === "today" && createdAt >= startOfToday)
        || (conversationFilter === "week" && createdAt >= startOfWeek.getTime())
      const matchesQuery = !query || conversation.title.toLowerCase().includes(query)
      return matchesFilter && matchesQuery
    })
  }, [conversationFilter, conversations, searchQuery])

  const activeConversation = useMemo(
    () => conversations.find((item) => item.id === activeConversationId) ?? null,
    [activeConversationId, conversations],
  )

  const selectedModelLabel = useMemo(() => {
    const option = hfTextModelOptions.find((item) => item.id === modelPreference)
    return option?.label ?? "Auto"
  }, [modelPreference])

  const filteredSavedResponses = useMemo(() => {
    const query = searchQuery.toLowerCase().trim()
    if (!query) return savedResponses
    return savedResponses.filter((item) => `${item.title} ${item.content}`.toLowerCase().includes(query))
  }, [savedResponses, searchQuery])

  useEffect(() => {
    const syncProfile = () => {
      const profile = readUserProfile()
      const fullName = getUserDisplayName(profile, "there")
      setDisplayName(fullName.split(" ")[0] || "there")
    }
    syncProfile()
    window.addEventListener("storage", syncProfile)
    return () => window.removeEventListener("storage", syncProfile)
  }, [])

  const cancelActiveStream = useCallback(() => {
    streamSessionRef.current += 1
    streamAbortRef.current?.abort()
    streamAbortRef.current = null
    setMessages((current) => current.map((message) => message.isStreaming ? { ...message, isStreaming: false, isTyping: false, content: message.content || "Response stopped." } : message))
    setIsLoading(false)
  }, [])

  const loadMessages = useCallback(async (conversationId: string) => {
    const cached = conversationCacheRef.current.get(conversationId)
    if (cached) {
      setMessages(cached)
      setLoadError(null)
      setIsConversationLoading(false)
    } else {
      setMessages([])
      setIsConversationLoading(true)
    }

    const requestId = ++loadRequestRef.current
    try {
      let request = conversationRequestCacheRef.current.get(conversationId)
      if (!request) {
        request = chatApi.listMessages(conversationId).then((records) => records.map(normalizeMessage))
        conversationRequestCacheRef.current.set(conversationId, request)
      }
      const normalized = await request
      if (requestId !== loadRequestRef.current) return
      const generated = await documentsApi.list().catch(() => [] as GeneratedDocument[])
      const hydrated = normalized.map((message, index) => {
        if (message.role !== "assistant") return message
        const previousUser = [...normalized.slice(0, index)].reverse().find((item) => item.role === "user")
        const match = generated.find((document) => previousUser && document.source_prompt.trim().toLowerCase() === previousUser.content.trim().toLowerCase())
        return match ? { ...message, artifact: artifactFromDocument(match, message.content) } : message
      })
      conversationCacheRef.current.set(conversationId, hydrated)
      setMessages(hydrated)
      setLoadError(null)
    } catch (error) {
      if (requestId !== loadRequestRef.current) return
      setMessages([])
      setLoadError(error instanceof Error ? error.message : "Conversation history is still loading.")
    } finally {
      conversationRequestCacheRef.current.delete(conversationId)
      if (requestId === loadRequestRef.current) {
        setIsConversationLoading(false)
      }
    }
  }, [])

  const loadConversations = useCallback(async () => {
    if (conversationsRequestRef.current) return conversationsRequestRef.current
    const request = (async () => {
      try {
        const records = await chatApi.listConversations(showArchivedChats)
        setConversations(records)
        setLoadError(null)
        return records
      } catch (error) {
        setConversations([])
        setLoadError(error instanceof Error ? error.message : "Conversation history is still loading.")
        return [] as ConversationRecord[]
      } finally {
        conversationsRequestRef.current = null
      }
    })()
    conversationsRequestRef.current = request
    return request
  }, [showArchivedChats])

  const refreshConversationList = useCallback(async () => {
    try {
      const records = await chatApi.listConversations(showArchivedChats)
      setConversations(records)
      setLoadError(null)
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "Conversation list is still loading.")
    }
  }, [showArchivedChats])

  useEffect(() => {
    const boot = async () => {
      setIsBooting(true)
      const seed = window.localStorage.getItem("ceaser_chat_seed")
      try {
        const projectFileIds = JSON.parse(window.localStorage.getItem("ceaser_project_file_ids") || "[]")
        setSeededProjectFileIds(Array.isArray(projectFileIds) ? projectFileIds.filter((id): id is string => typeof id === "string") : [])
      } catch {
        setSeededProjectFileIds([])
      }
      window.localStorage.removeItem("ceaser_project_file_ids")
      // A workflow request must always open a new conversation. Do not let the
      // asynchronous conversation-list load restore an older chat over it.
      const startsNewChat = Boolean(pendingChatRequest || seed)
      preferredConversationRef.current = startsNewChat ? null : window.localStorage.getItem(ACTIVE_CONVERSATION_KEY)
      if (seed) {
        setInput(seed)
        window.localStorage.removeItem("ceaser_chat_seed")
        autoSendSeedRef.current = window.localStorage.getItem("ceaser_chat_autosend") === "true"
        window.localStorage.removeItem("ceaser_chat_autosend")
      }
      setActiveConversationId(null)
      setMessages([])
      setIsConversationLoading(false)
      setIsBooting(false)
      recordStartupMetric("composer_rendered")
      recordStartupMetric("input_interactive")
      hasBootedRef.current = true

      const records = await loadConversations()
      recordStartupMetric("conversation_list_ready", { conversations: records.length })
      recordStartupMetric("core_data_ready")
      const preferredId = preferredConversationRef.current
      if (preferredId && records.some((conversation) => conversation.id === preferredId)) {
        setActiveConversationId(preferredId)
        void loadMessages(preferredId)
      } else {
        window.localStorage.removeItem(ACTIVE_CONVERSATION_KEY)
        setIsConversationLoading(false)
      }
    }
    void boot()
  }, [loadConversations])

  useEffect(() => {
    const container = chatScrollRef.current
    if (!container || !shouldFollowStreamRef.current) return
    isProgrammaticScrollRef.current = true
    container.scrollTop = container.scrollHeight
    requestAnimationFrame(() => {
      isProgrammaticScrollRef.current = false
    })
  }, [messages])

  useEffect(() => {
    try {
      const records = JSON.parse(window.localStorage.getItem(SAVED_RESPONSES_KEY) || "[]") as SavedResponse[]
      setSavedResponses(Array.isArray(records) ? records : [])
    } catch {
      setSavedResponses([])
    }

    const onSaved = () => {
      try {
        const records = JSON.parse(window.localStorage.getItem(SAVED_RESPONSES_KEY) || "[]") as SavedResponse[]
        setSavedResponses(Array.isArray(records) ? records : [])
      } catch {
        setSavedResponses([])
      }
    }

    window.addEventListener(SAVED_RESPONSE_EVENT, onSaved)
    return () => window.removeEventListener(SAVED_RESPONSE_EVENT, onSaved)
  }, [])

  useEffect(() => {
    if (!showSavedResponses && hasBootedRef.current) void loadConversations()
  }, [showArchivedChats, showSavedResponses, loadConversations])

  const isActiveChatLoading = isConversationLoading && Boolean(activeConversationId)

  const queueFollowUp = useCallback((prompt: string) => {
    setInput(prompt)
  }, [])

  const handleNewChat = async () => {
    cancelActiveStream()
    if (showArchivedChats) setShowArchivedChats(false)
    if (showSavedResponses) setShowSavedResponses(false)
    setActiveConversationId(null)
    window.localStorage.removeItem(ACTIVE_CONVERSATION_KEY)
    setMessages([])
    setLoadError(null)
    setIsConversationLoading(false)
    setAttachedFiles([])
    setSeededProjectFileIds([])
  }

  const handleSelectConversation = async (conversationId: string) => {
    setSeededProjectFileIds([])
    if (activeConversationId === conversationId) return
    cancelActiveStream()
    setShowSavedResponses(false)
    setOpenConversationMenuId(null)
    setActiveConversationId(conversationId)
    window.localStorage.setItem(ACTIVE_CONVERSATION_KEY, conversationId)
    setLoadError(null)
    void loadMessages(conversationId)
  }

  const handleSelectSavedResponse = (response: SavedResponse) => {
    cancelActiveStream()
    setActiveConversationId(null)
    window.localStorage.removeItem(ACTIVE_CONVERSATION_KEY)
    setMessages([
      {
        id: response.id,
        role: "assistant",
        content: response.content,
        timestamp: formatTime(response.createdAt),
      },
    ])
    setIsConversationLoading(false)
  }

  const handleRenameConversation = async (conversation: ConversationRecord) => {
    const title = (await promptDialog({
      title: "Rename chat",
      description: "Give this conversation a clear name.",
      defaultValue: conversation.title,
      confirmLabel: "Rename",
    }))?.trim()
    if (!title || title === conversation.title) return
    const updated = await chatApi.updateConversation(conversation.id, { title })
    setConversations((current) => current.map((item) => (item.id === updated.id ? updated : item)))
    setOpenConversationMenuId(null)
  }

  const handleTogglePinConversation = async (conversation: ConversationRecord) => {
    try {
      const updated = await chatApi.updateConversation(conversation.id, { pinned: !conversation.pinned })
      setConversations((current) => current.map((item) => (item.id === updated.id ? updated : item)).sort((a, b) => Number(b.pinned) - Number(a.pinned)))
      setLoadError(null)
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "Could not update the pinned chat.")
    } finally {
      setOpenConversationMenuId(null)
    }
  }

  const handleArchiveConversation = async (conversation: ConversationRecord) => {
    await chatApi.updateConversation(conversation.id, { archived: true })
    const remaining = conversations.filter((item) => item.id !== conversation.id)
    setConversations(remaining)
    setOpenConversationMenuId(null)
    conversationCacheRef.current.delete(conversation.id)
    if (activeConversationId === conversation.id) {
      cancelActiveStream()
      const next = remaining[0]
      setActiveConversationId(next?.id ?? null)
      if (next) {
        window.localStorage.setItem(ACTIVE_CONVERSATION_KEY, next.id)
        void loadMessages(next.id)
      } else {
        window.localStorage.removeItem(ACTIVE_CONVERSATION_KEY)
        setMessages([])
      }
    }
  }

  const handleUnarchiveConversation = async (conversation: ConversationRecord) => {
    await chatApi.updateConversation(conversation.id, { archived: false })
    const remaining = conversations.filter((item) => item.id !== conversation.id)
    setConversations(remaining)
    setOpenConversationMenuId(null)
    conversationCacheRef.current.delete(conversation.id)
    if (activeConversationId === conversation.id) {
      cancelActiveStream()
      const next = remaining[0]
      setActiveConversationId(next?.id ?? null)
      if (next) {
        window.localStorage.setItem(ACTIVE_CONVERSATION_KEY, next.id)
        void loadMessages(next.id)
      } else {
        window.localStorage.removeItem(ACTIVE_CONVERSATION_KEY)
        setMessages([])
      }
    }
  }

  const handleDeleteConversation = async (conversation: ConversationRecord) => {
    const confirmed = await confirmDialog({
      title: `Delete "${conversation.title}"?`,
      description: "This conversation and its messages will be removed. This cannot be undone.",
      confirmLabel: "Delete",
      tone: "danger",
    })
    if (!confirmed) return
    await chatApi.deleteConversation(conversation.id)
    const remaining = conversations.filter((item) => item.id !== conversation.id)
    setConversations(remaining)
    setOpenConversationMenuId(null)
    conversationCacheRef.current.delete(conversation.id)
    if (activeConversationId === conversation.id) {
      cancelActiveStream()
      const next = remaining[0]
      setActiveConversationId(next?.id ?? null)
      if (next) {
        window.localStorage.setItem(ACTIVE_CONVERSATION_KEY, next.id)
        void loadMessages(next.id)
      } else {
        window.localStorage.removeItem(ACTIVE_CONVERSATION_KEY)
        setMessages([])
      }
    }
  }

  const handleShareConversation = async (conversation: ConversationRecord) => {
    const url = `${window.location.origin}${window.location.pathname}?conversation=${conversation.id}`
    try {
      if (window.navigator.share) {
        await window.navigator.share({ title: conversation.title, url })
      } else if (window.navigator.clipboard) {
        await window.navigator.clipboard.writeText(url)
      }
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError")) {
        console.error("Failed to share conversation", error)
      }
    } finally {
      setOpenConversationMenuId(null)
    }
  }

  const ensureConversation = async () => {
    if (activeConversationId && !showArchivedChats) return activeConversationId
    if (showArchivedChats) setShowArchivedChats(false)
    const conversation = await chatApi.createConversation()
    setConversations((current) => [conversation, ...current])
    setActiveConversationId(conversation.id)
    window.localStorage.setItem(ACTIVE_CONVERSATION_KEY, conversation.id)
    return conversation.id
  }

  const handleSend = async (messageOverride?: string, forceNewStream = false) => {
    const content = (messageOverride ?? input).trim()
    if (!content || (isLoading && !forceNewStream)) return
    trackEvent("chat_message_sent")
    cancelActiveStream()
    const documentRequest = detectDocumentRequest(content)
    // A newly sent message should be visible, but once the user scrolls up we
    // keep their reading position stable while streamed chunks arrive.
    shouldFollowStreamRef.current = true
    setInput("")
    setIsLoading(true)

    const userMessage: Message = {
      id: `local-${Date.now()}`,
      role: "user",
      content,
      timestamp: formatTime(),
    }
    const typingMessage: Message = {
      id: `typing-${Date.now()}`,
      role: "assistant",
      content: "",
      timestamp: formatTime(),
      isTyping: true,
      isStreaming: true,
    }
    setMessages((current) => [...current, userMessage, typingMessage])
    const sendClickedAt = performance.now()
    console.info("[CEASER LATENCY] send_clicked")
    console.info("[CEASER LATENCY] user_message_rendered", Math.round(performance.now() - sendClickedAt))

    let conversationId: string | null = activeConversationId && !showArchivedChats ? activeConversationId : null
    try {
      console.info("[CEASER LATENCY] stream_request_start")
      if (conversationId) {
        const seededMessages = [...messages, userMessage, typingMessage]
        conversationCacheRef.current.set(conversationId, seededMessages)
      }
      const fileIds = Array.from(new Set([...attachedFiles.map((file) => file.id), ...seededProjectFileIds]))
      const controller = new AbortController()
      streamAbortRef.current = controller
      const streamSessionId = ++streamSessionRef.current
      const clientStreamStartedAt = performance.now()
      let firstTokenAt: number | null = null
      let response: CeaserChatResponse | null = null
      let streamedContent = ""
      let receivedStreamContent = false
      const imageGenerationRequested = isImageGenerationRequest(content)
      try {
        let streamError: string | null = null
        if (imageGenerationRequested) {
          response = await chatApi.sendCeaserMessage(content, conversationId ?? undefined, fileIds, {
            modelPreference: modelPreference === "auto" ? undefined : modelPreference,
            responseMode: "image",
            forceLiveWebSearch: false,
          })
        } else {
          await chatApi.sendCeaserMessageStream(content, conversationId ?? undefined, fileIds, {
            onToken: (text) => {
              if (streamSessionRef.current !== streamSessionId) return
              if (firstTokenAt === null) {
                firstTokenAt = performance.now()
                console.info("[CEASER LATENCY] frontend_first_token_ms", Math.round(firstTokenAt - clientStreamStartedAt))
                console.info("[CEASER LATENCY] first_content_token")
              }
              streamedContent += text
              receivedStreamContent = true
              setMessages((current) =>
                current.map((message) =>
                  message.id === typingMessage.id
                    ? { ...message, content: streamedContent, timestamp: formatTime(), isTyping: false, isStreaming: true }
                    : message,
                ),
              )
            },
            onComplete: (streamedResponse) => {
              if (streamSessionRef.current !== streamSessionId) return
              console.info(
                `[CEASER LLM] provider=${String(streamedResponse.context_summary?.provider ?? "not reported")} model=${String(streamedResponse.context_summary?.model ?? "not reported")} fallback_used=${String(streamedResponse.context_summary?.fallback_used ?? false)} agents=${streamedResponse.selected_agents.join(",") || "none"}`,
              )
              response = streamedResponse
              if (streamedResponse.conversation_id) {
                conversationId = streamedResponse.conversation_id
                setActiveConversationId(streamedResponse.conversation_id)
                window.localStorage.setItem(ACTIVE_CONVERSATION_KEY, streamedResponse.conversation_id)
              }
            },
            onError: (message) => {
              if (streamSessionRef.current !== streamSessionId) return
              streamError = message
            },
          }, { signal: controller.signal, modelPreference: modelPreference === "auto" ? undefined : modelPreference, forceLiveWebSearch: false })
          if (streamError) throw new Error(streamError)
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return
        if (imageGenerationRequested) throw error
        if (receivedStreamContent) {
          response = {
            scope: "personal_ai_os",
            conversation_id: conversationId,
            selected_agents: [],
            contributions: [],
            contribution_summary: "Response streamed.",
            memories_used: [],
            research: null,
            workflow: null,
            context_summary: {},
            suggestions: [],
            response: streamedContent,
          }
        } else {
          throw error
        }
      }

      if (!response) {
        response = {
          scope: "personal_ai_os",
          conversation_id: conversationId,
          selected_agents: [],
          contributions: [],
          contribution_summary: "Response streamed.",
          memories_used: [],
          research: null,
          workflow: null,
          context_summary: {},
          suggestions: [],
          response: streamedContent || "CEASER could not complete that response. Please try again.",
        }
      }

      const assistantMessage: Message = { ...responseToMessage(typingMessage.id, response), documentRequest: documentRequest ?? undefined }
      trackEvent("chat_response_completed", { request_mode: String(response.context_summary?.request_mode ?? "chat"), provider: String(response.context_summary?.provider ?? "unknown"), model: String(response.context_summary?.model ?? "unknown"), success: true })
      setMessages((current) => {
        const next = current.map((message) => (message.id === typingMessage.id ? { ...assistantMessage, isTyping: false, isStreaming: false } : message))
        if (conversationId) conversationCacheRef.current.set(conversationId, next)
        return next
      })
      if (documentRequest && conversationId) {
        trackEvent("artifact_requested", { artifact_type: documentRequest.kind })
        void documentsApi.create({
          kind: documentRequest.kind,
          prompt: content,
          agent_id: documentRequest.agentId,
          source_content: assistantMessage.content.slice(0, 50000) || null,
        }).then((generated) => {
          const artifact: GeneratedArtifact = {
            id: generated.document.id,
            fileId: generated.document.file_id,
            title: generated.document.file_name || documentRequest.label,
            format: generated.document.export_format,
            status: "ready",
            filename: generated.document.file_name || `${documentRequest.label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.${generated.document.export_format}`,
            preview: generated.preview || assistantMessage.content || "",
            metadata: (generated.file?.extraction_metadata as Record<string, unknown>) || {},
          }
          trackEvent("artifact_completed", { artifact_type: documentRequest.kind })
          setMessages((current) => current.map((message) => message.id === typingMessage.id ? { ...message, artifact } : message))
        }).catch(() => {
          setMessages((current) => current.map((message) => message.id === typingMessage.id ? { ...message, artifact: { id: `failed-${typingMessage.id}`, fileId: "", title: documentRequest.label, format: documentRequest.kind, status: "failed", filename: "", preview: "", metadata: {} } } : message))
        })
      }
      if (conversationId) {
        const convoId = conversationId
        void (async () => {
          for (let attempt = 0; attempt < 10; attempt += 1) {
            try {
              const persistedMessages = await chatApi.listMessages(convoId, 12)
              const persistedAssistant = [...persistedMessages].reverse().find((message) => message.role === "assistant")
              if (!persistedAssistant) {
                await new Promise((resolve) => window.setTimeout(resolve, 250))
                continue
              }
              const hydratedAssistant = {
                ...normalizeMessage(persistedAssistant),
                id: typingMessage.id,
                documentRequest: documentRequest ?? undefined,
              }
              setMessages((current) => {
                const next = current.map((message) =>
                  message.id === typingMessage.id
                    ? { ...hydratedAssistant, isTyping: false, isStreaming: false }
                    : message,
                )
                conversationCacheRef.current.set(convoId, next)
                return next
              })
              break
            } catch {
              await new Promise((resolve) => window.setTimeout(resolve, 250))
            }
          }
        })()
      }
      requestAnimationFrame(() => {
        console.info("[CEASER LATENCY] frontend_render_ms", Math.round(performance.now() - clientStreamStartedAt), "first_token_ms", firstTokenAt === null ? null : Math.round(firstTokenAt - clientStreamStartedAt))
      })
      setAttachedFiles([])
      void refreshConversationList()
      window.dispatchEvent(new Event("ceaser:activity-updated"))
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return
      const assistantMessage: Message = {
        id: typingMessage.id,
        role: "assistant",
        content: error instanceof Error ? error.message : "CEASER chat failed to connect.",
        timestamp: formatTime(),
      }
      setMessages((current) => {
        const next = current.map((message) => (message.id === typingMessage.id ? assistantMessage : message))
        if (conversationId) conversationCacheRef.current.set(conversationId, next)
        return next
      })
    } finally {
      streamAbortRef.current = null
      setIsLoading(false)
    }
  }

  const launchStructuredTask = () => {
    if (!activeLaunchTask || !launchTaskTopic.trim()) return
    if (activeLaunchTask.requiresFile && attachedFiles.length === 0) {
      setLoadError("Attach the exact dataset you want CEASER to analyze before starting this task.")
      chatFileInputRef.current?.click()
      return
    }
    const request = `${activeLaunchTask.instruction} ${launchTaskTopic.trim()}. Required output: a real, validated ${activeLaunchTask.output}; do not return a text-only substitute.`
    setActiveLaunchTask(null)
    setLaunchTaskTopic("")
    setLoadError(null)
    void handleSend(request)
  }

  useEffect(() => {
    if (!autoSendSeedRef.current || !input.trim() || isLoading || isBooting) return
    autoSendSeedRef.current = false
    void handleSend()
  }, [input, isBooting, isLoading])

  useEffect(() => {
    if (!pendingChatRequest || isBooting || isLoading || processedChatRequestRef.current === pendingChatRequest.id) return
    processedChatRequestRef.current = pendingChatRequest.id
    clearPendingChatRequest()
    void (async () => {
      await handleNewChat()
      await handleSend(pendingChatRequest.prompt, true)
    })()
  }, [pendingChatRequest, isBooting, isLoading])

  const handleEditSentMessage = async (message: Message) => {
    const updated = (await promptDialog({
      title: "Edit message",
      description: "Correct your message. CEASER will stop the current response and answer the edited version.",
      defaultValue: message.content,
      confirmLabel: "Use edited message",
    }))?.trim()
    if (!updated) return
    cancelActiveStream()
    void handleSend(updated, true)
  }

  const handleVoiceResponse = async (response: VoiceRespondResponse) => {
    const normalizedChat = normalizeChatResponse(response.chat as CeaserChatResponse)
    if (response.chat.conversation_id) {
      setActiveConversationId(response.chat.conversation_id)
      window.localStorage.setItem(ACTIVE_CONVERSATION_KEY, response.chat.conversation_id)
    }
    const userMessage: Message = {
      id: `voice-user-${Date.now()}`,
      role: "user",
      content: response.transcript,
      timestamp: formatTime(),
    }
    const assistantMessage: Message = {
      id: `voice-assistant-${Date.now()}`,
      role: "assistant",
      content: normalizedChat.response,
      timestamp: formatTime(),
      metadata: {
        scope: normalizedChat.scope,
        selected_agents: normalizedChat.selected_agents,
        contributions: normalizedChat.contributions,
        contribution_summary: normalizedChat.contribution_summary,
        memories_used: normalizedChat.memories_used,
        research: normalizedChat.research,
        workflow: normalizedChat.workflow,
        context_summary: normalizedChat.context_summary,
        suggestions: normalizedChat.suggestions,
      },
      agentIds: normalizedChat.selected_agents.map(agentNameToId),
      memoriesUsed: normalizedChat.memories_used,
      contributions: normalizedChat.contributions,
      contributionSummary: normalizedChat.contribution_summary,
      research: normalizedChat.research,
      workflow: normalizedChat.workflow,
      highlights: buildHighlights({
        scope: normalizedChat.scope,
        selected_agents: normalizedChat.selected_agents,
        memories_used: normalizedChat.memories_used,
        research: normalizedChat.research,
        workflow: normalizedChat.workflow,
      }),
    }
    setMessages((current) => {
      const next = [...current, userMessage, assistantMessage]
      if (response.chat.conversation_id) {
        conversationCacheRef.current.set(response.chat.conversation_id, next)
      }
      return next
    })
    await refreshConversationList()
    window.dispatchEvent(new Event("ceaser:activity-updated"))
  }

  useEffect(() => {
    const handleFooterVoiceResponse = (event: Event) => {
      const response = (event as CustomEvent<VoiceRespondResponse>).detail
      if (response) void handleVoiceResponse(response)
    }
    window.addEventListener(FOOTER_VOICE_EVENT, handleFooterVoiceResponse)
    return () => window.removeEventListener(FOOTER_VOICE_EVENT, handleFooterVoiceResponse)
  })

  const handleChatFileUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    setIsUploadingFile(true)
    try {
      const uploaded = await filesApi.upload(file)
      setAttachedFiles((current) => [...current, uploaded])
      setInput((current) => current || "Summarize this document")
    } catch {
      setMessages((current) => [
        ...current,
        {
          id: `file-upload-error-${Date.now()}`,
          role: "assistant",
          content: "File upload failed. Check the backend is running, then try again.",
          timestamp: formatTime(),
        },
      ])
    } finally {
      setIsUploadingFile(false)
      event.target.value = ""
    }
  }

  useEffect(() => {
    const openConversation = (event: Event) => {
      const id = (event as CustomEvent<{ id?: string }>).detail?.id
      if (id) void handleSelectConversation(id)
    }
    const startNewConversation = () => void handleNewChat()
    window.addEventListener("ceaser:open-conversation", openConversation)
    window.addEventListener("ceaser:new-chat", startNewConversation)
    return () => {
      window.removeEventListener("ceaser:open-conversation", openConversation)
      window.removeEventListener("ceaser:new-chat", startNewConversation)
    }
  })

  const ActiveLaunchIcon = activeLaunchTask?.icon ?? Sparkles

  return (
    <div className={cn("ceaser-chat relative flex h-full overflow-hidden text-foreground", "bg-[#040714]")}>
      <div className={cn("pointer-events-none absolute inset-0 [background-image:linear-gradient(rgba(148,163,184,.18)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,.18)_1px,transparent_1px)] [background-size:36px_36px]", "opacity-[0.08]")} />
      <div className={cn("pointer-events-none absolute inset-0", "bg-[radial-gradient(circle_at_18%_0%,rgba(124,58,237,0.12),transparent_34%),radial-gradient(circle_at_82%_100%,rgba(0,212,255,0.08),transparent_32%)]")} />

      <aside
        aria-hidden="true"
        className={cn(
          "hidden relative z-20 h-full shrink-0 flex-col border-r border-border bg-card/72 backdrop-blur-xl transition-all duration-300",
          chatSidebarCollapsed ? "w-[68px]" : "w-[272px]",
        )}
      >
        <div className="flex h-16 items-center justify-between border-b border-white/[0.07] px-4">
          {!chatSidebarCollapsed && <div className="flex items-center gap-2.5"><CeaserLogo showText={false} className="h-8 w-8" /><p className="text-[15px] font-semibold tracking-[0.08em] text-white">CEASER</p></div>}
          <button
            onClick={() => setChatSidebarCollapsed((value) => !value)}
            className="flex h-8 w-8 items-center justify-center rounded-full border border-border bg-secondary/45 text-muted-foreground transition hover:bg-secondary hover:text-foreground"
            aria-label={chatSidebarCollapsed ? "Expand chat sidebar" : "Collapse chat sidebar"}
          >
            <ChevronLeft className={cn("h-4 w-4 transition-transform", chatSidebarCollapsed && "rotate-180")} />
          </button>
        </div>

        <div className="mt-3 px-3">
          <button
            onClick={() => void handleNewChat()}
            className={cn(
              "ceaser-primary-action flex h-10 w-full items-center justify-center gap-2 rounded-lg text-xs font-semibold text-white transition",
              chatSidebarCollapsed && "rounded-full px-0",
            )}
          >
            <Plus className="h-4 w-4" />
            {!chatSidebarCollapsed && <span>New Chat</span>}
          </button>
        </div>

        <nav className={cn("mt-3 border-y border-white/[0.06] py-2", chatSidebarCollapsed ? "px-2" : "px-3")} aria-label="CEASER navigation">
          <div className="space-y-0.5">
            {navigationItems.map((item) => {
              const Icon = item.icon
              const active = item.id === "chat"
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setCurrentPage(item.id)}
                  title={item.label}
                  className={cn(
                    "flex h-8 w-full items-center rounded-md text-xs transition",
                    chatSidebarCollapsed ? "justify-center px-0" : "gap-2.5 px-2.5",
                    active ? "bg-white/[0.07] text-white" : "text-white/58 hover:bg-white/[0.045] hover:text-white",
                  )}
                >
                  <Icon className={cn("h-3.5 w-3.5 shrink-0", active && "text-cyan-300")} />
                  {!chatSidebarCollapsed && <span className="truncate">{item.label}</span>}
                </button>
              )
            })}
          </div>
        </nav>

        {!chatSidebarCollapsed && (
          <>
            <div className="mt-3 px-3">
              <div className="flex h-9 items-center gap-2 rounded-lg border border-border bg-secondary/35 px-3">
                <Search className="h-3.5 w-3.5 text-muted-foreground" />
                <input
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="Search chats..."
                  className="w-full bg-transparent text-xs text-foreground outline-none placeholder:text-muted-foreground"
                />
              </div>
            </div>

            <div className="mt-2 grid grid-cols-4 gap-0.5 px-3">
              {([["all", "All"], ["pinned", "Pinned"], ["today", "Today"], ["week", "This Week"]] as const).map(([value, label]) => (
                <button
                  key={value}
                  onClick={() => {
                    setShowSavedResponses(false)
                    setShowArchivedChats(false)
                    setConversationFilter(value)
                  }}
                  className={cn("rounded-md px-1 py-1.5 text-[10px] font-medium transition", conversationFilter === value ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-secondary/70 hover:text-foreground")}
                >
                  {label}
                </button>
              ))}
            </div>
          </>
        )}

        <div className={cn("mt-3 flex-1 overflow-y-auto", chatSidebarCollapsed ? "px-2" : "px-3")}>
          {chatSidebarCollapsed ? (
            <div className="space-y-2">
              {(showSavedResponses ? filteredSavedResponses : filteredConversations).slice(0, 8).map((item) => (
                <button
                  key={item.id}
                  onClick={() => showSavedResponses ? handleSelectSavedResponse(item as SavedResponse) : void handleSelectConversation((item as ConversationRecord).id)}
                  className={cn(
                    "flex h-11 w-11 items-center justify-center rounded-full border border-border text-xs font-semibold transition",
                    activeConversationId === item.id ? "bg-primary text-primary-foreground" : "bg-secondary/45 text-muted-foreground hover:bg-secondary hover:text-foreground",
                  )}
                  title={showSavedResponses ? (item as SavedResponse).title : (item as ConversationRecord).title}
                >
                  {(showSavedResponses ? (item as SavedResponse).title : (item as ConversationRecord).title).slice(0, 1).toUpperCase()}
                </button>
              ))}
            </div>
          ) : showSavedResponses ? (
            <div className="space-y-2">
              {filteredSavedResponses.map((response) => (
                <button
                  key={response.id}
                  onClick={() => handleSelectSavedResponse(response)}
                  className={cn(
                    "w-full rounded-lg border px-2.5 py-2 text-left transition",
                    messages.length === 1 && messages[0]?.id === response.id
                      ? "border-primary bg-primary/12 text-foreground shadow-[0_12px_32px_rgba(79,140,255,0.14)]"
                      : "border-transparent text-muted-foreground hover:border-border hover:bg-secondary/45 hover:text-foreground",
                  )}
                >
                  <p className="truncate text-xs font-semibold">{response.title}</p>
                  <p className="mt-0.5 text-[10px] text-muted-foreground">{formatTime(response.createdAt)}</p>
                </button>
              ))}
              {!filteredSavedResponses.length && <p className="px-3 py-8 text-center text-sm text-muted-foreground">No saved responses yet.</p>}
            </div>
          ) : (
            <div className="space-y-2">
              {filteredConversations.map((conversation) => (
                <div key={conversation.id} className="group relative">
                  <button
                    onClick={() => void handleSelectConversation(conversation.id)}
                    className={cn(
                      "w-full rounded-lg border px-2.5 py-2 text-left transition",
                      activeConversationId === conversation.id ? "border-primary bg-primary/12 text-foreground shadow-[0_12px_32px_rgba(79,140,255,0.14)]" : "border-transparent text-muted-foreground hover:border-border hover:bg-secondary/45 hover:text-foreground",
                    )}
                  >
                    <div className="flex items-start gap-2">
                      {conversation.pinned && <Pin className="mt-0.5 h-3.5 w-3.5 text-cyan-300" />}
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-xs font-medium">{conversation.title}</p>
                        <p className="mt-0.5 text-[10px] text-muted-foreground">{formatTime(conversation.created_at)}</p>
                      </div>
                    </div>
                  </button>
                  <button
                    onClick={() => setOpenConversationMenuId(openConversationMenuId === conversation.id ? null : conversation.id)}
                    className="absolute right-2 top-2 flex h-8 w-8 items-center justify-center rounded-full text-muted-foreground opacity-0 transition hover:bg-secondary hover:text-foreground group-hover:opacity-100"
                  >
                    <MoreHorizontal className="h-4 w-4" />
                  </button>
                  {openConversationMenuId === conversation.id && (
                    <div className="absolute right-2 top-11 z-30 w-48 rounded-2xl border border-border bg-popover p-2 shadow-2xl">
                      <ConversationMenuItem icon={Edit3} label="Rename" onClick={() => void handleRenameConversation(conversation)} />
                      <ConversationMenuItem icon={conversation.pinned ? PinOff : Pin} label={conversation.pinned ? "Unpin" : "Pin"} onClick={() => void handleTogglePinConversation(conversation)} />
                      <ConversationMenuItem icon={Share2} label="Share" onClick={() => void handleShareConversation(conversation)} />
                      <ConversationMenuItem icon={conversation.archived ? RotateCcw : Archive} label={conversation.archived ? "Unarchive" : "Archive"} onClick={() => void (conversation.archived ? handleUnarchiveConversation(conversation) : handleArchiveConversation(conversation))} />
                      <ConversationMenuItem icon={Trash2} label="Delete" onClick={() => void handleDeleteConversation(conversation)} danger />
                    </div>
                  )}
                </div>
              ))}
              {!filteredConversations.length && <p className="px-3 py-8 text-center text-sm text-muted-foreground">No conversations yet.</p>}
            </div>
          )}
        </div>

      </aside>

      <main className="relative z-10 flex min-h-0 min-w-0 flex-1 flex-col">
        <section className="relative flex min-h-0 w-full flex-1 flex-col px-8 pb-5 lg:px-16">
          {messages.length ? <header className="-mx-8 flex h-20 shrink-0 items-center border-b border-white/[0.08] px-8 lg:-mx-16 lg:px-10"><h1 className="truncate text-lg font-semibold text-white">{activeConversation?.title || firstMeaningfulLine(messages.find((item) => item.role === "user")?.content || "CEASER conversation")}</h1>{activeConversation ? <><button onClick={() => void handleTogglePinConversation(activeConversation)} className={cn("ml-3 transition hover:text-cyan-200", activeConversation.pinned ? "text-cyan-300" : "text-white/55")} title={activeConversation.pinned ? "Unpin chat" : "Pin chat"} aria-label={activeConversation.pinned ? "Unpin chat" : "Pin chat"}><Star className={cn("h-4 w-4", activeConversation.pinned && "fill-current")} /></button><div className="relative ml-auto"><button onClick={() => setOpenConversationMenuId(openConversationMenuId === activeConversation.id ? null : activeConversation.id)} className="flex h-9 w-9 items-center justify-center rounded-full text-white/60 transition hover:bg-white/10 hover:text-white" aria-label="Chat options"><MoreHorizontal className="h-5 w-5" /></button>{openConversationMenuId === activeConversation.id ? <div className="absolute right-0 top-11 z-40 w-48 rounded-2xl border border-border bg-popover p-2 shadow-2xl"><ConversationMenuItem icon={Edit3} label="Rename" onClick={() => void handleRenameConversation(activeConversation)} /><ConversationMenuItem icon={activeConversation.pinned ? PinOff : Pin} label={activeConversation.pinned ? "Unpin" : "Pin"} onClick={() => void handleTogglePinConversation(activeConversation)} /><ConversationMenuItem icon={activeConversation.archived ? RotateCcw : Archive} label={activeConversation.archived ? "Unarchive" : "Archive"} onClick={() => void (activeConversation.archived ? handleUnarchiveConversation(activeConversation) : handleArchiveConversation(activeConversation))} /><ConversationMenuItem icon={Trash2} label="Delete" onClick={() => void handleDeleteConversation(activeConversation)} danger /></div> : null}</div></> : null}</header> : null}
          <div
            ref={chatScrollRef}
            onScroll={captureScrollPosition}
            onWheel={stopFollowingStream}
            onTouchStart={stopFollowingStream}
            className={cn("min-h-0 flex-1 overflow-x-hidden overflow-y-auto pr-3", messages.length || isBooting || isActiveChatLoading ? "pt-10" : "pt-[9vh]")}
          >
            {loadError && (
              <div className="mb-4 rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
                {loadError}
              </div>
            )}
            {!messages.length && !isBooting && !isActiveChatLoading ? (
              <>
                <div className="mx-auto mb-6 flex w-fit rounded-full border border-white/10 bg-white/[0.035] px-5 py-2.5 text-sm text-white/80">{timeGreeting}, {displayName} 👋</div>
                <h1 className="flex min-h-[52px] items-center justify-center text-center text-[38px] font-semibold leading-[1.08] text-white md:min-h-[58px] md:text-[46px]" aria-live="polite">
                  <span className="ceaser-gradient-text">{typedWelcomePrompt}</span><span className="ceaser-typewriter-caret" aria-hidden="true" />
                </h1>

                <div className="ceaser-composer mx-auto mt-10 flex min-h-[156px] w-full max-w-[980px] flex-col rounded-[22px] p-5 backdrop-blur-2xl">
                  <input ref={chatFileInputRef} type="file" className="hidden" accept=".pdf,.docx,.pptx,.xlsx,.txt,.png,.jpg,.jpeg" onChange={(event) => void handleChatFileUpload(event)} />
                  <input ref={chatComposerRef} value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => event.key === "Enter" && handleSend()} placeholder="Ask anything or give a command..." className="min-h-14 w-full bg-transparent text-base text-white outline-none placeholder:text-white/50" />
                  <div className="mt-auto flex items-center gap-3">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <button
                          className={cn(
                            "flex h-11 items-center gap-2 rounded-full border border-white/10 bg-white/[0.025] px-3 text-white/75 transition hover:bg-white/[0.05] hover:text-white",
                            modelPreference !== "auto" && "border-cyan-300/30 bg-cyan-300/8 text-cyan-100",
                          )}
                          aria-label={`Choose CEASER model. Current: ${selectedModelLabel}`}
                        >
                          <Sparkles className="h-4 w-4" />
                          <span className="max-w-28 truncate text-xs font-medium">{selectedModelLabel}</span>
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="start" side="top" sideOffset={12} className="w-[260px] border-white/10 bg-[#050914]/98 p-2 text-white shadow-2xl backdrop-blur-xl">
                        <DropdownMenuRadioGroup value={modelPreference} onValueChange={setModelPreference} className="space-y-1">
                          {hfTextModelOptions.map((item) => (
                            <DropdownMenuRadioItem key={item.id} value={item.id} className="rounded-lg px-2.5 py-2 text-sm font-medium text-white data-[state=checked]:bg-white/[0.06]">
                              {item.label}
                            </DropdownMenuRadioItem>
                          ))}
                        </DropdownMenuRadioGroup>
                      </DropdownMenuContent>
                    </DropdownMenu>
                    <button onClick={() => chatFileInputRef.current?.click()} className="flex h-11 w-11 items-center justify-center rounded-full border border-white/10 bg-white/[0.025] text-white/70"><Plus className="h-5 w-5" /></button>
                    <button onClick={() => void handleSend()} disabled={!input.trim()} className="ml-auto flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br from-cyan-400 to-blue-600 text-white shadow-[0_0_28px_rgba(0,174,255,.35)] disabled:opacity-45"><Send className="h-5 w-5" /></button>
                  </div>
                </div>

                <div className="mx-auto mt-9 w-full max-w-[980px]"><h2 className="mb-3 text-lg font-medium text-white">Your Agents</h2><div className="grid grid-cols-2 gap-3 lg:grid-cols-5">{launchAgents.map(({ name, subtitle, icon: Icon, color }) => <button key={name} onClick={() => setInput(`${name}, help me with `)} className="flex min-h-24 items-center gap-3 rounded-xl border border-white/[0.08] bg-[#080e1c]/80 p-3 text-left hover:border-white/20"><span className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-xl", color)}><Icon className="h-5 w-5" /></span><span><span className="block text-sm text-white">{name}</span><span className="mt-1 block text-xs leading-4 text-white/45">{subtitle}</span></span></button>)}</div><div className="mt-5 flex gap-2 overflow-x-auto pb-2">{studentWorkflowShortcuts.map((item) => <button key={item.title} onClick={() => { setActiveLaunchTask(item); setLaunchTaskTopic(""); setLoadError(null) }} className="shrink-0 rounded-lg border border-cyan-300/15 bg-cyan-300/[0.05] px-3 py-2 text-xs text-cyan-100 hover:border-cyan-300/35">{item.title}</button>)}</div></div>
                <p className="mt-8 text-center text-xs text-white/38">CEASER can make mistakes. Verify important information.</p>
              </>
            ) : (
              <div className="mx-auto w-full max-w-[1180px] space-y-7">
                {isBooting || isActiveChatLoading ? (
                  <div className="flex items-center justify-center gap-2 py-12 text-sm text-white/55">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    {isBooting ? "Loading conversation..." : "Opening chat..."}
                  </div>
                ) : (
                  messages.map((message, index) => (
                    <ChatBubble
                      key={message.id}
                      message={message}
                      previousUserPrompt={findPreviousUserPrompt(messages, index)}
                      onPromptSelect={queueFollowUp}
                      onEdit={handleEditSentMessage}
                      userInitial={userInitial}
                    />
                  ))
                )}
              </div>
            )}
          </div>

          <div className={cn("pt-4", !messages.length && !isBooting && !isActiveChatLoading && "hidden")}>
            {attachedFiles.length ? (
              <div className="mb-2 flex flex-wrap gap-2">
                {attachedFiles.map((file) => (
                  <div key={file.id} className="flex items-center gap-2 rounded-full border border-cyan-300/25 bg-cyan-300/8 px-3 py-1.5 text-xs text-cyan-100">
                    <Paperclip className="h-3.5 w-3.5" />
                    <span className="max-w-56 truncate">{file.name}</span>
                    <button onClick={() => setAttachedFiles((current) => current.filter((item) => item.id !== file.id))} className="text-white/50 hover:text-white">Remove</button>
                  </div>
                ))}
              </div>
            ) : null}

            <div className="ceaser-conversation-composer mx-auto flex min-h-[96px] w-full max-w-[980px] flex-col rounded-[20px] px-5 py-4 backdrop-blur-2xl">
              <input
                ref={chatFileInputRef}
                type="file"
                className="hidden"
                accept=".pdf,.docx,.pptx,.xlsx,.txt,.png,.jpg,.jpeg"
                onChange={(event) => void handleChatFileUpload(event)}
              />
              <input
                ref={chatComposerRef}
                type="text"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => event.key === "Enter" && handleSend()}
                placeholder="Ask anything or give a command..."
                disabled={isLoading}
                className="h-10 min-w-0 w-full bg-transparent text-base text-white outline-none placeholder:text-white/45 disabled:opacity-50"
              />
              <div className="mt-auto flex items-center gap-3"><button onClick={() => chatFileInputRef.current?.click()} disabled={isUploadingFile} className="flex h-9 w-9 items-center justify-center rounded-full text-white/60 hover:bg-white/[0.06]">{isUploadingFile ? <Loader2 className="h-4 w-4 animate-spin" /> : <Paperclip className="h-4 w-4" />}</button>{isLoading ? <button onClick={cancelActiveStream} className="ml-auto flex h-11 w-11 items-center justify-center rounded-full bg-rose-500 text-white"><Square className="h-4 w-4 fill-current" /></button> : <button onClick={() => void handleSend()} disabled={!input.trim()} className="ml-auto flex h-11 w-11 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-purple-700 text-white shadow-[0_0_24px_rgba(124,58,237,.38)] disabled:opacity-45"><Send className="h-4 w-4" /></button>}</div>
            </div>
            <p className="mt-2 text-center text-[11px] text-white/35">CEASER can make mistakes. Please verify important information.</p>
          </div>
        </section>
      </main>
      {activeLaunchTask ? (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/65 p-5 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label={activeLaunchTask.title}>
          <div className="w-full max-w-lg rounded-2xl border border-white/12 bg-[#080d1a] p-5 shadow-2xl">
            <div className="flex items-start gap-3">
              <span className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-xl", activeLaunchTask.color)}><ActiveLaunchIcon className="h-5 w-5" /></span>
              <div><h2 className="text-lg font-semibold text-white">{activeLaunchTask.title}</h2><p className="mt-1 text-sm text-white/50">CEASER will create and validate a real {activeLaunchTask.output}.</p></div>
              <button onClick={() => setActiveLaunchTask(null)} className="ml-auto flex h-8 w-8 items-center justify-center rounded-full text-white/55 hover:bg-white/10 hover:text-white" aria-label="Close"><X className="h-4 w-4" /></button>
            </div>
            <label className="mt-5 block text-xs font-medium uppercase tracking-[0.14em] text-white/45">Topic or goal</label>
            <textarea autoFocus value={launchTaskTopic} onChange={(event) => setLaunchTaskTopic(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) launchStructuredTask() }} placeholder="Describe what the finished result should contain..." className="mt-2 min-h-28 w-full resize-none rounded-xl border border-white/10 bg-white/[0.035] p-3 text-sm text-white outline-none placeholder:text-white/30 focus:border-cyan-300/40" />
            {activeLaunchTask.requiresFile ? <button onClick={() => chatFileInputRef.current?.click()} className="mt-3 inline-flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-xs text-white/70 hover:bg-white/[0.05]"><Paperclip className="h-3.5 w-3.5" />{attachedFiles.length ? `${attachedFiles.length} file(s) attached` : "Attach dataset"}</button> : null}
            <div className="mt-5 flex justify-end gap-2"><button onClick={() => setActiveLaunchTask(null)} className="rounded-lg px-4 py-2 text-sm text-white/55 hover:bg-white/[0.05]">Cancel</button><button onClick={launchStructuredTask} disabled={!launchTaskTopic.trim()} className="rounded-lg bg-gradient-to-r from-cyan-500 to-violet-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">Start task</button></div>
          </div>
        </div>
      ) : null}
    </div>
  )
}

function PromptCard({ title, text, color, onClick }: { title: string; text: string; color: "cyan" | "rose" | "green"; onClick: () => void }) {
  const styles = {
    cyan: "from-cyan-300/10 to-cyan-500/5 border-cyan-200/10",
    rose: "from-rose-300/10 to-orange-500/5 border-rose-200/10",
    green: "from-lime-300/10 to-green-500/5 border-lime-200/10",
  }
  const label = {
    cyan: "bg-cyan-100 text-slate-900",
    rose: "bg-rose-100 text-slate-900",
    green: "bg-lime-100 text-slate-900",
  }
  return (
    <button onClick={onClick} className={cn("rounded-xl border bg-gradient-to-br p-2 text-left transition hover:-translate-y-0.5 hover:bg-white/[0.08]", styles[color])}>
      <span className={cn("inline-flex rounded-md px-2 py-1 text-[11px] font-medium", label[color])}>{title}</span>
      <p className="mt-2 text-[11px] text-white/55">{text}</p>
    </button>
  )
}

function findPreviousUserPrompt(messages: Message[], assistantIndex: number) {
  for (let index = assistantIndex - 1; index >= 0; index -= 1) {
    if (messages[index]?.role === "user") return messages[index].content
  }
  return ""
}

type ProjectReport = Record<string, unknown> & { type: "project_report"; title?: string }

function parseProjectReport(content: string): ProjectReport | null {
  const candidate = content.trim().replace(/^```json\s*/i, "").replace(/```$/, "").trim()
  try {
    const parsed = JSON.parse(candidate) as Record<string, unknown>
    return parsed.type === "project_report" ? parsed as ProjectReport : null
  } catch {
    return null
  }
}

const reportText = (value: unknown) => typeof value === "string" ? value : ""
const reportList = (value: unknown) => Array.isArray(value) ? value.map((item) => typeof item === "string" ? item : reportText((item as Record<string, unknown>)?.task || (item as Record<string, unknown>)?.name)).filter(Boolean) : []

function ProjectReportCard({ report }: { report: ProjectReport }) {
  const requirements = report.key_requirements as Record<string, unknown> | undefined
  const scope = report.scope as Record<string, unknown> | undefined
  const components = report.components as Record<string, unknown> | undefined
  const implementation = Array.isArray(report.implementation) ? report.implementation as Array<Record<string, unknown>> : []
  const risks = Array.isArray(report.risks) ? report.risks as Array<Record<string, unknown>> : []
  const sections = [
    ["Objectives", reportList(report.objective)],
    ["Functional requirements", reportList(requirements?.functional)],
    ["Non-functional requirements", reportList(requirements?.non_functional)],
    ["In scope", reportList(scope?.in_scope)],
    ["Out of scope", reportList(scope?.out_of_scope)],
    ["Next steps", reportList(report.next_steps)],
  ] as const

  return (
    <section className="overflow-hidden rounded-2xl border border-cyan-300/20 bg-gradient-to-br from-cyan-400/[0.08] via-slate-950/40 to-violet-500/[0.08]">
      <header className="border-b border-white/10 px-5 py-4">
        <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-cyan-200">CEASER · Project report</p>
        <h2 className="mt-1 text-xl font-semibold text-white">{reportText(report.title) || "Project Report"}</h2>
        {reportText(report.executive_summary) && <p className="mt-3 text-sm leading-6 text-white/72">{reportText(report.executive_summary)}</p>}
      </header>
      <div className="grid gap-3 p-4 md:grid-cols-2">
        {reportText(report.context) && <ReportPanel title="Context"><p>{reportText(report.context)}</p></ReportPanel>}
        {reportText(report.proposed_solution) && <ReportPanel title="Proposed solution"><p>{reportText(report.proposed_solution)}</p></ReportPanel>}
        {sections.filter(([, items]) => items.length).map(([title, items]) => <ReportPanel key={title} title={title}><ReportBullets items={items} /></ReportPanel>)}
      </div>
      {reportList(report.system_workflow).length > 0 && (
        <div className="border-y border-white/10 px-4 py-4">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-cyan-200">System / workflow</p>
          <div className="flex flex-wrap items-center gap-2">{reportList(report.system_workflow).map((step, index) => <span key={`${step}-${index}`} className="inline-flex items-center gap-2 rounded-full border border-cyan-200/15 bg-cyan-200/[0.06] px-3 py-1.5 text-xs text-cyan-50">{step}{index < reportList(report.system_workflow).length - 1 && <span className="text-cyan-300">→</span>}</span>)}</div>
        </div>
      )}
      {implementation.length > 0 && <div className="p-4"><p className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-cyan-200">Implementation plan</p><div className="space-y-2">{implementation.map((phase, index) => <div key={`${reportText(phase.phase)}-${index}`} className="rounded-xl border border-white/10 bg-black/15 p-3"><p className="font-medium text-white">{reportText(phase.phase) || `Phase ${index + 1}`}</p><p className="mt-1 text-xs text-white/55">{reportText(phase.objective) || "Requires confirmation"}</p><ReportBullets items={reportList(phase.tasks)} /></div>)}</div></div>}
      {(components || risks.length > 0 || reportText(report.expected_outcome)) && <div className="grid gap-3 border-t border-white/10 p-4 md:grid-cols-2">
        {components && <ReportPanel title="Components / resources"><ReportBullets items={Object.values(components).flatMap(reportList)} /></ReportPanel>}
        {risks.length > 0 && <ReportPanel title="Risks & constraints"><ReportBullets items={risks.map((risk) => `${reportText(risk.risk) || "Risk requires confirmation"}${reportText(risk.mitigation) ? ` — Mitigation: ${reportText(risk.mitigation)}` : ""}`)} /></ReportPanel>}
        {reportText(report.expected_outcome) && <ReportPanel title="Expected outcome"><p>{reportText(report.expected_outcome)}</p></ReportPanel>}
      </div>}
    </section>
  )
}

function ReportPanel({ title, children }: { title: string; children: ReactNode }) {
  return <section className="rounded-xl border border-white/10 bg-black/15 p-3 text-sm leading-6 text-white/70"><p className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-cyan-200">{title}</p>{children}</section>
}

function ReportBullets({ items }: { items: string[] }) {
  return <ul className="space-y-1.5">{items.map((item, index) => <li key={`${item}-${index}`} className="flex gap-2"><span className="text-cyan-300">•</span><span>{item}</span></li>)}</ul>
}

type FridayStructuredResponse = {
  type: string
  title: string
  summary: string
  sections: Array<{ title: string; description: string; items: unknown[] }>
  actions: unknown[]
  next_steps: unknown[]
  warnings: unknown[]
}

function parseFridayStructuredResponse(content: string): FridayStructuredResponse | null {
  try {
    const value = JSON.parse(content) as Partial<FridayStructuredResponse>
    if (!value || typeof value !== "object" || typeof value.title !== "string" || !Array.isArray(value.sections)) return null
    return {
      type: typeof value.type === "string" ? value.type : "answer",
      title: value.title,
      summary: typeof value.summary === "string" ? value.summary : "",
      sections: value.sections.filter((section): section is { title: string; description: string; items: unknown[] } => Boolean(section) && typeof section.title === "string").map((section) => ({ title: section.title, description: typeof section.description === "string" ? section.description : "", items: Array.isArray(section.items) ? section.items : [] })),
      actions: Array.isArray(value.actions) ? value.actions : [],
      next_steps: Array.isArray(value.next_steps) ? value.next_steps : [],
      warnings: Array.isArray(value.warnings) ? value.warnings : [],
    }
  } catch {
    return null
  }
}

function structuredItemText(item: unknown): string {
  if (typeof item === "string" || typeof item === "number" || typeof item === "boolean") return String(item)
  if (!item || typeof item !== "object" || Array.isArray(item)) return ""
  const preferred = ["phase", "name", "task", "title", "description", "objective", "status", "owner", "priority", "dependency", "risk", "impact", "mitigation", "deliverable"]
  const record = item as Record<string, unknown>
  const entries = preferred.filter((key) => record[key] !== undefined && record[key] !== "").map((key) => `${key.replace(/_/g, " ")}: ${typeof record[key] === "string" ? record[key] : JSON.stringify(record[key])}`)
  return entries.length ? entries.join(" · ") : Object.entries(record).filter(([, value]) => typeof value === "string" || typeof value === "number" || typeof value === "boolean").map(([key, value]) => `${key.replace(/_/g, " ")}: ${value}`).join(" · ")
}

function StructuredResponseCard({ response }: { response: FridayStructuredResponse }) {
  const list = (items: unknown[]) => items.map(structuredItemText).filter(Boolean)
  return (
    <section className="overflow-hidden rounded-2xl border border-cyan-300/20 bg-gradient-to-br from-cyan-400/[0.08] via-slate-950/45 to-violet-500/[0.08]">
      <header className="border-b border-white/10 px-5 py-4">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-cyan-200">Friday · {response.type.replace(/_/g, " ")}</p>
        <h2 className="mt-1 text-xl font-semibold text-white">{response.title}</h2>
        {response.summary && <p className="mt-2 text-sm leading-6 text-white/70">{response.summary}</p>}
      </header>
      {response.sections.length > 0 && <div className="grid gap-3 p-4 md:grid-cols-2">{response.sections.map((section, index) => <section key={`${section.title}-${index}`} className="rounded-xl border border-white/10 bg-black/15 p-3"><h3 className="font-medium text-white">{section.title}</h3>{section.description && <p className="mt-1 text-xs leading-5 text-white/55">{section.description}</p>}{list(section.items).length > 0 && <ul className="mt-3 space-y-2 text-sm text-white/75">{list(section.items).map((item, itemIndex) => <li key={`${item}-${itemIndex}`} className="flex gap-2"><span className="text-cyan-300">•</span><span>{item}</span></li>)}</ul>}</section>)}</div>}
      {(response.actions.length > 0 || response.next_steps.length > 0 || response.warnings.length > 0) && <div className="grid gap-3 border-t border-white/10 p-4 md:grid-cols-3">
        {response.actions.length > 0 && <StructuredList title="Actions" items={list(response.actions)} />}
        {response.next_steps.length > 0 && <StructuredList title="Next steps" items={list(response.next_steps)} />}
        {response.warnings.length > 0 && <StructuredList title="Requires confirmation" items={list(response.warnings)} tone="amber" />}
      </div>}
    </section>
  )
}

function StructuredList({ title, items, tone = "cyan" }: { title: string; items: string[]; tone?: "cyan" | "amber" }) {
  return <section className="rounded-xl border border-white/10 bg-black/15 p-3"><p className={cn("text-xs font-semibold uppercase tracking-[0.14em]", tone === "amber" ? "text-amber-200" : "text-cyan-200")}>{title}</p><ul className="mt-2 space-y-1.5 text-sm text-white/70">{items.map((item, index) => <li key={`${item}-${index}`} className="flex gap-2"><span className={tone === "amber" ? "text-amber-300" : "text-cyan-300"}>•</span><span>{item}</span></li>)}</ul></section>
}

function ChatBubble({
  message,
  previousUserPrompt,
  onPromptSelect,
  onEdit,
  userInitial,
}: {
  message: Message
  previousUserPrompt?: string
  onPromptSelect: (prompt: string) => void
  onEdit: (message: Message) => void
  userInitial: string
}) {
  const isUser = message.role === "user"
  return (
    <div className={cn("flex w-full gap-4", isUser ? "justify-end" : "justify-start")}>
      {!isUser && <div className="mt-1 flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-violet-500/45 bg-violet-500/10 text-violet-300 shadow-[0_0_24px_rgba(139,92,246,.14)]"><Sparkles className="h-5 w-5" /></div>}
      <div className={cn(isUser ? "max-w-[68%] text-white" : "min-w-0 flex-1 text-white")}>
        {!isUser && <div className="mb-3 flex items-center gap-3"><span className="font-semibold text-violet-400">CEASER</span><span className="text-xs text-white/40">{message.timestamp}</span>{!message.isTyping && !message.isStreaming ? <span className="ml-auto inline-flex items-center gap-2 rounded-full bg-emerald-500/[0.07] px-4 py-2 text-xs text-emerald-400"><Check className="h-3.5 w-3.5" />Completed</span> : null}</div>}
        {message.isTyping ? (
          <div className="flex items-center gap-2 text-white/55">
            <Loader2 className="h-4 w-4 animate-spin" aria-label="Generating response" />
          </div>
        ) : (
          <>
          <div className={cn(isUser ? "rounded-2xl border border-violet-500/45 bg-gradient-to-br from-violet-500/[0.16] to-purple-900/[0.16] px-5 py-4 shadow-[0_14px_45px_rgba(76,29,149,.12)]" : "rounded-2xl border border-white/[0.12] bg-[#080d1b]/76 p-5 shadow-[0_20px_60px_rgba(0,0,0,.2)]")}>
            {isUser && <div className="mb-2 flex items-center justify-between text-xs"><span className="font-semibold text-violet-300">You</span><span className="text-white/45">{message.timestamp}</span></div>}
            {message.role === "assistant" && !message.isStreaming && message.richResponse && hasStructuredRichContent(message.richResponse)
              ? <RichResponseRenderer response={message.richResponse} onAction={onPromptSelect} />
              : message.role === "assistant" && message.isStreaming && message.content.trimStart().startsWith("{")
              ? <div className="inline-flex items-center justify-center rounded-xl border border-cyan-300/15 bg-cyan-300/[0.05] px-3 py-2 text-cyan-100"><Loader2 className="h-4 w-4 animate-spin" aria-label="Streaming response" /></div>
              : message.role === "assistant" && !message.isStreaming && parseProjectReport(message.content)
                ? <ProjectReportCard report={parseProjectReport(message.content)!} />
                : message.role === "assistant" && !message.isStreaming && parseFridayStructuredResponse(message.content)
                ? <StructuredResponseCard response={parseFridayStructuredResponse(message.content)!} />
                : message.role === "assistant" && !message.isStreaming && message.artifact
                ? <><MarkdownMessage content={stripSandboxArtifactLinks(message.content)} isUser={false} isStreaming={false} /><GeneratedArtifactCard artifact={message.artifact} /></>
                : message.role === "assistant" && !message.isStreaming && extractCodeArtifact(message.content)
                ? <CodeArtifactCard artifact={extractCodeArtifact(message.content)!} />
                : <MarkdownMessage content={message.role === "assistant" ? stripSandboxArtifactLinks(message.content) : message.content} isUser={message.role === "user"} isStreaming={Boolean(message.isStreaming)} />}
            {message.role === "assistant" && !message.isStreaming && message.research?.images?.length ? (
              <ResearchImageStrip images={message.research.images} />
            ) : message.role === "assistant" && !message.isStreaming && message.research?.sources?.some((source) => source.image_url) ? (
              <ResearchImageStrip images={message.research.sources.filter((source) => source.image_url).map((source) => ({ title: source.title, url: source.url, image_url: source.image_url as string, source: source.source }))} />
            ) : null}
            {message.role === "user" && (
              <button
                onClick={() => onEdit(message)}
                className="ml-auto mt-2 inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-white/48 transition hover:bg-white/[0.08] hover:text-white"
                title="Edit and resend message"
              >
                <Edit3 className="h-3.5 w-3.5" />
                Edit
              </button>
            )}
          </div>
          {message.role === "assistant" && !message.isStreaming && (
              <ResponseActions message={message} previousUserPrompt={previousUserPrompt} onPromptSelect={onPromptSelect} />
          )}
          </>
        )}
      </div>
      {isUser && (
        <div className="mt-1 flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-blue-700 text-xs font-semibold text-white">
          {userInitial}
        </div>
      )}
    </div>
  )
}

function ResearchImageStrip({ images }: { images: NonNullable<ResearchResult["images"]> }) {
  const previews = images.slice(0, 3)
  if (!previews.length) return null

  return (
    <div className="mt-4 flex gap-3 overflow-x-auto pb-1" aria-label="Images from live research">
      {previews.map((source) => (
        <a
          key={`${source.url}-${source.image_url}`}
          href={source.url}
          target="_blank"
          rel="noreferrer"
          className="group relative block h-36 w-48 shrink-0 overflow-hidden rounded-lg border border-white/10 bg-white/5 focus:outline-none focus:ring-2 focus:ring-cyan-300/70"
          title={`Open ${source.title}`}
        >
          <img
            src={source.image_url ?? ""}
            alt={source.title}
            className="h-full w-full object-cover transition duration-300 group-hover:scale-105"
            loading="lazy"
            referrerPolicy="no-referrer"
            onError={(event) => { event.currentTarget.closest("a")?.remove() }}
          />
          <span className="absolute inset-x-0 bottom-0 bg-black/65 px-2 py-1.5 text-xs text-white line-clamp-1">{source.source}</span>
        </a>
      ))}
    </div>
  )
}

function ConversationMenuItem({
  icon: Icon,
  label,
  onClick,
  danger = false,
}: {
  icon: LucideIcon
  label: string
  onClick: () => void
  danger?: boolean
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors hover:bg-secondary",
        danger ? "text-destructive hover:text-destructive" : "text-foreground",
      )}
    >
      <Icon className="h-4 w-4" />
      <span>{label}</span>
    </button>
  )
}

type ResponseAction = {
  id: string
  label: string
  icon: LucideIcon
  run: () => void | Promise<void>
}

function ResponseActions({
  message,
  previousUserPrompt,
  onPromptSelect,
}: {
  message: Message
  previousUserPrompt?: string
  onPromptSelect: (prompt: string) => void
}) {
  const [copied, setCopied] = useState(false)
  const [feedback, setFeedback] = useState<"like" | "dislike" | null>(null)
  const [saved, setSaved] = useState(false)
  const [isSavingDocument, setIsSavingDocument] = useState(false)
  const [savedDocumentName, setSavedDocumentName] = useState<string | null>(null)
  const content = message.content.trim()
  const hasBackendSuggestions = safeArray(message.metadata?.suggestions).length > 0
  const contextualActions = useMemo(() => getContextualActions(content), [content])
  const proactiveSuggestions = useMemo(() => {
    const backendSuggestions = safeArray(message.metadata?.suggestions)
      .map((item) => (typeof item === "string" ? item : item?.text))
      .filter((item): item is string => Boolean(item))
    return backendSuggestions.slice(0, 5)
  }, [message.metadata?.suggestions])

  useEffect(() => {
    try {
      const records = JSON.parse(window.localStorage.getItem(SAVED_RESPONSES_KEY) || "[]") as SavedResponse[]
      setSaved(records.some((item) => item.content === content))
    } catch {
      setSaved(false)
    }
  }, [content])

  const copyText = async () => {
    await navigator.clipboard?.writeText(content)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1400)
  }

  const shareText = async () => {
    if (navigator.share) {
      await navigator.share({ title: firstMeaningfulLine(content), text: content })
      return
    }
    await copyText()
  }

  const saveResponse = () => {
    let existing: SavedResponse[] = []
    try {
      const parsed = JSON.parse(window.localStorage.getItem(SAVED_RESPONSES_KEY) || "[]") as SavedResponse[]
      existing = Array.isArray(parsed) ? parsed : []
    } catch {
      existing = []
    }
    if (existing.some((item) => item.content === content)) {
      setSaved(true)
      return
    }
    const record: SavedResponse = {
      id: `saved-${Date.now()}`,
      title: firstMeaningfulLine(content) || "Saved CEASER response",
      content,
      createdAt: new Date().toISOString(),
    }
    window.localStorage.setItem(SAVED_RESPONSES_KEY, JSON.stringify([record, ...existing].slice(0, 100)))
    setSaved(true)
    window.dispatchEvent(new Event(SAVED_RESPONSE_EVENT))
  }

  const saveAsDocument = async () => {
    const request = message.documentRequest
    if (!request || isSavingDocument || savedDocumentName) return
    setIsSavingDocument(true)
    try {
      const generated = await documentsApi.create({
        kind: request.kind,
        prompt: previousUserPrompt || `Create a ${request.label}`,
        agent_id: request.agentId,
        source_content: content.slice(0, 50000),
      })
      setSavedDocumentName(generated.document.file_name || "Document saved")
      window.dispatchEvent(new Event("ceaser:activity-updated"))
    } finally {
      setIsSavingDocument(false)
    }
  }

  const universal: ResponseAction[] = [
    { id: "copy", label: copied ? "Copied" : "Copy", icon: copied ? Check : Copy, run: copyText },
    ...(message.documentRequest ? [{ id: "save-document", label: savedDocumentName ? "Saved to Files" : isSavingDocument ? "Saving..." : "Save to Files", icon: savedDocumentName ? Check : FileText, run: saveAsDocument }] : []),
    { id: "like", label: "Like", icon: ThumbsUp, run: () => setFeedback(feedback === "like" ? null : "like") },
    { id: "dislike", label: "Dislike", icon: ThumbsDown, run: () => setFeedback(feedback === "dislike" ? null : "dislike") },
    { id: "share", label: "Share", icon: Share2, run: shareText },
    { id: "save", label: saved ? "Saved" : "Save", icon: saved ? Check : Bookmark, run: saveResponse },
  ]

  const actions: ResponseAction[] = [
    ...universal,
    ...contextualActions.map((action) => ({
      ...action,
      run: () => runContextAction(action.id, content),
    })),
  ]

  return (
    <div className="mt-4 space-y-3">
      {ENABLE_CHAT_SUGGESTIONS && proactiveSuggestions.length && (hasBackendSuggestions || !message.isStreaming) ? (
        <div>
          <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.18em] text-white/35">Next suggestions</p>
          <div className="flex flex-wrap gap-2">
            {proactiveSuggestions.map((suggestion) => (
              <button
                key={suggestion}
                onClick={() => onPromptSelect(suggestion)}
                className="inline-flex min-h-8 items-center rounded-full border border-cyan-300/15 bg-cyan-300/8 px-3 py-1.5 text-xs text-cyan-100 transition hover:bg-cyan-300/14"
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>
      ) : null}
      <div className="flex flex-wrap gap-2">
        {actions.map((action) => {
          const Icon = action.icon
          const active = (action.id === "like" && feedback === "like") || (action.id === "dislike" && feedback === "dislike") || (action.id === "save" && saved)
          return (
            <button
              key={action.id}
              onClick={() => void action.run()}
              className={cn(
                "inline-flex h-9 items-center gap-2 rounded-lg border border-white/[0.09] bg-transparent px-3 text-xs text-white/58 transition hover:bg-white/[0.06] hover:text-white",
                active && "bg-cyan-400/12 text-cyan-200",
              )}
            >
              <Icon className="h-3.5 w-3.5" />
              {action.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}

function getContextualActions(content: string): Array<Omit<ResponseAction, "run">> {
  const lower = content.toLowerCase()
  const actions: Array<Omit<ResponseAction, "run">> = []
  const add = (id: string, label: string, icon: LucideIcon) => {
    if (!actions.some((action) => action.id === id)) actions.push({ id, label, icon })
  }

  if (/(study|revision|timetable|time table|schedule|day \| focus|\| day \|)/i.test(content)) {
    add("calendar", "Add to Calendar", CalendarPlus)
  }
  if (/(email|mail|dear |subject:|cover letter|application)/i.test(content)) {
    add("gmail", "Open in Gmail", Mail)
  }
  return actions.slice(0, 4)
}

function runContextAction(id: string, content: string) {
  if (id === "gmail") {
    const subject = encodeURIComponent(firstMeaningfulLine(content) || "CEASER Draft")
    const body = encodeURIComponent(content)
    window.open(`https://mail.google.com/mail/?view=cm&fs=1&su=${subject}&body=${body}`, "_blank", "noopener,noreferrer")
    return
  }

  if (id === "calendar") {
    const title = encodeURIComponent(firstMeaningfulLine(content) || "CEASER Plan")
    const details = encodeURIComponent(content)
    window.open(`https://calendar.google.com/calendar/render?action=TEMPLATE&text=${title}&details=${details}`, "_blank", "noopener,noreferrer")
    return
  }

  const blob = new Blob([content], { type: "text/plain;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  const suffix = id.replace(/[^a-z0-9]+/gi, "-").toLowerCase()
  link.href = url
  link.download = `${slugify(firstMeaningfulLine(content) || "ceaser-output")}-${suffix}.txt`
  link.click()
  URL.revokeObjectURL(url)
}

function firstMeaningfulLine(content: string) {
  return content
    .split("\n")
    .map((line) => line.replace(/^#{1,3}\s*/, "").trim())
    .find((line) => line && !line.startsWith("|") && !/^[-*]\s*$/.test(line)) ?? "CEASER Response"
}

function slugify(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "").slice(0, 50) || "ceaser-response"
}

function MarkdownMessage({ content, isUser, isStreaming }: { content: string; isUser: boolean; isStreaming?: boolean }) {
  if (isUser) return <p className="whitespace-pre-wrap text-sm leading-relaxed">{content}</p>
  if (isStreaming && !content.trim()) {
    return <div className="flex items-center gap-2 text-sm text-white/60"><Loader2 className="h-4 w-4 animate-spin" /> Writing response…</div>
  }
  const visibleContent = content.replace(/\s*\(\s*\[?[-\w.]+\.(?:com|org|net|gov|edu|in)\]?\s*\)/gi, "")
  const structured = isStreaming ? null : parseAnswerSections(visibleContent)
  if (structured) return <StructuredAnswer data={structured} />

  const lines = visibleContent.split("\n")
  const elements: ReactNode[] = []
  let bullets: string[] = []

  const flushBullets = () => {
    if (!bullets.length) return
    elements.push(
      <ul key={`ul-${elements.length}`} className="my-2 list-disc space-y-1 pl-5 text-sm">
        {bullets.map((bullet, index) => (
          <li key={`${bullet}-${index}`}>{renderInlineMarkdown(bullet)}</li>
        ))}
      </ul>,
    )
    bullets = []
  }

  for (let index = 0; index < lines.length; index += 1) {
    const fence = lines[index].match(/^\s*```([^\s`]*)\s*$/)
    if (fence) {
      flushBullets()
      const codeLines: string[] = []
      let endIndex = index + 1
      while (endIndex < lines.length && !/^\s*```\s*$/.test(lines[endIndex])) {
        codeLines.push(lines[endIndex])
        endIndex += 1
      }
      elements.push(<MarkdownCodeBlock key={`code-${index}`} language={fence[1] || "code"} content={codeLines.join("\n")} streaming={Boolean(isStreaming && endIndex >= lines.length)} />)
      index = endIndex < lines.length ? endIndex : lines.length
      continue
    }
    const table = readMarkdownTable(lines, index)
    if (table) {
      flushBullets()
      elements.push(<MarkdownTable key={`table-${index}`} headers={table.headers} rows={table.rows} />)
      index = table.endIndex
      continue
    }
    const line = lines[index]
    const trimmed = line.trim()
    if (!trimmed) {
      flushBullets()
      continue
    }
    if (trimmed.startsWith("### ")) {
      flushBullets()
      elements.push(<h3 key={index} className="mb-1 mt-3 text-sm font-semibold">{renderInlineMarkdown(trimmed.slice(4))}</h3>)
      continue
    }
    if (trimmed.startsWith("## ")) {
      flushBullets()
      elements.push(<h2 key={index} className="mb-2 text-base font-semibold">{renderInlineMarkdown(trimmed.slice(3))}</h2>)
      continue
    }
    if (trimmed.startsWith("# ")) {
      flushBullets()
      elements.push(<h1 key={index} className="mb-2 text-lg font-semibold">{renderInlineMarkdown(trimmed.slice(2))}</h1>)
      continue
    }
    if (/^[-*]\s+/.test(trimmed)) {
      bullets.push(trimmed.replace(/^[-*]\s+/, ""))
      continue
    }
    flushBullets()
    elements.push(<p key={index} className="my-2 text-sm leading-relaxed">{renderInlineMarkdown(trimmed)}</p>)
  }
  flushBullets()

  return <div className="space-y-1">{elements}{isStreaming ? <span aria-label="CEASER is typing" className="ml-1 inline-block h-4 w-1 animate-pulse bg-cyan-300 align-[-2px]" /> : null}</div>
}

function MarkdownCodeBlock({ language, content, streaming }: { language: string; content: string; streaming: boolean }) {
  const [copied, setCopied] = useState(false)
  const label = language.trim().toUpperCase() || "CODE"
  const copyCode = async () => {
    await navigator.clipboard.writeText(content)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1400)
  }
  return (
    <section className="my-4 overflow-hidden rounded-md border border-white/15 bg-[#070a0d] shadow-[0_16px_40px_rgba(0,0,0,0.28)]">
      <header className="flex h-10 items-center justify-between border-b border-white/10 bg-white/[0.035] px-3">
        <span className="rounded border border-white/15 bg-white/[0.07] px-2 py-1 font-mono text-[11px] font-semibold text-white/88">{label}</span>
        <button type="button" onClick={() => void copyCode()} className="flex items-center gap-1.5 text-xs font-medium text-white/72 transition hover:text-cyan-300" aria-label="Copy code">
          {copied ? <Check className="h-3.5 w-3.5 text-emerald-300" /> : <Copy className="h-3.5 w-3.5" />}{copied ? "Copied" : "Copy"}
        </button>
      </header>
      <pre className="max-h-[32rem] overflow-auto p-4 font-mono text-[13px] leading-6 text-slate-200"><code>{highlightCode(content, language)}</code>{streaming ? <span className="ml-0.5 inline-block h-4 w-1 animate-pulse bg-cyan-300 align-[-2px]" /> : null}</pre>
    </section>
  )
}

function highlightCode(content: string, language: string): ReactNode[] {
  const htmlLike = /^(html|xml|svg|jsx|tsx)$/i.test(language)
  const pattern = htmlLike
    ? /(<!--[\s\S]*?-->|<\/?[A-Za-z][^>]*>|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')/g
    : /(\/\*[\s\S]*?\*\/|\/\/[^\n]*|#[^\n]*|`(?:\\.|[^`\\])*`|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\b(?:const|let|var|function|return|if|else|for|while|class|def|import|from|export|async|await|new|try|catch|throw|true|false|null|None|True|False)\b|\b\d+(?:\.\d+)?\b)/g
  return content.split(pattern).filter(Boolean).map((token, index) => {
    let color = "text-slate-200"
    if (/^(<!--|\/\*|\/\/|#)/.test(token)) color = "text-slate-500"
    else if (/^<\/?[A-Za-z]/.test(token)) color = "text-pink-400"
    else if (/^["'`]/.test(token)) color = "text-lime-300"
    else if (/^(const|let|var|function|return|if|else|for|while|class|def|import|from|export|async|await|new|try|catch|throw|true|false|null|None|True|False)$/.test(token)) color = "text-cyan-300"
    else if (/^\d/.test(token)) color = "text-amber-300"
    return <span key={`${index}-${token.slice(0, 12)}`} className={color}>{token}</span>
  })
}

function readMarkdownTable(lines: string[], startIndex: number) {
  const header = lines[startIndex]?.trim()
  const separator = lines[startIndex + 1]?.trim()
  if (!header?.includes("|") || !separator || !/^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(separator)) return null
  const headers = splitTableRow(header)
  const rows: string[][] = []
  let endIndex = startIndex + 1
  for (let index = startIndex + 2; index < lines.length; index += 1) {
    const line = lines[index].trim()
    if (!line.includes("|")) break
    rows.push(splitTableRow(line))
    endIndex = index
  }
  return headers.length && rows.length ? { headers, rows, endIndex } : null
}

function splitTableRow(line: string) {
  return line.replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim())
}

function MarkdownTable({ headers, rows }: { headers: string[]; rows: string[][] }) {
  return (
    <div className="my-4 overflow-x-auto">
      <table className="w-full min-w-[720px] border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-white/12 text-white/72">
            {headers.map((header) => (
              <th key={header} className="px-3 py-2 font-semibold">{renderInlineMarkdown(header)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex} className="border-b border-white/8 align-top">
              {headers.map((header, cellIndex) => (
                <td key={`${header}-${cellIndex}`} className="px-3 py-3 text-white/70">{renderInlineMarkdown(row[cellIndex] ?? "")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

type AnswerSections = {
  title?: string
  executiveSummary?: string[]
  keyTrends?: string[]
  insights?: string[]
  recommendations?: string[]
  fallback: string[]
}

function parseAnswerSections(content: string): AnswerSections | null {
  const lines = content.split("\n").map((line) => line.trim()).filter(Boolean)
  if (!lines.length) return null
  const data: AnswerSections = { fallback: [] }
  let current: keyof AnswerSections | "fallback" = "fallback"

  for (const line of lines) {
    const clean = line.replace(/^#{1,3}\s*/, "").trim()
    const lower = clean.toLowerCase()
    if (line.startsWith("# ") || line.startsWith("## ")) {
      if (!["executive summary", "key findings", "key trends", "insights", "recommendations", "sources"].includes(lower)) {
        data.title = clean
        continue
      }
    }
    if (lower === "executive summary") {
      current = "executiveSummary"
      data.executiveSummary = []
      continue
    }
    if (lower === "key trends" || lower === "key findings") {
      current = "keyTrends"
      data.keyTrends = []
      continue
    }
    if (lower === "insights") {
      current = "insights"
      data.insights = []
      continue
    }
    if (lower === "recommendations") {
      current = "recommendations"
      data.recommendations = []
      continue
    }
    if (lower === "sources") {
      current = "fallback"
      continue
    }

    const normalized = clean.replace(/^[-*]\s+/, "")
    if (current === "executiveSummary") data.executiveSummary?.push(normalized)
    else if (current === "keyTrends") data.keyTrends?.push(normalized)
    else if (current === "insights") data.insights?.push(normalized)
    else if (current === "recommendations") data.recommendations?.push(normalized)
    else data.fallback.push(normalized)
  }

  if (!data.executiveSummary && !data.keyTrends && !data.insights && !data.recommendations) return null
  return data
}

function StructuredAnswer({ data }: { data: AnswerSections }) {
  const trends = data.keyTrends ?? []
  const recommendations = data.recommendations ?? []
  const insights = data.insights ?? []

  return (
    <div>
      {data.title && <h1 className="text-xl font-semibold tracking-normal">{renderInlineMarkdown(data.title)}</h1>}
      {data.executiveSummary?.length ? (
        <section className="mt-4">
          <h2 className="text-sm font-semibold">Executive Summary</h2>
          <div className="mt-2 space-y-2 text-sm leading-relaxed text-white/82">
            {data.executiveSummary.map((item, index) => <p key={index}>{renderInlineMarkdown(item)}</p>)}
          </div>
        </section>
      ) : null}

      {trends.length ? (
        <section className="mt-5">
          <h2 className="text-sm font-semibold">Key Trends</h2>
          <div className="mt-3 grid gap-5 md:grid-cols-3">
            {trends.slice(0, 3).map((trend, index) => {
              const [title, body] = splitBoldLead(trend)
              return (
                <article key={index}>
                  <p className="mb-2 text-lg leading-none">💬</p>
                  <h3 className="text-sm font-semibold">{renderInlineMarkdown(title)}</h3>
                  {body && <p className="mt-1 text-sm leading-relaxed text-white/62">{renderInlineMarkdown(body)}</p>}
                </article>
              )
            })}
          </div>
          {trends.length > 3 && (
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-white/62">
              {trends.slice(3).map((trend, index) => <li key={index}>{renderInlineMarkdown(trend)}</li>)}
            </ul>
          )}
        </section>
      ) : null}

      {(insights.length || recommendations.length) ? (
        <section className="mt-5 grid gap-6 md:grid-cols-2">
          {insights.length ? (
            <div>
              <h2 className="text-sm font-semibold">Insights</h2>
              <div className="mt-2 space-y-2 text-sm leading-relaxed text-white/62">
                {insights.map((item, index) => <p key={index}>{renderInlineMarkdown(item)}</p>)}
              </div>
            </div>
          ) : null}
          {recommendations.length ? (
            <div>
              <h2 className="text-sm font-semibold">Recommendations</h2>
              <ul className="mt-2 space-y-2">
                {recommendations.map((item, index) => (
                  <li key={index} className="flex gap-2 text-sm leading-relaxed text-white/62">
                    <span className="mt-0.5 text-emerald-300">✅</span>
                    <span>{renderInlineMarkdown(item)}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>
      ) : null}

      {data.fallback.length ? (
        <div className="mt-4 space-y-2 text-sm leading-relaxed text-white/62">
          {data.fallback.map((item, index) => <p key={index}>{renderInlineMarkdown(item)}</p>)}
        </div>
      ) : null}
    </div>
  )
}

function splitBoldLead(value: string) {
  const match = value.match(/^\*\*([^*]+)\*\*:?\s*(.*)$/)
  if (match) return [match[1], match[2]] as const
  const colon = value.indexOf(":")
  if (colon > 0 && colon < 70) return [value.slice(0, colon), value.slice(colon + 1).trim()] as const
  return [value, ""] as const
}

function renderInlineMarkdown(value: string) {
  const parts = value.split(/(\*\*[^*]+\*\*)/g)
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>
    }
    return <span key={index}>{part}</span>
  })
}

function ResearchSidePanel({ message }: { message?: Message }) {
  const memories = message?.memoriesUsed ?? []
  const contributions = message?.contributions ?? []
  const workflow = message?.workflow

  return (
    <aside className="hidden w-80 flex-shrink-0 space-y-3 overflow-y-auto lg:block">
      <section className="rounded-3xl border border-white/10 bg-[#111827]/72 p-4 shadow-[0_22px_65px_rgba(0,0,0,0.22)]">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Workflow</h2>
          <span className="text-xs capitalize text-muted-foreground">{workflow?.status ?? "Ready"}</span>
        </div>
        {workflow ? (
          <div>
            <p className="text-sm font-medium capitalize">{workflow.type.replace(/_/g, " ")}</p>
            <p className="mt-1 text-xs text-muted-foreground">{workflow.summary}</p>
            <div className="mt-3 space-y-2">
              {workflow.steps.map((step) => (
                <div key={step.id} className="rounded-xl border border-white/10 bg-white/5 p-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-medium">{step.agent_name}</span>
                    <span className={cn("rounded-full px-2 py-0.5 text-[10px] capitalize", step.status === "completed" ? "bg-emerald-500/10 text-emerald-400" : step.status === "running" ? "bg-primary/10 text-primary" : "bg-secondary text-muted-foreground")}>{step.status}</span>
                  </div>
                  {step.output_summary && <p className="mt-1 line-clamp-2 text-[11px] text-muted-foreground">{step.output_summary}</p>}
                </div>
              ))}
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Workflow activity appears here after a workforce response.</p>
        )}
      </section>

      <section className="rounded-3xl border border-white/10 bg-[#111827]/72 p-4 shadow-[0_22px_65px_rgba(0,0,0,0.18)]">
        <h2 className="text-sm font-semibold">Context Used</h2>
        <div className="mt-3">
          <p className="text-xs font-medium text-muted-foreground">Scope</p>
          <p className="mt-1 text-sm">CEASER OS</p>
        </div>
        {memories.length > 0 && (
          <div className="mt-3">
            <p className="text-xs font-medium text-muted-foreground">Relevant memories ({memories.length})</p>
            <ul className="mt-2 space-y-1">
              {memories.slice(0, 4).map((memory) => (
                <li key={memory.id} className="flex gap-2 text-xs text-muted-foreground">
                  <CheckCircle2 className="mt-0.5 h-3 w-3 flex-shrink-0 text-primary" />
                  <span>{memory.content}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <section className="rounded-3xl border border-white/10 bg-[#111827]/72 p-4 shadow-[0_22px_65px_rgba(0,0,0,0.18)]">
        <h2 className="text-sm font-semibold">Agents Involved</h2>
        {contributions.length ? (
          <div className="mt-3 space-y-2">
            {contributions.map((contribution) => (
              <div key={contribution.agent} className="rounded-2xl border border-white/10 bg-white/5 p-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium">{contribution.agent}</p>
                    <p className="text-xs text-muted-foreground">{contribution.domain}</p>
                  </div>
                  <span className="rounded-full border border-primary/40 px-2 py-1 text-xs text-primary">{Math.round(contribution.confidence * 100)}%</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-2 text-sm text-muted-foreground">Agent details appear after CEASER responds.</p>
        )}
      </section>
    </aside>
  )
}
