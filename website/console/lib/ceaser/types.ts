import type { LucideIcon } from "lucide-react"

export type AgentId = "ceaser" | "bolt" | "alex" | "friday" | "zeus" | "nova" | "atlas"

export type AgentStatus = "active" | "idle" | "busy"

export type IntegrationId =
  | "github"
  | "vscode"
  | "vercel"
  | "railway"
  | "supabase"
  | "google-drive"
  | "gmail"
  | "google-calendar"
  | "notion"
  | "deepgram"
  | "elevenlabs"

export type AppPage =
  | "mission-control"
  | "chat"
  | "student"
  | "agents"
  | "drafts"
  | "projects"
  | "goals"
  | "memory"
  | "files"
  | "automations"
  | "integrations"
  | "analytics"
  | "admin"
  | "settings"

export interface CeaserModule {
  id: string
  name: string
  description: string
}

export interface CeaserAgent {
  id: AgentId
  name: string
  role: string
  description: string
  purpose: string
  status: AgentStatus
  color: string
  colorClass: string
  bgColorClass: string
  icon: LucideIcon
  currentTask?: string
  progress?: number
  modules: CeaserModule[]
  capabilities: string[]
}

export interface CeaserIntegration {
  id: IntegrationId
  name: string
  category: "development" | "deployment" | "productivity" | "voice" | "data"
  description: string
  status: "connected" | "available" | "planned"
}

export interface CeaserEngine {
  id: "atlas" | "document" | "automation" | "memory" | "voice"
  name: string
  purpose: string
  workflow: string[]
  capabilities: string[]
  integrations?: IntegrationId[]
}

export interface NavigationItem {
  id: AppPage
  label: string
  icon: LucideIcon
}
