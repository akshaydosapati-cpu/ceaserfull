"use client"

import { AppProvider } from "@/lib/app-context"
import { Sidebar } from "./sidebar"
import { Header } from "./header"
import { VoiceModal } from "./modals/voice-modal"
import { SearchModal } from "./modals/search-modal"
import { AgentConfigModal } from "./modals/agent-config-modal"
import { WelcomeGate } from "./welcome-gate"
import { WindowTitlebar } from "./window-titlebar"
import { useEffect, useState, type ReactNode } from "react"
import { useApp } from "@/lib/app-context"
import { cn } from "@/lib/utils"
import { recordStartupMetric } from "@/lib/api/client"
import { trackEvent } from "@/lib/analytics"
import { Menu } from "lucide-react"

interface AppLayoutProps {
  children: ReactNode
  guestDemo?: boolean
}

export function AppLayout({ children, guestDemo = false }: AppLayoutProps) {
  return (
    <AppProvider guestDemo={guestDemo}>
      <WelcomeGate>
        <AppHotkeyBridge />
        <ButtonInteractionFeedback />
        <AppLayoutShell>{children}</AppLayoutShell>
        <VoiceModal />
        <SearchModal />
        <AgentConfigModal />
      </WelcomeGate>
    </AppProvider>
  )
}

function AppLayoutShell({ children }: AppLayoutProps) {
  const { currentPage, guestDemo, sidebarCollapsed, setSidebarCollapsed } = useApp()
  useEffect(() => {
    recordStartupMetric("app_navigation_start", { page: currentPage })
    recordStartupMetric("shell_visible")
    trackEvent("console_opened")
  }, [])
  return (
    <div className="ceaser-product-shell flex h-[100dvh] flex-col overflow-hidden bg-background">
      {typeof window !== 'undefined' && !!(window as any).ceaserDesktop?.windowClose && <WindowTitlebar />}
      <div className="spatial-shell relative flex min-h-0 flex-1 overflow-hidden p-0 md:p-2">
        {!sidebarCollapsed && (
          <button
            type="button"
            aria-label="Close navigation"
            onClick={() => setSidebarCollapsed(true)}
            className={cn("fixed inset-0 z-40 bg-black/65 backdrop-blur-[1px]", guestDemo ? "min-[520px]:hidden" : "md:hidden")}
          />
        )}
        {sidebarCollapsed && (
          <button
            type="button"
            aria-label="Open navigation"
            onClick={() => setSidebarCollapsed(false)}
            className={cn("fixed left-3 top-3 z-40 flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-[#0a1020]/90 text-white shadow-xl backdrop-blur-md", guestDemo ? "min-[520px]:hidden" : "md:hidden")}
          >
            <Menu className="h-5 w-5" />
          </button>
        )}
        <Sidebar />
        <div className={cn(
          "ceaser-app-frame ml-0 flex min-w-0 flex-1 flex-col overflow-hidden rounded-none border-y border-border bg-card/55 shadow-[0_30px_100px_rgba(0,0,0,0.18)] md:ml-2 md:rounded-lg md:border",
          guestDemo && "min-[520px]:ml-2 min-[520px]:rounded-lg min-[520px]:border",
          currentPage === "chat" && "bg-[#030712]",
        )}>
          {currentPage !== "chat" && <Header />}
          <main className="min-h-0 flex-1 overflow-y-auto">
            {children}
          </main>
        </div>
      </div>
    </div>
  )
}

function AppHotkeyBridge() {
  const { setIsVoiceModalOpen } = useApp()

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!(event.ctrlKey && event.shiftKey && event.code === "Space")) return
      event.preventDefault()
      window.dispatchEvent(new CustomEvent("ceaser:start-web-voice"))
      setIsVoiceModalOpen(true)
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [setIsVoiceModalOpen])

  return null
}

function ButtonInteractionFeedback() {
  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      const button = (event.target as Element | null)?.closest("button") as HTMLButtonElement | null
      if (!button || button.disabled || button.dataset.loading === "true") return
      button.dataset.loading = "true"
      button.setAttribute("aria-busy", "true")
      window.setTimeout(() => {
        button.dataset.loading = "false"
        button.removeAttribute("aria-busy")
      }, 450)
    }
    document.addEventListener("click", onClick)
    return () => document.removeEventListener("click", onClick)
  }, [])

  return null
}
