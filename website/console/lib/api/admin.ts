import { apiBlobRequest, apiRequest } from "./client"

export interface AdminMe {
  is_admin: boolean
  email: string
}

export interface AdminOverview {
  generated_at: string
  admin: { email: string }
  totals: Record<string, number>
  downloads_by_source: Array<{ source: string; platform: string; count: number }>
  plans: Array<{ code: string; name: string; subscriptions: number }>
  recent_users: Array<{ id: string; email: string; created_at: string }>
  recent_downloads: Array<{ source: string; platform: string; version?: string | null; created_at: string }>
  recent_payments: Array<{ provider_payment_id?: string | null; amount: number; currency: string; status: string; created_at: string; email?: string | null }>
  usage_7d: Array<{ action_type: string; quantity: number; tokens: number }>
}

export type InternshipStatus = "draft" | "published" | "revoked"
export interface InternshipDocument { id: string; document_type: string; original_filename: string; mime_type: string; file_size: number; version: number; status: string; uploaded_at: string }
export interface InternshipRecord { id: string; certificate_id: string; intern_name: string; role: string; organization: string; start_date: string; end_date: string; issue_date: string; status: InternshipStatus; created_at: string; documents: InternshipDocument[] }
export interface InternshipInput { intern_name: string; role: string; start_date: string; end_date: string; issue_date: string; certificate_id?: string }

export const adminApi = {
  me: () => apiRequest<AdminMe>("/admin/me", { cacheTtlMs: 30_000 }),
  overview: () => apiRequest<AdminOverview>("/admin/overview", { cacheTtlMs: 15_000 }),
  internships: (search = "", status = "") => apiRequest<InternshipRecord[]>(`/admin/internships?search=${encodeURIComponent(search)}&status=${encodeURIComponent(status)}`),
  createInternship: (body: InternshipInput) => apiRequest<InternshipRecord>("/admin/internships", { method: "POST", body }),
  updateInternship: (id: string, body: Partial<InternshipInput>) => apiRequest<InternshipRecord>(`/admin/internships/${id}`, { method: "PUT", body }),
  uploadInternshipDocument: (id: string, documentType: string, file: File) => { const body = new FormData(); body.append("document_type", documentType); body.append("upload", file); return apiRequest(`/admin/internships/${id}/documents`, { method: "POST", body }) },
  deleteInternshipDocument: (id: string, documentId: string) => apiRequest<void>(`/admin/internships/${id}/documents/${documentId}`, { method: "DELETE" }),
  publishInternship: (id: string) => apiRequest<InternshipRecord>(`/admin/internships/${id}/publish`, { method: "POST" }),
  revokeInternship: (id: string) => apiRequest<InternshipRecord>(`/admin/internships/${id}/revoke`, { method: "POST" }),
  restoreInternship: (id: string) => apiRequest<InternshipRecord>(`/admin/internships/${id}/restore`, { method: "POST" }),
  internshipDocument: (id: string, documentId: string, download = false) => apiBlobRequest(`/admin/internships/${id}/documents/${documentId}${download ? "?download=true" : ""}`),
}
