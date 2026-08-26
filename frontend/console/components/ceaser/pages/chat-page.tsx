"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import type { ChangeEvent, ReactNode } from "react"
import { chatApi, type AgentContribution, type CeaserChatResponse, type ChatMessage, type ConversationRecord, type MessageMetadata, type RankedMemory, type ResearchResult, type WorkflowResult } from "@/lib/api/chat"
import { documentsApi, type DocumentKind } from "@/lib/api/documents"
import { filesApi, type FileRecord } from "@/lib/api/files"
import { useApp } from "@/lib/app-context"
import { cn } from "@/lib/utils"
import { CeaserLogo } from "../ceaser-logo"
import { FOOTER_VOICE_EVENT } from "../command-bar"
import { VoiceControls } from "@/components/voice/VoiceControls"
import type { VoiceRespondResponse } from "@/lib/api/voice"
import { Archive, Bookmark, CalendarPlus, Check, CheckCircle2, ChevronLeft, Copy, Edit3, Loader2, Mail, MessageSquare, MoreHorizontal, Paperclip, Pin, PinOff, Plus, RotateCcw, Search, Send, Share2, ThumbsDown, ThumbsUp, Trash2 } from "lucide-react"
import type { LucideIcon } from "lucide-react"

interface Message {
  id: string
  role: "user" | "assistant" | "system"
  content: string
  timestamp: string
  agentIds?: string[]
  highlights?: string[]
  memoriesUsed?: RankedMemory[]
  contributions?: AgentContribution[]
  contributionSummary?: string
  research?: ResearchResult | null
  workflow?: WorkflowResult | null
  isTyping?: boolean
}

const ACTIVE_CONVERSATION_KEY = "ceaser_active_conversation_id"
const SAVED_RESPONSES_KEY = "ceaser_saved_responses"
const SAVED_RESPONSE_EVENT = "ceaser_saved_response"

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

const agentNameToId = (name: string) => name.toLowerCase()

const detectDocumentRequest = (message: string): DocumentRequest | null => {
  const normalized = message.toLowerCase()
  if (!/\b(create|write|draft|generate|make|prepare)\b/.test(normalized)) return null
  if (/\b(pitch deck|deck|slides|presentation|ppt|pptx)\b/.test(normalized)) return { kind: "pptx", label: "PowerPoint deck", agentId: "zeus" }
  if (/\b(excel|spreadsheet|sheet|tracker|xlsx|table)\b/.test(normalized)) return { kind: "xlsx", label: "Excel sheet", agentId: "bolt" }
  if (/\b(pdf)\b/.test(normalized)) return { kind: "pdf", label: "PDF document", agentId: "friday" }
  if (/\b(document|doc|docx|report|business plan|proposal|brief|article|essay|writeup|write-up|marketing plan|startup plan)\b/.test(normalized)) {
    const agentId = /\b(business plan|startup plan|strategy|revenue|growth|investor)\b/.test(normalized) ? "zeus" : "friday"
    return { kind: "docx", label: "Word document", agentId }
  }
  return null
}

const documentCreatedMessage = (request: DocumentRequest, fileName?: string | null) =>
  [
    "Document Created",
    "",
    `CEASER created a real ${request.label}${fileName ? `: ${fileName}` : ""}.`,
    "",
    "You can find it in Files. Use the file actions there to download, review, summarize, or ask CEASER about it.",
  ].join("\n")

