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

interface AppLayoutProps {
  children: ReactNode
}

export function AppLayout({ children }: AppLayoutProps) {
  return (
    <AppProvider>
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
  const { currentPage } = useApp()
  useEffect(() => {
    recordStartupMetric("app_navigation_start", { page: currentPage })
    recordStartupMetric("shell_visible")
    trackEvent("console_opened")
  }, [])
  return (
    <div className="ceaser-product-shell flex h-screen flex-col overflow-hidden bg-background">
      {typeof window !== 'undefined' && !!(window as any).ceaserDesktop?.windowClose && <WindowTitlebar />}
      <div className="spatial-shell flex min-h-0 flex-1 overflow-hidden p-2">
        <Sidebar />
        <div className={cn("ceaser-app-frame ml-2 flex min-w-0 flex-1 flex-col overflow-hidden rounded-lg border border-border bg-card/55 shadow-[0_30px_100px_rgba(0,0,0,0.18)]", currentPage === "chat" && "bg-[#030712]")}>
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
