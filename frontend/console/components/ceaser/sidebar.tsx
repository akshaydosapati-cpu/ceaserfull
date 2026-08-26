"use client"

import Image from "next/image"
import { useEffect, useRef } from "react"
import favicon from "@/public/favicon.png"
import darkWordmark from "@/public/ceaser-wordmark-dark-transparent.png"
import { useApp } from "@/lib/app-context"
import { ceaserAgents, navigationItems } from "@/lib/ceaser"
import { AgentAvatar } from "./agent-avatar"
import { cn } from "@/lib/utils"
import { Plus } from "lucide-react"

export function Sidebar() {
  const { currentPage, setCurrentPage, setSelectedAgentId, sidebarCollapsed, setSidebarCollapsed } = useApp()
  const hoverTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const expandSidebar = () => {
    if (hoverTimer.current) clearTimeout(hoverTimer.current)
    hoverTimer.current = setTimeout(() => setSidebarCollapsed(false), 45)
  }

  const collapseSidebar = () => {
    if (hoverTimer.current) clearTimeout(hoverTimer.current)
    hoverTimer.current = setTimeout(() => setSidebarCollapsed(true), 90)
  }

  useEffect(() => () => {
    if (hoverTimer.current) clearTimeout(hoverTimer.current)
  }, [])

  return (
    <aside 
      onMouseEnter={expandSidebar}
      onMouseLeave={collapseSidebar}
      className={cn(
        "spatial-panel flex h-[calc(100vh-1.5rem)] transform-gpu flex-col rounded-[1.65rem] will-change-[width] transition-[width] duration-200 ease-[cubic-bezier(0.22,1,0.36,1)]",
        sidebarCollapsed ? "w-16" : "w-56"
      )}
    >
      {/* Logo */}
      <div className="flex h-20 items-center justify-center border-b border-border px-4 py-3 transition-[padding] duration-200">
        {sidebarCollapsed ? (
          <Image
            src={favicon}
            alt="CEASER"
            width={40}
            height={40}
            className="h-10 w-10 rounded-xl object-contain"
            priority
          />
        ) : (
          <Image
            src={darkWordmark}
            alt="CEASER"
            width={178}
            height={46}
            className="h-10 w-full max-w-[178px] object-contain"
            priority
          />
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto p-2">
        <div className="space-y-1">
          {navigationItems.map((item) => {
            const Icon = item.icon
            const isActive = currentPage === item.id
            return (
              <button
                key={item.id}
                onClick={() => setCurrentPage(item.id)}
                className={cn(
                  "flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-[background-color,color,padding] duration-150",
                  isActive 
                    ? "spatial-active-glow bg-primary/15 text-primary" 
                    : "text-muted-foreground hover:bg-white/5 hover:text-foreground",
                  sidebarCollapsed && "justify-center px-0"
                )}
              >
                <Icon className="h-4 w-4 flex-shrink-0" />
                {!sidebarCollapsed && <span>{item.label}</span>}
              </button>
            )
          })}
        </div>

        {/* Agents Section */}
        {!sidebarCollapsed && (
          <div className="mt-6">
            <p className="mb-2 px-3 text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Agents
            </p>
            <div className="space-y-1">
              {ceaserAgents.filter((agent) => agent.id !== "ceaser").map((agent) => (
                <button
                  key={agent.id}
                  onClick={() => {
                    setSelectedAgentId(agent.id)
                    setCurrentPage("agents")
                  }}
                  className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-muted-foreground transition-all hover:bg-white/5 hover:text-foreground"
                >
                  <AgentAvatar agent={agent} size="sm" showStatus />
                  <div className="flex-1 text-left">
                    <p className="font-medium text-foreground">{agent.name}</p>
                    <p className="text-xs text-muted-foreground">{agent.role}</p>
                  </div>
                </button>
              ))}
              <button className="flex w-full items-center gap-3 rounded-xl border border-dashed border-white/15 px-3 py-2.5 text-sm text-muted-foreground transition-colors hover:border-primary/60 hover:text-primary">
                <Plus className="h-4 w-4" />
                <span>Add New Agent</span>
              </button>
            </div>
          </div>
        )}
      </nav>

    </aside>
  )
}
