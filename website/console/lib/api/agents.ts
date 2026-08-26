import { apiRequest } from "./client"

export interface BackendAgentModule {
  id: string
  agent_id: string
  module_name: string
  enabled: boolean
}

export interface BackendAgent {
  id: string
  user_id: string
  name: string
  enabled: boolean
  modules: BackendAgentModule[]
}

export const agentsApi = {
  list: () => apiRequest<BackendAgent[]>("/agents"),
  get: (agentId: string) => apiRequest<BackendAgent>(`/agents/${agentId}`),
  enable: (agentId: string) => apiRequest<BackendAgent>(`/agents/${agentId}/enable`, { method: "POST" }),
  disable: (agentId: string) => apiRequest<BackendAgent>(`/agents/${agentId}/disable`, { method: "POST" }),
  updateModules: (agentId: string, moduleIds: string[]) =>
    apiRequest<BackendAgent>(`/agents/${agentId}/modules`, {
      method: "PUT",
      body: { moduleIds },
    }),
}
