import { apiRequest } from "./client"

export interface DesktopIntent {
  intent: "desktop_action" | "agent_action" | "chat_action" | "blocked" | string
  intent_type?: string | null
  action: string
  parameters: Record<string, unknown>
  requires_confirmation: boolean
  requires_permission: boolean
  required_permission?: string | null
  risk_level: string
  active_agent?: string | null
  agent_action?: string | null
  overlay_mode: string
  overlay_state: string
  progress_steps: Array<Record<string, unknown>>
  result_preview: Record<string, unknown>
}

export const desktopApi = {
  classify: (command: string) =>
    apiRequest<DesktopIntent>("/desktop/intent", {
      method: "POST",
      body: { command },
    }),
}