const formatTime = (value?: string) => {
  const date = value ? new Date(value) : new Date()
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
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
  const selectedAgents = metadata.selected_agents ?? []
  const memoriesUsed = metadata.memories_used ?? []
  const sourceCount = metadata.research?.sources.length ?? 0
  const highlights =
    message.role === "assistant" && (selectedAgents.length || metadata.scope || memoriesUsed.length || sourceCount)
      ? [
          metadata.scope ? `Scope: ${metadata.scope}` : null,
          selectedAgents.length ? `Selected Agents: ${selectedAgents.join(", ")}` : null,
          `Memories Used: ${memoriesUsed.length}`,
          `Sources: ${sourceCount}`,
        ].filter(Boolean) as string[]
      : undefined

  return {
    agentIds: selectedAgents.length ? selectedAgents.map(agentNameToId) : undefined,
    highlights,
    memoriesUsed,
    contributions: metadata.contributions,
    contributionSummary: metadata.contribution_summary,
    research: metadata.research,
    workflow: metadata.workflow,
  }
}

export function ChatPage() {
  const { setCurrentPage, confirmDialog, promptDialog } = useApp()
  const [conversations, setConversations] = useState<ConversationRecord[]>([])
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [searchQuery, setSearchQuery] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [isUploadingFile, setIsUploadingFile] = useState(false)
  const [attachedFiles, setAttachedFiles] = useState<FileRecord[]>([])
  const [isBooting, setIsBooting] = useState(true)
  const [openConversationMenuId, setOpenConversationMenuId] = useState<string | null>(null)
  const [showArchivedChats, setShowArchivedChats] = useState(false)
  const [showSavedResponses, setShowSavedResponses] = useState(false)
  const [savedResponses, setSavedResponses] = useState<SavedResponse[]>([])
  const [chatSidebarCollapsed, setChatSidebarCollapsed] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const chatFileInputRef = useRef<HTMLInputElement>(null)

  const latestAssistantIntel = useMemo(
    () => [...messages].reverse().find((message) => message.role === "assistant" && (message.workflow || message.research || message.memoriesUsed?.length || message.contributions?.length)),
    [messages],
  )

  const filteredConversations = useMemo(() => {
    const query = searchQuery.toLowerCase().trim()
    if (!query) return conversations
    return conversations.filter((conversation) => conversation.title.toLowerCase().includes(query) || messages.some((message) => message.content.toLowerCase().includes(query)))
  }, [conversations, messages, searchQuery])

  const filteredSavedResponses = useMemo(() => {
    const query = searchQuery.toLowerCase().trim()
    if (!query) return savedResponses
    return savedResponses.filter((item) => `${item.title} ${item.content}`.toLowerCase().includes(query))
  }, [savedResponses, searchQuery])

  const loadMessages = useCallback(async (conversationId: string) => {
    const records = await chatApi.listMessages(conversationId)
    setMessages(
      records.map((message) => ({
        id: message.id,
        role: message.role,
        content: message.content,
        timestamp: formatTime(message.created_at),
        ...richMessageFields(message),
      })),
    )
  }, [])

  const loadConversations = useCallback(async (preferredConversationId?: string | null) => {
    const records = await chatApi.listConversations(showArchivedChats)
    setConversations(records)
    const selected = records.find((item) => item.id === preferredConversationId) ?? records[0]
    if (selected) {
      setActiveConversationId(selected.id)
      window.localStorage.setItem(ACTIVE_CONVERSATION_KEY, selected.id)
      await loadMessages(selected.id)
    } else {
      setActiveConversationId(null)
      setMessages([])
      window.localStorage.removeItem(ACTIVE_CONVERSATION_KEY)
    }
  }, [loadMessages, showArchivedChats])

  const refreshConversationList = useCallback(async () => {
    const records = await chatApi.listConversations(showArchivedChats)
    setConversations(records)
  }, [showArchivedChats])

  useEffect(() => {
    const boot = async () => {
      setIsBooting(true)
      try {
        await loadConversations(window.localStorage.getItem(ACTIVE_CONVERSATION_KEY))
        const seed = window.localStorage.getItem("ceaser_chat_seed")
        if (seed) {
          setInput(seed)
          window.localStorage.removeItem("ceaser_chat_seed")
        }
      } finally {
        setIsBooting(false)
      }
    }
    void boot()
  }, [loadConversations])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
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
    if (!showSavedResponses) void loadConversations(showArchivedChats ? null : window.localStorage.getItem(ACTIVE_CONVERSATION_KEY))
  }, [showArchivedChats, showSavedResponses, loadConversations])

  const handleNewChat = async () => {
    if (showArchivedChats) setShowArchivedChats(false)
    if (showSavedResponses) setShowSavedResponses(false)
    const conversation = await chatApi.createConversation()
    setConversations((current) => [conversation, ...current])
    setActiveConversationId(conversation.id)
    window.localStorage.setItem(ACTIVE_CONVERSATION_KEY, conversation.id)
    setMessages([])
  }

  const handleSelectConversation = async (conversationId: string) => {
    setShowSavedResponses(false)
    setOpenConversationMenuId(null)
    setActiveConversationId(conversationId)
    window.localStorage.setItem(ACTIVE_CONVERSATION_KEY, conversationId)
    await loadMessages(conversationId)
  }

  const handleSelectSavedResponse = (response: SavedResponse) => {
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
    const updated = await chatApi.updateConversation(conversation.id, { pinned: !conversation.pinned })
    setConversations((current) => current.map((item) => (item.id === updated.id ? updated : item)).sort((a, b) => Number(b.pinned) - Number(a.pinned)))
    setOpenConversationMenuId(null)
  }

  const handleArchiveConversation = async (conversation: ConversationRecord) => {
    await chatApi.updateConversation(conversation.id, { archived: true })
    const remaining = conversations.filter((item) => item.id !== conversation.id)
    setConversations(remaining)
    setOpenConversationMenuId(null)
    if (activeConversationId === conversation.id) {
      const next = remaining[0]
      setActiveConversationId(next?.id ?? null)
      if (next) {
        window.localStorage.setItem(ACTIVE_CONVERSATION_KEY, next.id)
        await loadMessages(next.id)
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
    if (activeConversationId === conversation.id) {
      const next = remaining[0]
      setActiveConversationId(next?.id ?? null)
      if (next) {
        window.localStorage.setItem(ACTIVE_CONVERSATION_KEY, next.id)
        await loadMessages(next.id)
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
    if (activeConversationId === conversation.id) {
      const next = remaining[0]
      setActiveConversationId(next?.id ?? null)
      if (next) {
        window.localStorage.setItem(ACTIVE_CONVERSATION_KEY, next.id)
        await loadMessages(next.id)
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

  const handleSend = async () => {
    if (!input.trim() || isLoading) return
    const content = input.trim()
    const documentRequest = detectDocumentRequest(content)
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
      timestamp: "",
      isTyping: true,
    }
    setMessages((current) => [...current, userMessage, typingMessage])

    try {
      const conversationId = await ensureConversation()
      const fileIds = attachedFiles.map((file) => file.id)
      let response: CeaserChatResponse | null = null
      try {
        let streamedContent = ""
        let streamError: string | null = null
        await chatApi.sendCeaserMessageStream(content, conversationId, fileIds, {
          onToken: (text) => {
            streamedContent += text
            setMessages((current) =>
              current.map((message) =>
                message.id === typingMessage.id
                  ? { ...message, content: streamedContent, timestamp: formatTime(), isTyping: false }
                  : message,
              ),
            )
          },
          onComplete: (streamedResponse) => {
            response = streamedResponse
          },
          onError: (message) => {
            streamError = message
          },
        })
        if (streamError) throw new Error(streamError)
      } catch {
        response = await chatApi.sendCeaserMessage(content, conversationId, fileIds)
      }
      if (!response) throw new Error("We couldn't complete your request. Please try again.")
      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: response.response,
        timestamp: formatTime(),
        agentIds: response.selected_agents.map(agentNameToId),
        memoriesUsed: response.memories_used,
        contributions: response.contributions,
        contributionSummary: response.contribution_summary,
        research: response.research,
        workflow: response.workflow,
        highlights: [
          `Scope: ${response.scope}`,
          `Selected Agents: ${response.selected_agents.join(", ") || "None"}`,
          response.workflow ? `Workflow: ${response.workflow.type}` : null,
          `Memories Used: ${response.memories_used.length}`,
          `Sources: ${response.research?.sources.length ?? 0}`,
        ].filter(Boolean) as string[],
      }
      setMessages((current) => current.filter((message) => !message.isTyping).concat(assistantMessage))
      if (documentRequest) {
        const generated = await documentsApi.create({
          kind: documentRequest.kind,
          prompt: content,
          agent_id: documentRequest.agentId,
        })
        const generatedContent = documentCreatedMessage(documentRequest, generated.document.file_name)
        const generatedRecord = await chatApi.sendMessage(conversationId, generatedContent, "assistant", {
          generated_document: generated.document,
          generated_file: generated.file,
          preview: generated.preview,
        })
        const generatedMessage: Message = {
          id: generatedRecord.id,
          role: "assistant",
          content: generatedRecord.content,
          timestamp: formatTime(generatedRecord.created_at),
          ...richMessageFields(generatedRecord),
        }
        setMessages((current) => current.concat(generatedMessage))
      }
      setAttachedFiles([])
      await refreshConversationList()
      window.dispatchEvent(new Event("ceaser:activity-updated"))
    } catch (error) {
      const assistantMessage: Message = {
        id: `error-${Date.now()}`,
        role: "assistant",
        content: error instanceof Error ? error.message : "CEASER chat failed to connect.",
        timestamp: formatTime(),
      }
      setMessages((current) => current.filter((message) => !message.isTyping).concat(assistantMessage))
    } finally {
      setIsLoading(false)
    }
  }

  const handleVoiceResponse = async (response: VoiceRespondResponse) => {
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
      content: response.chat.response,
      timestamp: formatTime(),
      agentIds: response.chat.selected_agents.map(agentNameToId),
      memoriesUsed: response.chat.memories_used,
      contributions: response.chat.contributions,
      contributionSummary: response.chat.contribution_summary,
      research: response.chat.research,
      workflow: response.chat.workflow,
      highlights: [
        `Scope: ${response.chat.scope}`,
        `Selected Agents: ${response.chat.selected_agents.join(", ") || "None"}`,
        response.chat.workflow ? `Workflow: ${response.chat.workflow.type}` : null,
        `Memories Used: ${response.chat.memories_used.length}`,
        `Sources: ${response.chat.research?.sources.length ?? 0}`,
      ].filter(Boolean) as string[],
    }
    setMessages((current) => [...current, userMessage, assistantMessage])
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

  return (
    <div className="relative flex h-full overflow-hidden bg-[#050816] text-foreground">
      <div className="pointer-events-none absolute inset-0 opacity-[0.08] [background-image:linear-gradient(rgba(148,163,184,.18)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,.18)_1px,transparent_1px)] [background-size:36px_36px]" />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_18%_0%,rgba(124,58,237,0.12),transparent_34%),radial-gradient(circle_at_82%_100%,rgba(0,212,255,0.08),transparent_32%)]" />

      <aside
        className={cn(
          "relative z-20 flex h-full shrink-0 flex-col border-r border-border bg-card/72 backdrop-blur-xl transition-all duration-300",
          chatSidebarCollapsed ? "w-[76px]" : "w-[292px]",
        )}
      >
        <div className="flex h-16 items-center justify-between px-4">
          {!chatSidebarCollapsed && <p className="text-sm font-semibold tracking-wide text-foreground">Chats</p>}
          <button
            onClick={() => setChatSidebarCollapsed((value) => !value)}
            className="flex h-9 w-9 items-center justify-center rounded-full border border-border bg-secondary/45 text-muted-foreground transition hover:bg-secondary hover:text-foreground"
            aria-label={chatSidebarCollapsed ? "Expand chat sidebar" : "Collapse chat sidebar"}
          >
            <ChevronLeft className={cn("h-4 w-4 transition-transform", chatSidebarCollapsed && "rotate-180")} />
          </button>
        </div>

        <div className="px-3">
          <button
            onClick={() => void handleNewChat()}
            className={cn(
              "flex h-11 w-full items-center justify-center gap-2 rounded-2xl bg-cyan-400 text-sm font-semibold text-black transition hover:bg-cyan-300",
              chatSidebarCollapsed && "rounded-full px-0",
            )}
          >
            <Plus className="h-4 w-4" />
            {!chatSidebarCollapsed && <span>New Chat</span>}
          </button>
        </div>

        {!chatSidebarCollapsed && (
          <>
            <div className="mt-4 px-3">
              <div className="flex h-10 items-center gap-2 rounded-2xl border border-border bg-secondary/35 px-3">
                <Search className="h-4 w-4 text-muted-foreground" />
                <input
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder="Search conversations..."
                  className="w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                />
              </div>
            </div>

            <div className="mt-3 grid grid-cols-3 gap-2 px-3">
              <button
                onClick={() => {
                  setShowSavedResponses(false)
                  setShowArchivedChats(false)
                }}
                className={cn("rounded-xl px-3 py-2 text-xs font-medium transition", !showArchivedChats && !showSavedResponses ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-secondary/70 hover:text-foreground")}
              >
                Active
              </button>
              <button
                onClick={() => {
                  setShowSavedResponses(false)
                  setShowArchivedChats(true)
                }}
                className={cn("rounded-xl px-3 py-2 text-xs font-medium transition", showArchivedChats && !showSavedResponses ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-secondary/70 hover:text-foreground")}
              >
                Archived
              </button>
              <button
                onClick={() => {
                  setShowArchivedChats(false)
                  setShowSavedResponses(true)
                }}
                className={cn("rounded-xl px-3 py-2 text-xs font-medium transition", showSavedResponses ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-secondary/70 hover:text-foreground")}
              >
                Saved
              </button>
            </div>
          </>
        )}

        <div className={cn("mt-4 flex-1 overflow-y-auto", chatSidebarCollapsed ? "px-2" : "px-3")}>
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
                    "w-full rounded-2xl border px-3 py-3 text-left transition",
                    messages.length === 1 && messages[0]?.id === response.id
                      ? "border-primary bg-primary/12 text-foreground shadow-[0_12px_32px_rgba(79,140,255,0.14)]"
                      : "border-transparent text-muted-foreground hover:border-border hover:bg-secondary/45 hover:text-foreground",
                  )}
                >
                  <p className="truncate text-sm font-semibold">{response.title}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{formatTime(response.createdAt)}</p>
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
                      "w-full rounded-2xl border px-3 py-3 text-left transition",
                      activeConversationId === conversation.id ? "border-primary bg-primary/12 text-foreground shadow-[0_12px_32px_rgba(79,140,255,0.14)]" : "border-transparent text-muted-foreground hover:border-border hover:bg-secondary/45 hover:text-foreground",
                    )}
                  >
                    <div className="flex items-start gap-2">
                      {conversation.pinned && <Pin className="mt-0.5 h-3.5 w-3.5 text-cyan-300" />}
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium">{conversation.title}</p>
                        <p className="mt-1 text-xs text-muted-foreground">{formatTime(conversation.created_at)}</p>
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
        <section className="flex min-h-0 w-full flex-1 flex-col px-8 pb-6">
          <div className={cn("min-h-0 flex-1 overflow-y-auto pr-3", messages.length || isBooting ? "pt-10" : "pt-[17vh]")}>
            {!messages.length && !isBooting ? (
              <>
                <h1 className="text-left text-[38px] font-light leading-[1.08] tracking-[-0.03em] text-white md:text-[44px]">
                  Hey! Akshay
                  <br />
                  <span className="text-white/82">What can I help with?</span>
                </h1>

                <div className="mt-7 grid gap-4 md:grid-cols-3">
                  <PromptCard color="cyan" title="Content Help" text="Help with me create a Presentation" onClick={() => setInput("Help me create a presentation about ")} />
                  <PromptCard color="rose" title="Suggestions" text="Help with me ideas" onClick={() => setInput("Give me suggestions for ")} />
                  <PromptCard color="green" title="Job Application" text="Help with me apply for job application" onClick={() => setInput("Help me prepare a job application for ")} />
                </div>

                <div className="mt-7">
                  <p className="mb-3 text-xs font-medium uppercase tracking-[0.18em] text-white/38">Quick Actions</p>
                  <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {creationActions.map((action) => (
                      <button
                        key={action.title}
                        onClick={() => setInput(action.prompt)}
                        className="rounded-2xl bg-white/[0.035] px-4 py-3 text-left transition hover:bg-white/[0.07]"
                      >
                        <p className="text-sm font-medium text-white">{action.title}</p>
                        <p className="mt-1 text-xs text-white/42">{action.subtitle}</p>
                      </button>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <div className="mx-auto w-full max-w-[1180px] space-y-7">
                {isBooting ? (
                  <div className="flex items-center justify-center gap-2 py-12 text-sm text-white/55">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading conversation...
                  </div>
                ) : (
                  messages.map((message) => <ChatBubble key={message.id} message={message} />)
                )}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          <div className="pt-4">
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

            <div className="mx-auto flex min-h-[60px] w-full max-w-[1180px] items-center gap-3 rounded-full bg-white/[0.045] px-4 backdrop-blur-2xl">
              <input
                ref={chatFileInputRef}
                type="file"
                className="hidden"
                accept=".pdf,.docx,.pptx,.xlsx,.txt,.png,.jpg,.jpeg"
                onChange={(event) => void handleChatFileUpload(event)}
              />
              <button
                onClick={() => chatFileInputRef.current?.click()}
                disabled={isUploadingFile}
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white/[0.05] text-white/65 transition hover:bg-white/10 hover:text-white disabled:opacity-50"
              >
                {isUploadingFile ? <Loader2 className="h-4 w-4 animate-spin" /> : <Paperclip className="h-4 w-4" />}
              </button>
              <input
                type="text"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => event.key === "Enter" && handleSend()}
                placeholder="Tell me what do you want?"
                disabled={isLoading}
                className="h-12 min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-white/45 disabled:opacity-50"
              />
              <VoiceControls conversationId={activeConversationId} disabled={isLoading} onResponse={(response) => void handleVoiceResponse(response)} />
              <button
                onClick={handleSend}
                disabled={!input.trim() || isLoading}
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-emerald-500 text-white shadow-[0_0_28px_rgba(16,185,129,0.26)] transition hover:bg-emerald-400 disabled:opacity-50"
              >
                {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </button>
            </div>
          </div>
        </section>
      </main>
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

function ChatBubble({ message }: { message: Message }) {
  return (
    <div className={cn("flex w-full gap-3", message.role === "user" ? "justify-end" : "justify-start")}>
      {message.role === "assistant" && (
        <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-emerald-500/15 text-xs font-semibold text-emerald-200">
          C
        </div>
      )}
      <div className={cn(message.role === "user" ? "max-w-[78%] text-right text-white" : "min-w-0 flex-1 text-white")}>
        <div className={cn("mb-2 flex items-center gap-2 text-xs", message.role === "user" ? "justify-end text-white/42" : "text-white/48")}>
          <span>{message.role === "user" ? "You" : "Ceaser"}</span>
        </div>
        {message.isTyping ? (
          <div className="flex items-center gap-2 text-white/55">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span className="text-sm">Thinking...</span>
          </div>
        ) : (
          <>
            <MarkdownMessage content={message.content} isUser={message.role === "user"} />
            {message.role === "assistant" && <InlineSourceStrip message={message} />}
            {message.role === "assistant" && <ResponseActions message={message} />}
            <p className={cn("mt-2 text-xs", message.role === "user" ? "text-white/60" : "text-white/38")}>{message.timestamp}</p>
          </>
        )}
      </div>
      {message.role === "user" && (
        <div className="mt-1 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-[#0b3f4a] text-xs font-semibold text-cyan-100">
          A
        </div>
      )}
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

function ResponseActions({ message }: { message: Message }) {
  const [copied, setCopied] = useState(false)
  const [feedback, setFeedback] = useState<"like" | "dislike" | null>(null)
  const [saved, setSaved] = useState(false)
  const content = message.content.trim()
  const contextualActions = useMemo(() => getContextualActions(content), [content])

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

  const universal: ResponseAction[] = [
    { id: "copy", label: copied ? "Copied" : "Copy", icon: copied ? Check : Copy, run: copyText },
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
    <div className="mt-4 flex flex-wrap gap-2">
      {actions.map((action) => {
        const Icon = action.icon
        const active = (action.id === "like" && feedback === "like") || (action.id === "dislike" && feedback === "dislike") || (action.id === "save" && saved)
        return (
          <button
            key={action.id}
            onClick={() => void action.run()}
            className={cn(
              "inline-flex h-8 items-center gap-2 rounded-full bg-white/[0.045] px-3 text-xs text-white/58 transition hover:bg-white/[0.08] hover:text-white",
              active && "bg-cyan-400/12 text-cyan-200",
            )}
          >
            <Icon className="h-3.5 w-3.5" />
            {action.label}
          </button>
        )
      })}
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

function MarkdownMessage({ content, isUser }: { content: string; isUser: boolean }) {
  if (isUser) return <p className="whitespace-pre-wrap text-sm">{content}</p>
  const structured = parseAnswerSections(content)
  if (structured) return <StructuredAnswer data={structured} />

  const lines = content.split("\n")
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

  return <div className="space-y-1">{elements}</div>
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

function InlineSourceStrip({ message }: { message: Message }) {
  if (!message.research?.sources.length) return null
  return (
    <div className="mt-5">
      <p className="text-xs font-medium text-white/45">Sources ({message.research.sources.length})</p>
      <div className="mt-2 space-y-1.5">
        {message.research.sources.slice(0, 5).map((source, index) => (
          <a key={source.url} href={source.url} target="_blank" rel="noreferrer" className="block text-xs text-white/62 transition hover:text-cyan-200">
            <span className="text-white/38">[{index + 1}]</span> {source.title}
            <span className="text-white/35"> - {source.source}</span>
          </a>
        ))}
      </div>
    </div>
  )
}

function ResearchSidePanel({ message }: { message?: Message }) {
  const sources = message?.research?.sources ?? []
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

      <section className="rounded-3xl border border-white/10 bg-[#111827]/72 p-4 shadow-[0_22px_65px_rgba(0,0,0,0.22)]">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Sources ({sources.length})</h2>
          <span className="text-xs text-muted-foreground">View all</span>
        </div>
        <div className="space-y-3">
          {sources.length ? sources.slice(0, 6).map((source, index) => (
            <a key={source.url} href={source.url} target="_blank" rel="noreferrer" className="flex gap-2 rounded-xl p-1.5 transition hover:bg-white/5">
              <span className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded bg-primary/20 text-xs font-semibold text-primary">{index + 1}</span>
              <span className="min-w-0">
                <span className="block truncate text-[11px] text-muted-foreground">{source.source}</span>
                <span className="line-clamp-2 text-xs font-medium">{source.title}</span>
              </span>
            </a>
          )) : (
            <p className="text-sm text-muted-foreground">Sources appear here after a research response.</p>
          )}
        </div>
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
