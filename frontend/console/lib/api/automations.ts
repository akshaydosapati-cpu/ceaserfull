import { apiRequest } from "./client"

export type AutomationStatus = "active" | "paused"
export type AutomationType = "research" | "news" | "business" | "content" | "learning" | "execution" | "engineering"
export type AutomationFrequency = "once" | "daily" | "weekly" | "monthly" | "every_weekday" | "custom"

export interface AutomationTemplateRecord {
  id: string
  name: string
  category: AutomationType
  description: string
  default_agent: string
  default_prompt: string
  supported_frequencies: AutomationFrequency[]
  icon: string
  is_active: boolean
}

export interface AutomationRecord {
  id: string
  user_id: string
  workspace_id?: string | null
  name: string
  description?: string | null
  automation_type: AutomationType
  assigned_agent: string
  trigger_frequency: AutomationFrequency
  trigger_time?: string | null
  timezone: string
  status: AutomationStatus
  config_json: Record<string, unknown>
  last_run_at?: string | null
  next_run_at?: string | null
  created_at: string
  updated_at: string
}

export interface AutomationRunRecord {
  id: string
  automation_id: string
  user_id: string
  assigned_agent: string
  status: "running" | "completed" | "failed"
  started_at: string
  completed_at?: string | null
  output_title?: string | null
  output_summary?: string | null
  output_content: string
  error_message?: string | null
  metadata_json: AutomationRunMetadata
}

export interface AutomationNewsArticle {
  title: string
  source?: string | null
  url?: string | null
  published_at?: string | null
  summary?: string | null
  image_url?: string | null
}

export interface AutomationNewsBrief {
  query: string
  mode: string
  provider: string
  articles: AutomationNewsArticle[]
  error?: string | null
}

export interface AutomationRunMetadata {
  selected_agents?: string[]
  memory_count?: number
  research?: unknown
  news?: AutomationNewsBrief | null
  integrations?: unknown
  context_summary?: Record<string, unknown>
  [key: string]: unknown
}

export interface AutomationWorkerHealth {
  enabled: boolean
  running: boolean
  interval_seconds: number
  batch_size: number
  started_at?: string | null
  last_scan_at?: string | null
  last_run_count: number
  total_runs: number
  last_error?: string | null
}

export interface AutomationCreatePayload {
  name: string
  description?: string | null
  automation_type: AutomationType
  trigger_frequency: AutomationFrequency
  trigger_time?: string | null
  timezone: string
  status: AutomationStatus
  config_json: Record<string, unknown>
}

export const automationsApi = {
  templates: () => apiRequest<AutomationTemplateRecord[]>("/automations/templates"),
  list: () => apiRequest<AutomationRecord[]>("/automations"),
  create: (payload: AutomationCreatePayload) => apiRequest<AutomationRecord>("/automations", { method: "POST", body: payload }),
  update: (automationId: string, payload: Partial<AutomationCreatePayload>) =>
    apiRequest<AutomationRecord>(`/automations/${automationId}`, { method: "PUT", body: payload }),
  delete: (automationId: string) => apiRequest<void>(`/automations/${automationId}`, { method: "DELETE" }),
  pause: (automationId: string) => apiRequest<AutomationRecord>(`/automations/${automationId}/pause`, { method: "POST" }),
  resume: (automationId: string) => apiRequest<AutomationRecord>(`/automations/${automationId}/resume`, { method: "POST" }),
  runNow: (automationId: string) => apiRequest<AutomationRunRecord>(`/automations/${automationId}/run-now`, { method: "POST" }),
  runs: (automationId: string) => apiRequest<AutomationRunRecord[]>(`/automations/${automationId}/runs`),
  workerHealth: () => apiRequest<AutomationWorkerHealth>("/automations/worker/health"),
  runDue: () => apiRequest<AutomationRunRecord[]>("/automations/worker/run-due", { method: "POST" }),
}
