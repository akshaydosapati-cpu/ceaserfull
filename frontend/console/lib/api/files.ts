import { apiRequest, getAccessToken } from "./client"

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  process.env.NEXT_PUBLIC_CEASER_API_URL ??
  "https://ceaser-backend-production.onrender.com"

export interface FileRecord {
  id: string
  user_id: string
  project_id?: string | null
  name: string
  file_type: string
  storage_path: string
  extraction_metadata: Record<string, unknown>
  created_at: string
}

export interface FileContentRecord extends FileRecord {
  extracted_content: string
}

export type DocumentAction = "summarize" | "explain" | "simple" | "notes" | "mcqs" | "flashcards" | "actions"

async function multipartRequest<T>(path: string, formData: FormData): Promise<T> {
  const token = getAccessToken()
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: formData,
  })
  if (!response.ok) throw new Error(`CEASER file request failed: ${path}`)
  return response.json() as Promise<T>
}

export const filesApi = {
  list: () => apiRequest<FileRecord[]>("/files"),
  get: (fileId: string) => apiRequest<FileContentRecord>(`/files/${fileId}`),
  upload: (file: File, projectId?: string | null) => {
    const formData = new FormData()
    if (projectId) formData.set("project_id", projectId)
    formData.set("upload", file, file.name)
    return multipartRequest<FileRecord>("/files/upload", formData)
  },
  analyze: (fileId: string, action: DocumentAction, question?: string, language?: string) =>
    apiRequest<{ file_id: string; action: DocumentAction; response: string }>(`/files/${fileId}/analyze`, {
      method: "POST",
      body: { action, question, language },
    }),
  updateProject: (fileId: string, projectId: string | null) =>
    apiRequest<FileRecord>(`/files/${fileId}/project`, {
      method: "PATCH",
      body: { project_id: projectId },
    }),
  delete: (fileId: string) => apiRequest<void>(`/files/${fileId}`, { method: "DELETE" }),
  downloadUrl: (fileId: string) => `${API_BASE_URL}/files/${fileId}/download`,
  download: async (file: FileRecord) => {
    const token = getAccessToken()
    const response = await fetch(`${API_BASE_URL}/files/${file.id}/download`, {
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    })
    if (!response.ok) throw new Error("Download failed")
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = file.name
    anchor.click()
    window.URL.revokeObjectURL(url)
  },
}
