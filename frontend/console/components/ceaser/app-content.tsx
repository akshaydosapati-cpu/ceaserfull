"use client"

import { useApp } from "@/lib/app-context"
import { MissionControl } from "./pages/mission-control"
import { ChatPage } from "./pages/chat-page"
import { StudentPage } from "./pages/student-page"
import { AgentsPage } from "./pages/agents-page"
import { DraftsPage } from "./pages/drafts-page"
import { MemoryPage } from "./pages/memory-page"
import { ProjectsPage } from "./pages/projects-page"
import { GoalsPage } from "./pages/goals-page"
import { FilesPage } from "./pages/files-page"
import { IntegrationsPage } from "./pages/integrations-page"
import { SettingsPage } from "./pages/settings-page"

export function AppContent() {
  const { currentPage } = useApp()

  switch (currentPage) {
    case "mission-control":
      return <MissionControl />
    case "chat":
      return <ChatPage />
    case "student":
      return <StudentPage />
    case "agents":
      return <AgentsPage />
    case "drafts":
      return <DraftsPage />
    case "memory":
      return <MemoryPage />
    case "projects":
      return <ProjectsPage />
    case "goals":
      return <GoalsPage />
    case "files":
      return <FilesPage />
    case "integrations":
      return <IntegrationsPage />
    case "settings":
      return <SettingsPage />
    default:
      return <MissionControl />
  }
}
