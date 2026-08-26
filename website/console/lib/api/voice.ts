import { getAccessToken, getApiBaseUrl } from "./client"
import type { CeaserChatResponse } from "./chat"

const API_BASE_URL = getApiBaseUrl()

export type VoiceStatus = "idle" | "listening" | "transcribing" | "processing" | "speaking" | "ready" | "error"

export interface VoiceSettingsRecord {
  id: string
  user_id: string
  voice_enabled: boolean
  auto_speak_responses: boolean
  voice_provider: "auto" | "browser" | "elevenlabs"
  preferred_voice?: string | null
  speech_speed: number
  speech_volume: number
  language: string
}

export interface VoiceRespondResponse {
  session_id: string
  transcript: string
  chat: CeaserChatResponse
  spoken_summary: string
  audio_base64?: string | null
  audio_content_type?: string | null
  voice_warning?: string | null
}

async function voiceRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getAccessToken()
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })
  if (!response.ok) {
    let detail = `CEASER voice request failed: ${path}`
    try {
      const payload = await response.json()
      if (payload?.detail) detail = String(payload.detail)
    } catch {
      // Keep the default error when the response is not JSON.
    }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

export const voiceApi = {
  transcribe: (audio: Blob, language?: string | null) => {
    const formData = new FormData()
    formData.set("audio", audio, "ceaser-voice.webm")
    if (language) formData.set("language", language)
    return voiceRequest<{ transcript: string }>("/voice/transcribe", { method: "POST", body: formData })
  },
  respond: (audio: Blob, conversationId?: string | null) => {
    const formData = new FormData()
    formData.set("audio", audio, "ceaser-voice.webm")
    if (conversationId) formData.set("conversation_id", conversationId)
    return voiceRequest<VoiceRespondResponse>("/voice/respond", { method: "POST", body: formData })
  },
  getSettings: () => voiceRequest<VoiceSettingsRecord>("/voice/settings"),
  updateSettings: (settings: Partial<VoiceSettingsRecord>) =>
    voiceRequest<VoiceSettingsRecord>("/voice/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    }),
}
