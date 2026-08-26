"use client"

import { useEffect, useMemo, useState } from "react"
import { useApp } from "@/lib/app-context"
import { getPageTitle } from "@/lib/ceaser"
import { getUserDisplayName, getUserDisplayRole, readUserProfile } from "@/lib/user-profile"
import { authApi } from "@/lib/api/auth"
import { chatApi, type ConversationRecord } from "@/lib/api/chat"
import { memoryApi, type MemoryRecord } from "@/lib/api/memory"
import {
  Search,
  Bell,
  ChevronDown,
  Command,
  LogOut
} from "lucide-react"

const PROFILE_KEY = "ceaser_user_profile"
const READ_NOTIFICATIONS_KEY = "ceaser_read_notifications"

export function Header() {
  const { setIsSearchOpen, currentPage, setCurrentPage, confirmDialog } = useApp()
  const pageTitle = getPageTitle(currentPage)
  const [profile, setProfile] = useState<{ name?: string; useCase?: string; email?: string } | null>(readUserProfile())
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false)
  const [isProfileOpen, setIsProfileOpen] = useState(false)
  const [memories, setMemories] = useState<MemoryRecord[]>([])
  const [conversations, setConversations] = useState<ConversationRecord[]>([])
  const [readNotificationIds, setReadNotificationIds] = useState<string[]>([])

  useEffect(() => {
    try {
      setProfile(readUserProfile())
      setReadNotificationIds(JSON.parse(window.localStorage.getItem(READ_NOTIFICATIONS_KEY) || "[]"))
    } catch {
      setProfile(null)
      setReadNotificationIds([])
    }
  }, [])

  useEffect(() => {
    let mounted = true
    async function loadHeaderData() {
      const [memoryResult, conversationResult] = await Promise.allSettled([
        memoryApi.list(),
        chatApi.listConversations(false),
      ])
      if (!mounted) return
      if (memoryResult.status === "fulfilled") setMemories(memoryResult.value)
      if (conversationResult.status === "fulfilled") setConversations(conversationResult.value)
    }
    void loadHeaderData()
    const refresh = () => {
      try {
        setProfile(readUserProfile())
      } catch {
        setProfile(null)
      }
      void loadHeaderData()
    }
    window.addEventListener("focus", refresh)
    window.addEventListener("ceaser:activity-updated", refresh)
    window.addEventListener("ceaser:saved-response", refresh)
    const timer = window.setInterval(refresh, 30000)
    return () => {
      mounted = false
      window.removeEventListener("focus", refresh)
      window.removeEventListener("ceaser:activity-updated", refresh)
      window.removeEventListener("ceaser:saved-response", refresh)
      window.clearInterval(timer)
    }
  }, [])

  const displayName = getUserDisplayName(profile)
  const displayRole = getUserDisplayRole(profile)
  const notificationItems = useMemo(() => {
    return [
      memories[0]
        ? {
            id: `memory-${memories[0].id}`,
            title: "Latest memory saved",
            detail: getMemoryTitle(memories[0]),
            page: "memory" as const,
          }
        : null,
      conversations[0]
        ? {
            id: `chat-${conversations[0].id}`,
            title: "Recent chat",
            detail: conversations[0].title,
            page: "chat" as const,
          }
        : null,
    ].filter(Boolean) as Array<{ id: string; title: string; detail: string; page: "memory" | "chat" }>
  }, [conversations, memories])
  const notificationCount = notificationItems.filter((item) => !readNotificationIds.includes(item.id)).length

  function markNotificationsRead() {
    const ids = notificationItems.map((item) => item.id)
    if (!ids.length) return
    setReadNotificationIds((current) => {
      const next = Array.from(new Set([...current, ...ids])).slice(-50)
      window.localStorage.setItem(READ_NOTIFICATIONS_KEY, JSON.stringify(next))
      return next
    })
  }

  async function signOut() {
    const confirmed = await confirmDialog({
      title: "Sign out of CEASER?",
      description: "You can sign back in anytime. This device will return to the welcome screen.",
      confirmLabel: "Sign out",
    })
    if (!confirmed) return
    try {
      await authApi.signOut()
    } catch {
      // Local sign out still keeps the product usable when the backend is unavailable.
    }
    window.location.reload()
  }

  return (
    <header className="relative z-30 m-3 mb-0 flex h-14 min-w-0 items-center justify-between gap-4 rounded-lg border border-border bg-card/72 px-5 backdrop-blur-md">
      <div className="flex min-w-0 flex-1 items-center gap-4">
        <span className="hidden shrink-0 text-sm font-medium text-muted-foreground md:inline">{pageTitle}</span>
        <span className="rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">Unified AI OS</span>
      </div>

      <div className="flex shrink-0 items-center gap-3">
        {/* Search */}
        <button
          onClick={() => setIsSearchOpen(true)}
          className="hidden items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-muted-foreground transition-colors hover:bg-white/10 hover:text-foreground lg:flex"
        >
          <Search className="h-4 w-4" />
          <span>Search anything...</span>
          <kbd className="ml-4 flex items-center gap-0.5 rounded border border-border bg-background px-1.5 py-0.5 text-xs">
            <Command className="h-3 w-3" />
            <span>K</span>
          </kbd>
        </button>

        {/* Notifications */}
        <div className="relative">
          <button
            onClick={() => {
              setIsNotificationsOpen((open) => {
                if (!open) markNotificationsRead()
                return !open
              })
              setIsProfileOpen(false)
            }}
            className="relative flex h-10 w-10 items-center justify-center rounded-xl text-muted-foreground transition-colors hover:bg-white/10 hover:text-foreground"
            title="Notifications"
          >
            <Bell className="h-5 w-5" />
            {notificationCount > 0 && (
              <span className="absolute right-1.5 top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-medium text-white">
                {notificationCount}
              </span>
            )}
          </button>
          {isNotificationsOpen && (
            <div className="absolute right-0 top-12 z-50 w-80 rounded-2xl border border-border bg-card p-2 shadow-2xl">
              <div className="px-3 py-2">
                <p className="text-sm font-semibold">Notifications</p>
                <p className="text-xs text-muted-foreground">Live CEASER activity</p>
              </div>
              <div className="space-y-1">
                {notificationItems.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => {
                      markNotificationsRead()
                      setCurrentPage(item.page)
                      setIsNotificationsOpen(false)
                    }}
                    className="w-full rounded-xl px-3 py-2 text-left transition hover:bg-white/10"
                  >
                    <p className="text-sm font-medium">{item.title}</p>
                    <p className="line-clamp-1 text-xs text-muted-foreground">{item.detail}</p>
                  </button>
                ))}
                {!notificationItems.length && (
                  <p className="rounded-xl px-3 py-4 text-sm text-muted-foreground">No new activity yet.</p>
                )}
              </div>
            </div>
          )}
        </div>

        {/* User Avatar */}
        <div className="relative">
          <button
            onClick={() => {
              setIsProfileOpen((open) => !open)
              setIsNotificationsOpen(false)
            }}
            className="flex items-center gap-3 rounded-xl px-2 py-1.5 transition-colors hover:bg-white/10"
          >
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-primary/30 to-primary/10 text-sm font-semibold text-primary">
              {displayName.charAt(0)}
            </div>
            <div className="text-left">
              <p className="text-sm font-medium">{displayName}</p>
              <p className="text-xs text-muted-foreground">{displayRole}</p>
            </div>
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          </button>
          {isProfileOpen && (
            <div className="absolute right-0 top-12 z-50 w-64 rounded-2xl border border-border bg-card p-2 shadow-2xl">
              <div className="border-b border-border px-3 py-3">
                <p className="text-sm font-semibold">{displayName}</p>
                <p className="line-clamp-1 text-xs text-muted-foreground">{profile?.email || "CEASER account"}</p>
              </div>
              <button
                onClick={() => {
                  setCurrentPage("settings")
                  setIsProfileOpen(false)
                }}
                className="mt-2 w-full rounded-xl px-3 py-2 text-left text-sm transition hover:bg-white/10"
              >
                Settings
              </button>
              <button
                onClick={() => void signOut()}
                className="w-full rounded-xl px-3 py-2 text-left text-sm text-red-300 transition hover:bg-red-500/10"
              >
                Sign out
              </button>
            </div>
          )}
        </div>
        <button onClick={() => void signOut()} className="flex h-10 w-10 items-center justify-center rounded-xl text-muted-foreground transition-colors hover:bg-white/10 hover:text-primary" title="Sign out">
          <LogOut className="h-4 w-4" />
        </button>
      </div>
    </header>
  )
}

function getMemoryTitle(memory: MemoryRecord) {
  const metadata = (memory.metadata ?? memory.extra_metadata ?? {}) as { title?: string }
  return metadata.title || memory.content.split("\n")[0]?.replace(/^#+\s*/, "").slice(0, 80) || "Memory"
}


