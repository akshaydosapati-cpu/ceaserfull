import { apiRequest, invalidateApiCache } from "./client"

export type DocumentKind = "pptx" | "docx" | "xlsx" | "pdf"

export interface DocumentTemplate {
  id: string
  name: string
  kind: DocumentKind
  agent_id: string
  sections: string[]
}

export interface GeneratedDocument {
  id: string
  file_id: string
  user_id: string
  agent_id: string
  template_id: string
  generated_by: string
  export_format: DocumentKind
  version: number
  source_prompt: string
  created_at: string
  file_name?: string | null
}

export interface AgentActivity {
  id: string
  user_id: string
  file_id?: string | null
  agent_id: string
  action: string
  detail: string
  created_at: string
}

export const documentsApi = {
  templates: (params?: { kind?: DocumentKind; agent_id?: string }) => {
    const query = new URLSearchParams()
    if (params?.kind) query.set("kind", params.kind)
    if (params?.agent_id) query.set("agent_id", params.agent_id)
    return apiRequest<DocumentTemplate[]>(`/documents/templates${query.toString() ? `?${query}` : ""}`)
  },
  list: (params?: { agent_id?: string }) => {
    const query = new URLSearchParams()
    if (params?.agent_id) query.set("agent_id", params.agent_id)
    return apiRequest<GeneratedDocument[]>(`/documents${query.toString() ? `?${query}` : ""}`)
  },
  create: (payload: { kind: DocumentKind; prompt: string; template_id?: string | null; agent_id?: string | null; source_content?: string | null }) =>
    apiRequest<{ document: GeneratedDocument; file: Record<string, unknown>; preview: string }>("/documents", { method: "POST", body: payload }).then((response) => {
      invalidateApiCache(["/documents", "/files", "/projects", "/memories"])
      return response
    }),
  export: (documentId: string) =>
    apiRequest<{ downloadUrl: string; file_id: string }>(`/documents/${documentId}/export`, { method: "POST" }),
  agentWorkbench: (agentId: string) =>
    apiRequest<{ agent_id: string; templates: DocumentTemplate[]; generated_documents: GeneratedDocument[]; activity: AgentActivity[] }>(
      `/agent-document-workbenches/${agentId}`,
    ),
}
