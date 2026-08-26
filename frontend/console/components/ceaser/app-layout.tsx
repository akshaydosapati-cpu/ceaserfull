"use client"

import { AppProvider } from "@/lib/app-context"
import { Sidebar } from "./sidebar"
import { Header } from "./header"
import { CommandBar } from "./command-bar"
import { VoiceModal } from "./modals/voice-modal"
import { SearchModal } from "./modals/search-modal"
import { AgentConfigModal } from "./modals/agent-config-modal"
import { WelcomeGate } from "./welcome-gate"
import { WindowTitlebar } from "./window-titlebar"
import { useEffect, useState, type ReactNode } from "react"
import { useApp } from "@/lib/app-context"

interface AppLayoutProps {
  children: ReactNode
}

export function AppLayout({ children }: AppLayoutProps) {
  return (
    <AppProvider>
      <WelcomeGate>
        <AppHotkeyBridge />
        <div className="flex flex-col h-screen overflow-hidden bg-background">
          {typeof window !== 'undefined' && !!(window as any).ceaserDesktop?.windowClose && <WindowTitlebar />}
          <div className="spatial-shell flex min-h-0 flex-1 overflow-hidden p-3">
            <Sidebar />
            <div className="ml-3 flex min-w-0 flex-1 flex-col overflow-hidden rounded-[1.65rem] border border-border bg-card/55 shadow-[0_30px_100px_rgba(0,0,0,0.18)]">
              <Header />
              <main className="min-h-0 flex-1 overflow-y-auto">
                {children}
              </main>
              <CommandBar />
            </div>
          </div>
        </div>
        <VoiceModal />
        <SearchModal />
        <AgentConfigModal />
      </WelcomeGate>
    </AppProvider>
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
