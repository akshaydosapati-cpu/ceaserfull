"use client"

import Image from "next/image"
import { useEffect, useMemo, useRef, useState, type ElementType, type ReactNode } from "react"
import { Archive, ChevronDown, Edit3, FileInput, FileText, Folder, FolderKanban, LockKeyhole, MessageSquarePlus, MoreHorizontal, Pin, PinOff, Puzzle, Search, Settings, ShieldCheck, Sparkles, Trash2, X } from "lucide-react"
import darkWordmark from "@/public/ceaser-wordmark-dark-transparent.png"
import { useApp } from "@/lib/app-context"
import { chatApi, type ConversationRecord } from "@/lib/api/chat"
import { projectsApi, type ProjectRecord } from "@/lib/api/projects"
import { getUserDisplayName, getUserDisplayRole, readUserProfile } from "@/lib/user-profile"
import { cn } from "@/lib/utils"
import { recordStartupMetric } from "@/lib/api/client"
import { adminApi } from "@/lib/api/admin"

export function Sidebar() {
  const { currentPage, setCurrentPage, confirmDialog, promptDialog, guestDemo, sidebarCollapsed, setSidebarCollapsed } = useApp()
  const [projects, setProjects] = useState<ProjectRecord[]>([])
  const [chats, setChats] = useState<ConversationRecord[]>([])
  const [query, setQuery] = useState("")
  const [showMore, setShowMore] = useState(false)
  const [openChatMenuId, setOpenChatMenuId] = useState<string | null>(null)
  const [moveChatId, setMoveChatId] = useState<string | null>(null)
  const [chatActionError, setChatActionError] = useState("")
  const sidebarRef = useRef<HTMLElement>(null)
  const [profile, setProfile] = useState(readUserProfile())
  const [isAdmin, setIsAdmin] = useState(false)

  useEffect(() => {
    if (guestDemo) {
      recordStartupMetric("secondary_data_ready", { projects: 0, conversations: 0, guest_demo: true })
      return
    }
    let disposed = false
    void adminApi.me().then((admin) => { if (!disposed) setIsAdmin(admin.is_admin) }).catch(() => undefined)
    void Promise.allSettled([
      projectsApi.list().then((items) => { if (!disposed) setProjects(items); return items }),
      chatApi.listConversations(false).then((items) => { if (!disposed) setChats(items); return items }),
    ]).then(([projectResult, chatResult]) => {
      recordStartupMetric("secondary_data_ready", {
        projects: projectResult.status === "fulfilled" ? projectResult.value.length : 0,
        conversations: chatResult.status === "fulfilled" ? chatResult.value.length : 0,
      })
    })
    const refresh = () => setProfile(readUserProfile())
    window.addEventListener("ceaser:profile-updated", refresh)
    return () => { disposed = true; window.removeEventListener("ceaser:profile-updated", refresh) }
  }, [guestDemo])

  useEffect(() => {
    const closeMenu = (event: MouseEvent) => {
      if (sidebarRef.current && !sidebarRef.current.contains(event.target as Node)) setOpenChatMenuId(null)
    }
    document.addEventListener("mousedown", closeMenu)
    return () => document.removeEventListener("mousedown", closeMenu)
  }, [])

  useEffect(() => {
    const syncConversationChange = (event: Event) => {
      const detail = (event as CustomEvent<{ action?: string; conversationId?: string; conversation?: ConversationRecord; conversations?: ConversationRecord[] }>).detail || {}
      if (detail.action === "created" && detail.conversation) {
        setChats((current) => [detail.conversation as ConversationRecord, ...current.filter((item) => item.id !== detail.conversation?.id)])
      } else if (detail.action === "updated" && detail.conversation) {
        setChats((current) => current.map((item) => item.id === detail.conversation?.id ? detail.conversation as ConversationRecord : item).filter((item) => !item.archived))
      } else if (detail.action === "deleted" && detail.conversationId) {
        setChats((current) => current.filter((item) => item.id !== detail.conversationId))
      } else if (detail.action === "synced" && detail.conversations) {
        setChats(detail.conversations)
      } else if (detail.action === "reload") {
        void chatApi.listConversations(false).then(setChats).catch(() => undefined)
      }
    }
    window.addEventListener("ceaser:conversations-changed", syncConversationChange)
    return () => window.removeEventListener("ceaser:conversations-changed", syncConversationChange)
  }, [])

  const publishConversationChange = (detail: Record<string, unknown>) => {
    window.dispatchEvent(new CustomEvent("ceaser:conversations-changed", { detail }))
  }

  const updateChat = async (chat: ConversationRecord, updates: Partial<Pick<ConversationRecord, "title" | "pinned" | "archived" | "project_id">>) => {
    const previous = chats
    const optimistic = { ...chat, ...updates }
    setChats((current) => current.map((item) => item.id === chat.id ? optimistic : item).filter((item) => !item.archived))
    setOpenChatMenuId(null)
    setMoveChatId(null)
    setChatActionError("")
    publishConversationChange({ action: "updated", conversation: optimistic })
    try {
      const saved = await chatApi.updateConversation(chat.id, updates)
      setChats((current) => current.map((item) => item.id === saved.id ? saved : item).filter((item) => !item.archived))
      publishConversationChange({ action: "updated", conversation: saved })
    } catch (error) {
      setChats(previous)
      publishConversationChange({ action: "reload" })
      setChatActionError(error instanceof Error ? error.message : "Could not update this chat.")
    }
  }

  const renameChat = async (chat: ConversationRecord) => {
    const title = (await promptDialog({ title: "Rename chat", description: "Give this conversation a clear name.", defaultValue: chat.title, confirmLabel: "Rename" }))?.trim()
    if (title && title !== chat.title) await updateChat(chat, { title })
  }

  const deleteChat = async (chat: ConversationRecord) => {
    const confirmed = await confirmDialog({ title: `Delete "${chat.title}"?`, description: "This permanently removes the conversation and all of its messages.", confirmLabel: "Delete", tone: "danger" })
    if (!confirmed) return
    const previous = chats
    setChats((current) => current.filter((item) => item.id !== chat.id))
    setOpenChatMenuId(null)
    setChatActionError("")
    publishConversationChange({ action: "deleted", conversationId: chat.id })
    try {
      await chatApi.deleteConversation(chat.id)
    } catch (error) {
      setChats(previous)
      publishConversationChange({ action: "reload" })
      setChatActionError(error instanceof Error ? error.message : "Could not delete this chat.")
    }
  }

  const filteredProjects = useMemo(() => projects.filter((item) => item.name.toLowerCase().includes(query.toLowerCase())).slice(0, 7), [projects, query])
  const filteredChats = useMemo(() => chats.filter((item) => item.title.toLowerCase().includes(query.toLowerCase())), [chats, query])
  const openChat = (id?: string) => {
    if (id) window.localStorage.setItem("ceaser_active_conversation_id", id)
    else window.localStorage.removeItem("ceaser_active_conversation_id")
    setCurrentPage("chat")
    window.dispatchEvent(new CustomEvent(id ? "ceaser:open-conversation" : "ceaser:new-chat", { detail: { id } }))
    if (window.innerWidth < 768) setSidebarCollapsed(true)
  }

  const openPage = (page: "files" | "projects" | "integrations" | "admin" | "settings") => {
    setCurrentPage(page)
    if (window.innerWidth < 768) setSidebarCollapsed(true)
  }

  return <aside ref={sidebarRef} className={cn(
    "ceaser-global-sidebar fixed inset-y-0 left-0 z-50 flex h-[100dvh] w-[min(86vw,300px)] shrink-0 flex-col border-r border-white/[0.08] bg-[#050810] text-white shadow-2xl transition-transform duration-300 ease-out md:static md:h-full md:w-[260px] md:translate-x-0 md:shadow-none",
    guestDemo && "min-[520px]:static min-[520px]:h-full min-[520px]:w-[260px] min-[520px]:translate-x-0 min-[520px]:shadow-none",
    sidebarCollapsed ? "-translate-x-full" : "translate-x-0",
  )}>
    <button onClick={() => openChat()} className="flex h-[76px] items-center px-4 text-left hover:bg-white/[0.03]"><Image src={darkWordmark} alt="CEASER" width={170} height={42} className="h-9 w-auto object-contain" priority /></button>
    <div className="px-3 pb-2">
      <div className="mb-2 flex h-9 items-center gap-2 rounded-lg border border-white/10 bg-white/[0.025] px-3 focus-within:border-cyan-300/40 focus-within:bg-white/[0.04]">
        <Search className="h-3.5 w-3.5 shrink-0 text-white/45" />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search chats..."
          aria-label="Search chats"
          className="min-w-0 flex-1 bg-transparent text-xs outline-none placeholder:text-white/35"
        />
      </div>
      <NavButton icon={MessageSquarePlus} label="New chat" onClick={() => openChat()} />
      <NavButton icon={FileText} label="Library" locked={guestDemo} active={currentPage === "files"} onClick={() => openPage("files")} />
      <NavButton icon={FolderKanban} label="Projects" locked={guestDemo} active={currentPage === "projects"} onClick={() => openPage("projects")} />
      <NavButton icon={Puzzle} label="Plugins" locked={guestDemo} active={currentPage === "integrations"} onClick={() => openPage("integrations")} />
      {isAdmin && <NavButton icon={ShieldCheck} label="Admin" active={currentPage === "admin"} onClick={() => openPage("admin")} />}
      <NavButton icon={MoreHorizontal} label="More" locked={guestDemo} onClick={() => setShowMore((value) => !value)} />
      {showMore && !guestDemo && <div className="ml-3 border-l border-white/10 pl-2"><NavButton compact icon={Settings} label="Settings" onClick={() => openPage("settings")} /></div>}
    </div>
    <div className="mt-3 flex-1 overflow-y-auto px-3 pb-5 [scrollbar-width:thin]">
      {chatActionError && <p className="mb-2 rounded-lg border border-rose-400/20 bg-rose-400/10 px-2 py-2 text-[11px] text-rose-200">{chatActionError}</p>}
      <SidebarSection title="Pinned">{chats.filter((chat) => chat.pinned).slice(0, 3).map((chat) => <ChatSidebarRow key={chat.id} chat={chat} icon={Sparkles} active={currentPage === "chat" && window.localStorage.getItem("ceaser_active_conversation_id") === chat.id} menuOpen={openChatMenuId === chat.id} moving={moveChatId === chat.id} projects={projects} onOpen={() => openChat(chat.id)} onMenu={() => { setMoveChatId(null); setOpenChatMenuId(openChatMenuId === chat.id ? null : chat.id) }} onRename={() => void renameChat(chat)} onPin={() => void updateChat(chat, { pinned: !chat.pinned })} onMove={() => setMoveChatId(chat.id)} onMoveTo={(projectId) => void updateChat(chat, { project_id: projectId })} onArchive={() => void updateChat(chat, { archived: true })} onDelete={() => void deleteChat(chat)} />)}</SidebarSection>
      <SidebarSection title="Projects">{filteredProjects.map((project) => <SidebarRow key={project.id} icon={Folder} label={project.name} onClick={() => { window.localStorage.setItem("ceaser_selected_project_id", project.id); openPage("projects") }} />)}{!filteredProjects.length && <p className="px-2 py-2 text-xs text-white/35">No projects yet</p>}</SidebarSection>
      <SidebarSection title="Chats">{filteredChats.map((chat) => <ChatSidebarRow key={chat.id} chat={chat} active={currentPage === "chat" && window.localStorage.getItem("ceaser_active_conversation_id") === chat.id} menuOpen={openChatMenuId === chat.id} moving={moveChatId === chat.id} projects={projects} onOpen={() => openChat(chat.id)} onMenu={() => { setMoveChatId(null); setOpenChatMenuId(openChatMenuId === chat.id ? null : chat.id) }} onRename={() => void renameChat(chat)} onPin={() => void updateChat(chat, { pinned: !chat.pinned })} onMove={() => setMoveChatId(chat.id)} onMoveTo={(projectId) => void updateChat(chat, { project_id: projectId })} onArchive={() => void updateChat(chat, { archived: true })} onDelete={() => void deleteChat(chat)} />)}</SidebarSection>
    </div>
    <button disabled={guestDemo} onClick={() => openPage("settings")} className="m-3 flex items-center gap-3 rounded-xl border border-white/[0.08] p-2 text-left hover:bg-white/[0.05] disabled:cursor-not-allowed disabled:hover:bg-transparent"><span className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-cyan-500 to-violet-600 text-xs font-semibold">{guestDemo ? "G" : getUserDisplayName(profile).charAt(0)}</span><span className="min-w-0 flex-1"><span className="block truncate text-sm">{guestDemo ? "Guest" : getUserDisplayName(profile)}</span><span className="block truncate text-[11px] text-white/45">{guestDemo ? "Demo account" : getUserDisplayRole(profile)}</span></span>{guestDemo ? <LockKeyhole className="h-3.5 w-3.5 text-white/35" /> : <ChevronDown className="h-4 w-4 text-white/45" />}</button>
  </aside>
}

