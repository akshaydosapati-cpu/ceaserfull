import { BrowserTTSProvider, ElevenLabsProvider } from "./providers"

export function playVoiceAudio(audioBase64?: string | null, contentType = "audio/mpeg") {
  if (!audioBase64 || typeof window === "undefined") return
  new ElevenLabsProvider().play(audioBase64, contentType)
}

export function speakWithBrowserVoice(text?: string | null, preferredVoice?: string | null, options: { rate?: number; volume?: number; lang?: string } = {}) {
  return new BrowserTTSProvider().speak(text ?? "", preferredVoice, options)
}
