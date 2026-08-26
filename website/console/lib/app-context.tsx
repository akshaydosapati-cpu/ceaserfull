"use client"

import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react"
import type { AppPage } from "@/lib/ceaser"
import { ENABLE_STUDENT_HUB } from "@/lib/ceaser"

type DialogTone = "default" | "danger"
type AppTheme = "dark"
type PendingChatRequest = { id: string; prompt: string }
type DialogRequest =
  | {
      type: "confirm"
      title: string
      description?: string
      confirmLabel?: string
      cancelLabel?: string
      tone?: DialogTone
    }
  | {
      type: "prompt"
      title: string
      description?: string
      defaultValue?: string
      confirmLabel?: string
      cancelLabel?: string
      tone?: DialogTone
    }

interface AppState {
  currentPage: AppPage
  setCurrentPage: (page: AppPage) => void
  selectedAgentId: string | null
  setSelectedAgentId: (id: string | null) => void
  isVoiceModalOpen: boolean
  setIsVoiceModalOpen: (open: boolean) => void
  isSearchOpen: boolean
  setIsSearchOpen: (open: boolean) => void
  isAgentConfigOpen: boolean
  setIsAgentConfigOpen: (open: boolean) => void
  configAgentId: string | null
  setConfigAgentId: (id: string | null) => void
  sidebarCollapsed: boolean
  setSidebarCollapsed: (collapsed: boolean) => void
  theme: AppTheme
  setTheme: (theme: AppTheme) => void
  pendingChatRequest: PendingChatRequest | null
  startNewChatWithPrompt: (prompt: string) => void
  clearPendingChatRequest: () => void
  confirmDialog: (request: Omit<Extract<DialogRequest, { type: "confirm" }>, "type">) => Promise<boolean>
  promptDialog: (request: Omit<Extract<DialogRequest, { type: "prompt" }>, "type">) => Promise<string | null>
}

const AppContext = createContext<AppState | undefined>(undefined)

export function AppProvider({ children }: { children: ReactNode }) {
  const [currentPage, setCurrentPage] = useState<AppPage>("chat")
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null)
  const [isVoiceModalOpen, setIsVoiceModalOpen] = useState(false)
  const [isSearchOpen, setIsSearchOpen] = useState(false)
  const [isAgentConfigOpen, setIsAgentConfigOpen] = useState(false)
  const [configAgentId, setConfigAgentId] = useState<string | null>(null)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(true)
  const [theme, setThemeState] = useState<AppTheme>("dark")
  const [pendingChatRequest, setPendingChatRequest] = useState<PendingChatRequest | null>(null)
  const [dialog, setDialog] = useState<DialogRequest | null>(null)
  const [promptValue, setPromptValue] = useState("")
  const dialogResolver = useRef<((value: boolean | string | null) => void) | null>(null)

  const closeDialog = (value: boolean | string | null) => {
    dialogResolver.current?.(value)
    dialogResolver.current = null
    setDialog(null)
    setPromptValue("")
  }

  const confirmDialog: AppState["confirmDialog"] = (request) =>
    new Promise((resolve) => {
      dialogResolver.current = (value) => resolve(Boolean(value))
      setDialog({ ...request, type: "confirm" })
    })

  const promptDialog: AppState["promptDialog"] = (request) =>
    new Promise((resolve) => {
      dialogResolver.current = (value) => resolve(typeof value === "string" ? value : null)
      setPromptValue(request.defaultValue ?? "")
      setDialog({ ...request, type: "prompt" })
    })

  useEffect(() => {
    // CEASER is dark-mode only. The light class is always removed and dark is always applied.
    document.documentElement.classList.remove("light")
    document.documentElement.classList.add("dark")
    document.documentElement.dataset.theme = "dark"
    window.localStorage.setItem("ceaser_theme", "dark")
    const params = new URLSearchParams(window.location.search)
    const view = params.get("view") || window.localStorage.getItem("ceaser_current_page")
    if (view) setCurrentPage(
      view === "mission-control" || (view === "student" && !ENABLE_STUDENT_HUB)
        ? "chat"
        : (view as AppPage),
    )
  }, [])

  const setPage = (page: AppPage) => {
    const nextPage = page === "mission-control" || (page === "student" && !ENABLE_STUDENT_HUB) ? "chat" : page
    setCurrentPage(nextPage)
    if (typeof window === "undefined") return
    window.localStorage.setItem("ceaser_current_page", nextPage)
    const url = new URL(window.location.href)
    url.searchParams.set("view", nextPage)
    window.history.replaceState({}, "", url)
  }

  const setTheme = (_nextTheme: AppTheme) => setThemeState("dark")
  const startNewChatWithPrompt = (prompt: string) => {
    const trimmedPrompt = prompt.trim()
    if (!trimmedPrompt) return
    setPendingChatRequest({ id: `${Date.now()}-${Math.random().toString(36).slice(2)}`, prompt: trimmedPrompt })
  }
  const clearPendingChatRequest = () => setPendingChatRequest(null)

  return (
    <AppContext.Provider
      value={{
        currentPage,
        setCurrentPage: setPage,
        selectedAgentId,
        setSelectedAgentId,
        isVoiceModalOpen,
        setIsVoiceModalOpen,
        isSearchOpen,
        setIsSearchOpen,
        isAgentConfigOpen,
        setIsAgentConfigOpen,
        configAgentId,
        setConfigAgentId,
        sidebarCollapsed,
        setSidebarCollapsed,
        theme,
        setTheme,
        pendingChatRequest,
        startNewChatWithPrompt,
        clearPendingChatRequest,
        confirmDialog,
        promptDialog,
      }}
    >
      {children}
      {dialog && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
          <section className="w-full max-w-md rounded-3xl border border-white/10 bg-[#0B1224] p-5 shadow-[0_30px_100px_rgba(0,0,0,0.48)]">
            <div className="mb-4">
              <p className="text-xs font-medium uppercase tracking-[0.2em] text-primary">CEASER Confirmation</p>
              <h2 className="mt-2 text-lg font-semibold text-foreground">{dialog.title}</h2>
              {dialog.description && <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{dialog.description}</p>}
            </div>
            {dialog.type === "prompt" && (
              <input
                value={promptValue}
                onChange={(event) => setPromptValue(event.target.value)}
                autoFocus
                className="mb-5 h-11 w-full rounded-2xl border border-white/10 bg-white/5 px-4 text-sm outline-none ring-primary/30 transition focus:ring-2"
              />
            )}
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => closeDialog(dialog.type === "confirm" ? false : null)}
                className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-muted-foreground transition hover:bg-white/10 hover:text-foreground"
              >
                {dialog.cancelLabel ?? "Cancel"}
              </button>
              <button
                type="button"
                onClick={() => closeDialog(dialog.type === "confirm" ? true : promptValue.trim())}
                className={[
                  "rounded-xl px-4 py-2 text-sm font-semibold text-white transition",
                  dialog.tone === "danger" ? "bg-red-500 hover:bg-red-400" : "bg-primary hover:bg-primary/90",
                ].join(" ")}
              >
                {dialog.confirmLabel ?? "Confirm"}
              </button>
            </div>
          </section>
        </div>
      )}
    </AppContext.Provider>
  )
}

export function useApp() {
  const context = useContext(AppContext)
  if (context === undefined) {
    throw new Error("useApp must be used within an AppProvider")
  }
  return context
}
