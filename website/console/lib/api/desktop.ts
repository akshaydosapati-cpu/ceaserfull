import { apiRequest } from "./client"

export interface DesktopDevice {
  device_id: string
  device_name: string
  platform?: string | null
  app_version?: string | null
  created_at: string
  last_seen_at?: string | null
  revoked_at?: string | null
  status: string
  gateway_status?: string
  capabilities?: string[]
}

export interface DesktopIntent {
  intent: string
  intent_type?: string | null
  action: string
  parameters?: Record<string, unknown>
  requires_confirmation?: boolean
  requires_permission?: boolean
  required_permission?: string | null
  risk_level?: string
  active_agent?: string | null
  agent_action?: string | null
  overlay_mode?: string
  overlay_state?: string
  progress_steps?: Record<string, unknown>[]
  result_preview?: Record<string, unknown>
}

export interface DesktopAuthorizePayload {
  state: string
  code_challenge: string
  code_challenge_method: "S256"
  redirect_uri: string
  device_id: string
  device_name: string
  platform?: string | null
  app_version?: string | null
}

export const desktopApi = {
  classify: (command: string) =>
    apiRequest<DesktopIntent>("/desktop/intent", {
      method: "POST",
      body: { command },
    }),
  authorize: (payload: DesktopAuthorizePayload) =>
    apiRequest<{ code: string; state: string; expires_in: number }>("/auth/desktop/authorize", {
      method: "POST",
      body: payload,
    }),
  listDevices: () => apiRequest<DesktopDevice[]>("/desktop/devices", { cacheTtlMs: 10_000 }),
  revokeDevice: (deviceId: string) => apiRequest<{ status: string }>(`/desktop/devices/${encodeURIComponent(deviceId)}`, { method: "DELETE" }),
}
