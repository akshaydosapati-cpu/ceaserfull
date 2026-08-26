import { apiRequest, invalidateApiCache } from "./client"

export interface DraftSection {
  title: string
  body: string
  status: string
}

export interface DraftRecord {
  id: string
  user_id: string
  agent_id: string
  title: string
  draft_type: string
  status: string
  progress: number
  target_app: string
  requested_units: number
  source_prompt: string
  content: {
    title: string
    type: string
    owner_agent: string
    sections?: Array<DraftSection | { heading?: string; summary?: string; details?: string[]; recommendations?: string[] }>
    draft_type?: string
    slides?: Array<{ slide_number: number; title: string; purpose: string; bullets: string[]; visual_suggestion: string; speaker_notes: string; memory_references?: string[]; source_references?: string[] }>
    key_findings?: Array<{ finding: string; evidence: string; source_references?: string[] }>
    sources?: Array<Record<string, unknown>>
    recommendations?: string[]
    modules?: Array<{ name: string; purpose: string; responsibilities?: string[]; dependencies?: string[] }>
    apis?: Array<Record<string, unknown>>
    database_design?: Array<Record<string, unknown>>
    calendar_items?: Array<Record<string, string>>
    daily_plan?: Array<{ day: string; focus: string; tasks: string[]; practice?: string[] }>
    milestones?: Array<{ name: string; tasks: string[]; priority?: string; deadline?: string; dependencies?: string[]; status?: string }>
    [key: string]: unknown
  }
  created_at: string
}

export interface DraftHistoryRecord {
  id: string
  draft_id: string
  user_id: string
  agent_id: string
  action: string
  detail: string
  created_at: string
}

export interface AgentWorkbenchRecord {
  agent_id: string
  kpis: {
    active_drafts: number
    completed_drafts: number
    reports_generated: number
    strategies_created: number
  }
  quick_actions: string[]
  templates: Array<{ id: string; name: string; kind: string; agent_id: string; sections: string[] }>
  drafts: DraftRecord[]
  activity: DraftHistoryRecord[]
}

export const draftsApi = {
  list: (params?: { agent_id?: string; status?: string }) => {
    const query = new URLSearchParams()
    if (params?.agent_id) query.set("agent_id", params.agent_id)
    if (params?.status) query.set("status", params.status)
    return apiRequest<DraftRecord[]>(`/drafts${query.toString() ? `?${query}` : ""}`)
  },
  create: (payload: { prompt: string; draft_type?: string | null; agent_id?: string | null; target_app?: string; requested_units?: number }) =>
    apiRequest<DraftRecord>("/drafts", { method: "POST", body: payload }).then((response) => {
      invalidateApiCache(["/drafts"])
      return response
    }),
  action: (draftId: string, action: "regenerated" | "approved" | "archived") =>
    apiRequest<DraftRecord>(`/drafts/${draftId}/${action}`, { method: "POST" }).then((response) => {
      invalidateApiCache(["/drafts"])
      return response
    }),
  delete: (draftId: string) =>
    apiRequest<{ status: string; id: string }>(`/drafts/${draftId}`, { method: "DELETE" }).then((response) => {
      invalidateApiCache(["/drafts"])
      return response
    }),
  agentWorkbench: (agentId: string) =>
    apiRequest<AgentWorkbenchRecord>(`/agent-workbenches/${agentId}`),
}
