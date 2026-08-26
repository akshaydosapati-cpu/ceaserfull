import { apiRequest, invalidateApiCache } from "./client"

export interface MemoryRecord {
  id: string
  user_id: string
  memory_type: string
  content: string
  metadata?: Record<string, unknown>
  extra_metadata?: Record<string, unknown>
  created_at?: string
}

export interface MemoryGraph {
  nodes: { id: string; label: string; type: string }[]
  links: { source: string; target: string; label: string }[]
}

export const memoryApi = {
  list: () => apiRequest<MemoryRecord[]>("/memories"),
  create: (payload: { memory_type: string; content: string; metadata?: Record<string, unknown> }) =>
    apiRequest<MemoryRecord>("/memories", { method: "POST", body: payload }).then((response) => {
      invalidateApiCache(["/memories", "/memory/graph"])
      return response
    }),
  search: (query: string) =>
    apiRequest<MemoryRecord[]>("/memories/search", { method: "POST", body: { query } }),
  graph: () => apiRequest<MemoryGraph>("/memory/graph"),
  delete: (memoryId: string) =>
    apiRequest<void>(`/memories/${memoryId}`, { method: "DELETE" }).then((response) => {
      invalidateApiCache([`/memories/${memoryId}`, "/memories", "/memory/graph"])
      return response
    }),
}