function NavButton({ icon: Icon, label, active, compact, locked, onClick }: { icon: ElementType; label: string; active?: boolean; compact?: boolean; locked?: boolean; onClick: () => void }) { return <button disabled={locked} title={locked ? `${label} is available after sign in` : label} onClick={onClick} className={cn("flex w-full items-center gap-3 rounded-lg px-2 text-sm font-medium hover:bg-white/[0.07] disabled:cursor-not-allowed disabled:text-white/38 disabled:hover:bg-transparent", compact ? "h-9 text-xs text-white/75" : "h-10", active && "bg-white/[0.09]")}><Icon className="h-4 w-4" />{label}{locked && <LockKeyhole className="ml-auto h-3.5 w-3.5" />}</button> }
function SidebarSection({ title, children }: { title: string; children: ReactNode }) { return <section className="mt-5"><h2 className="mb-1 px-2 text-xs font-medium text-white/55">{title}</h2><div className="space-y-0.5">{children}</div></section> }
function SidebarRow({ icon: Icon, label, active, onClick }: { icon?: ElementType; label: string; active?: boolean; onClick: () => void }) { return <button onClick={onClick} title={label} className={cn("flex h-9 w-full items-center gap-2 rounded-lg px-2 text-left text-xs text-white/82 hover:bg-white/[0.07]", active && "bg-white/[0.09]")}>{Icon && <Icon className="h-3.5 w-3.5 shrink-0" />}<span className="truncate">{label}</span></button> }

