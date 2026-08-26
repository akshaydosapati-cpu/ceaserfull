import { apiRequest } from "./client"

export interface IntegrationRecord {
  id: string
  name: string
  category: string
  description: string
  scopes: string[]
  permissions: string[]
  read_only: boolean
  status: string
  connected: boolean
  account_email?: string | null
  last_sync_at?: string | null
  provider_account_id?: string | null
  metadata: Record<string, unknown>
  token_expires_at?: string | null
}

export interface IntegrationProvider {
  id: string
  name: string
  category: string
  description: string
  scopes: string[]
  permissions: string[]
  read_only: boolean
}

export interface IntegrationConnectResponse {
  provider: string
  auth_url?: string | null
  state?: string | null
  requires_credentials: boolean
  integration?: IntegrationRecord | null
}

export const integrationsApi = {
  list: () => apiRequest<IntegrationRecord[]>("/integrations"),
  providers: () => apiRequest<IntegrationProvider[]>("/integrations/providers"),
  status: (provider: string) => apiRequest(`/integrations/${provider}/status`),
  connect: (provider: string, code?: string) =>
    apiRequest<IntegrationConnectResponse>(`/integrations/${provider}/connect`, {
      method: "POST",
      body: {
        code,
        return_url: typeof window !== "undefined" ? `${window.location.origin}${window.location.pathname}` : undefined,
      },
    }),
  disconnect: (provider: string) => apiRequest(`/integrations/${provider}/disconnect`, { method: "POST" }),
  refresh: (provider: string) => apiRequest(`/integrations/${provider}/refresh`, { method: "POST" }),
  sync: (provider: string) => apiRequest(`/integrations/${provider}/sync`, { method: "POST" }),
  metadata: (provider: string) => apiRequest(`/integrations/${provider}/metadata`),
}
