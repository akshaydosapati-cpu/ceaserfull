import { apiRequest } from "./client"

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

export const adminApi = {
  me: () => apiRequest<AdminMe>("/admin/me", { cacheTtlMs: 30_000 }),
  overview: () => apiRequest<AdminOverview>("/admin/overview", { cacheTtlMs: 15_000 }),
}
