import { apiRequest } from "./client"

export interface ProjectRecord {
  id: string
  user_id?: string
  name: string
  description?: string | null
  status: string
  created_at?: string
  updated_at?: string
}

export const projectsApi = {
  list: () => apiRequest<ProjectRecord[]>("/projects"),
  get: (projectId: string) => apiRequest<ProjectRecord>(`/projects/${projectId}`),
  create: (project: Omit<ProjectRecord, "id" | "user_id">) =>
    apiRequest<ProjectRecord>("/projects", { method: "POST", body: project }),
  update: (projectId: string, updates: Partial<Pick<ProjectRecord, "name" | "description" | "status">>) =>
    apiRequest<ProjectRecord>(`/projects/${projectId}`, { method: "PATCH", body: updates }),
  delete: (projectId: string) => apiRequest<void>(`/projects/${projectId}`, { method: "DELETE" }),
}