function ChatSidebarRow({ chat, icon: Icon, active, menuOpen, moving, projects, onOpen, onMenu, onRename, onPin, onMove, onMoveTo, onArchive, onDelete }: { chat: ConversationRecord; icon?: ElementType; active: boolean; menuOpen: boolean; moving: boolean; projects: ProjectRecord[]; onOpen: () => void; onMenu: () => void; onRename: () => void; onPin: () => void; onMove: () => void; onMoveTo: (projectId: string | null) => void; onArchive: () => void; onDelete: () => void }) {
  return <div className="group relative"><button onClick={onOpen} title={chat.title} className={cn("flex h-9 w-full items-center gap-2 rounded-lg px-2 pr-9 text-left text-xs text-white/82 hover:bg-white/[0.07]", active && "bg-white/[0.09]")}>{Icon && <Icon className="h-3.5 w-3.5 shrink-0" />}<span className="truncate">{chat.title}</span></button><button onClick={(event) => { event.stopPropagation(); onMenu() }} aria-label={`Options for ${chat.title}`} className="absolute right-1 top-1 flex h-7 w-7 items-center justify-center rounded-md text-white/45 opacity-100 hover:bg-white/10 hover:text-white md:opacity-0 md:group-hover:opacity-100 md:focus:opacity-100"><MoreHorizontal className="h-4 w-4" /></button>{menuOpen && <div className="absolute right-1 top-9 z-[70] w-52 rounded-xl border border-white/10 bg-[#090d18] p-1.5 shadow-2xl">{moving ? <><MenuButton icon={X} label="No project" onClick={() => onMoveTo(null)} />{projects.map((project) => <MenuButton key={project.id} icon={FolderKanban} label={project.name} onClick={() => onMoveTo(project.id)} />)}{!projects.length && <p className="px-2 py-2 text-xs text-white/40">No projects yet.</p>}</> : <><MenuButton icon={Edit3} label="Rename" onClick={onRename} /><MenuButton icon={chat.pinned ? PinOff : Pin} label={chat.pinned ? "Unpin" : "Pin"} onClick={onPin} /><MenuButton icon={FileInput} label="Move to project" onClick={onMove} /><MenuButton icon={Archive} label="Archive" onClick={onArchive} /><MenuButton icon={Trash2} label="Delete" danger onClick={onDelete} /></>}</div>}</div>
}

function MenuButton({ icon: Icon, label, danger, onClick }: { icon: ElementType; label: string; danger?: boolean; onClick: () => void }) { return <button onClick={onClick} className={cn("flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-xs hover:bg-white/[0.07]", danger ? "text-rose-300" : "text-white/80")}><Icon className="h-3.5 w-3.5" />{label}</button> }
