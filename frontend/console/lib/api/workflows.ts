import { apiRequest } from "./client"

export interface WorkflowTemplateRecord {
  id: string
  name: string
  description: string
  agents: string[]
  mode: string
}

export interface WorkflowRunRecord {
  id: string
  user_id: string
  workflow_type: string
  status: string
  started_at?: string | null
  completed_at?: string | null
  result_summary?: string | null
  metadata_json: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface WorkflowStepRecord {
  id: string
  workflow_id: string
  agent_name: string
  status: string
  started_at?: string | null
  completed_at?: string | null
  output_summary?: string | null
  metadata_json: Record<string, unknown>
}

export const workflowsApi = {
  templates: () => apiRequest<WorkflowTemplateRecord[]>("/workflows/templates"),
  list: () => apiRequest<WorkflowRunRecord[]>("/workflows"),
  get: (workflowId: string) => apiRequest<WorkflowRunRecord>(`/workflows/${workflowId}`),
  steps: (workflowId: string) => apiRequest<WorkflowStepRecord[]>(`/workflows/${workflowId}/steps`),
  start: (message: string, conversationId?: string | null, fileIds?: string[]) =>
    apiRequest("/workflows/start", { method: "POST", body: { message, conversation_id: conversationId, file_ids: fileIds ?? [] } }),
  cancel: (workflowId: string) => apiRequest<WorkflowRunRecord>(`/workflows/${workflowId}/cancel`, { method: "POST" }),
}
