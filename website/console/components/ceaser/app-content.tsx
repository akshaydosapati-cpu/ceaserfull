"use client"

import { useApp } from "@/lib/app-context"
import { ENABLE_STUDENT_HUB } from "@/lib/ceaser"
import dynamic from "next/dynamic"
import { ChatPage } from "./pages/chat-page"

const StudentPage = dynamic(() => import("./pages/student-page").then((module) => module.StudentPage))
const MemoryPage = dynamic(() => import("./pages/memory-page").then((module) => module.MemoryPage))
const ProjectsPage = dynamic(() => import("./pages/projects-page").then((module) => module.ProjectsPage))
const GoalsPage = dynamic(() => import("./pages/goals-page").then((module) => module.GoalsPage))
const FilesPage = dynamic(() => import("./pages/files-page").then((module) => module.FilesPage))
const IntegrationsPage = dynamic(() => import("./pages/integrations-page").then((module) => module.IntegrationsPage))
const SettingsPage = dynamic(() => import("./pages/settings-page").then((module) => module.SettingsPage))
const AdminPage = dynamic(() => import("./pages/admin-page").then((module) => module.AdminPage))

export function AppContent() {
  const { currentPage } = useApp()

  if (currentPage === "student" && !ENABLE_STUDENT_HUB) {
    return <ChatPage />
  }

  switch (currentPage) {
    case "mission-control":
      return <ChatPage />
    case "chat":
      return <ChatPage />
    case "student":
      return <StudentPage />
    case "agents":
      return <ChatPage />
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
    case "admin":
      return <AdminPage />
    default:
      return <ChatPage />
  }
}
