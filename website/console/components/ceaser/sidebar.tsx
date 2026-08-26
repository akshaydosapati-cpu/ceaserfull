"use client"

import Image from "next/image"
import { useEffect, useMemo, useState, type ElementType, type ReactNode } from "react"
import { ChevronDown, FileText, Folder, FolderKanban, MessageSquarePlus, MoreHorizontal, Puzzle, Search, Settings, Sparkles } from "lucide-react"
import darkWordmark from "@/public/ceaser-wordmark-dark-transparent.png"
import { useApp } from "@/lib/app-context"
import { chatApi, type ConversationRecord } from "@/lib/api/chat"
import { projectsApi, type ProjectRecord } from "@/lib/api/projects"
import { getUserDisplayName, getUserDisplayRole, readUserProfile } from "@/lib/user-profile"
import { cn } from "@/lib/utils"
import { recordStartupMetric } from "@/lib/api/client"

export function Sidebar() {
  const { currentPage, setCurrentPage } = useApp()
  const [projects, setProjects] = useState<ProjectRecord[]>([])
  const [chats, setChats] = useState<ConversationRecord[]>([])
  const [query, setQuery] = useState("")
  const [showMore, setShowMore] = useState(false)
  const [profile, setProfile] = useState(readUserProfile())

  useEffect(() => {
    void Promise.allSettled([projectsApi.list(), chatApi.listConversations(false)]).then(([projectResult, chatResult]) => {
      if (projectResult.status === "fulfilled") setProjects(projectResult.value)
      if (chatResult.status === "fulfilled") setChats(chatResult.value)
      recordStartupMetric("secondary_data_ready", {
        projects: projectResult.status === "fulfilled" ? projectResult.value.length : 0,
        conversations: chatResult.status === "fulfilled" ? chatResult.value.length : 0,
      })
    })
    const refresh = () => setProfile(readUserProfile())
    window.addEventListener("ceaser:profile-updated", refresh)
    return () => window.removeEventListener("ceaser:profile-updated", refresh)
  }, [])

  const filteredProjects = useMemo(() => projects.filter((item) => item.name.toLowerCase().includes(query.toLowerCase())).slice(0, 7), [projects, query])
  const filteredChats = useMemo(() => chats.filter((item) => item.title.toLowerCase().includes(query.toLowerCase())).slice(0, 9), [chats, query])
  const openChat = (id?: string) => {
    if (id) window.localStorage.setItem("ceaser_active_conversation_id", id)
    else window.localStorage.removeItem("ceaser_active_conversation_id")
    setCurrentPage("chat")
    window.dispatchEvent(new CustomEvent(id ? "ceaser:open-conversation" : "ceaser:new-chat", { detail: { id } }))
  }

  return <aside className="ceaser-global-sidebar flex h-full w-[260px] shrink-0 flex-col border-r border-white/[0.08] bg-[#050810] text-white">
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
      <NavButton icon={FileText} label="Library" active={currentPage === "files"} onClick={() => setCurrentPage("files")} />
      <NavButton icon={FolderKanban} label="Projects" active={currentPage === "projects"} onClick={() => setCurrentPage("projects")} />
      <NavButton icon={Puzzle} label="Plugins" active={currentPage === "integrations"} onClick={() => setCurrentPage("integrations")} />
      <NavButton icon={MoreHorizontal} label="More" onClick={() => setShowMore((value) => !value)} />
      {showMore && <div className="ml-3 border-l border-white/10 pl-2"><NavButton compact icon={Settings} label="Settings" onClick={() => setCurrentPage("settings")} /></div>}
    </div>
    <div className="mt-3 flex-1 overflow-y-auto px-3 pb-5 [scrollbar-width:thin]">
      <SidebarSection title="Pinned">{chats.filter((chat) => chat.pinned).slice(0, 3).map((chat) => <SidebarRow key={chat.id} icon={Sparkles} label={chat.title} onClick={() => openChat(chat.id)} />)}</SidebarSection>
      <SidebarSection title="Projects">{filteredProjects.map((project) => <SidebarRow key={project.id} icon={Folder} label={project.name} onClick={() => { window.localStorage.setItem("ceaser_selected_project_id", project.id); setCurrentPage("projects") }} />)}{!filteredProjects.length && <p className="px-2 py-2 text-xs text-white/35">No projects yet</p>}</SidebarSection>
      <SidebarSection title="Chats">{filteredChats.map((chat) => <SidebarRow key={chat.id} label={chat.title} active={currentPage === "chat" && window.localStorage.getItem("ceaser_active_conversation_id") === chat.id} onClick={() => openChat(chat.id)} />)}</SidebarSection>
    </div>
    <button onClick={() => setCurrentPage("settings")} className="m-3 flex items-center gap-3 rounded-xl border border-white/[0.08] p-2 text-left hover:bg-white/[0.05]"><span className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-cyan-500 to-violet-600 text-xs font-semibold">{getUserDisplayName(profile).charAt(0)}</span><span className="min-w-0 flex-1"><span className="block truncate text-sm">{getUserDisplayName(profile)}</span><span className="block truncate text-[11px] text-white/45">{getUserDisplayRole(profile)}</span></span><ChevronDown className="h-4 w-4 text-white/45" /></button>
  </aside>
}

function NavButton({ icon: Icon, label, active, compact, onClick }: { icon: ElementType; label: string; active?: boolean; compact?: boolean; onClick: () => void }) { return <button onClick={onClick} className={cn("flex w-full items-center gap-3 rounded-lg px-2 text-sm font-medium hover:bg-white/[0.07]", compact ? "h-9 text-xs text-white/75" : "h-10", active && "bg-white/[0.09]")}><Icon className="h-4 w-4" />{label}</button> }
function SidebarSection({ title, children }: { title: string; children: ReactNode }) { return <section className="mt-5"><h2 className="mb-1 px-2 text-xs font-medium text-white/55">{title}</h2><div className="space-y-0.5">{children}</div></section> }
function SidebarRow({ icon: Icon, label, active, onClick }: { icon?: ElementType; label: string; active?: boolean; onClick: () => void }) { return <button onClick={onClick} title={label} className={cn("flex h-9 w-full items-center gap-2 rounded-lg px-2 text-left text-xs text-white/82 hover:bg-white/[0.07]", active && "bg-white/[0.09]")}>{Icon && <Icon className="h-3.5 w-3.5 shrink-0" />}<span className="truncate">{label}</span></button> }
