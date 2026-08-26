export interface BrowserVoiceOption {
  id: string
  name: string
  lang: string
  localService: boolean
  rank: number
}

export class BrowserTTSProvider {
  getVoices(): BrowserVoiceOption[] {
    if (typeof window === "undefined" || !window.speechSynthesis) return []
    return window.speechSynthesis
      .getVoices()
      .map((voice) => ({
        id: voice.voiceURI || voice.name,
        name: voice.name,
        lang: voice.lang,
        localService: voice.localService,
        rank: rankVoice(voice),
      }))
      .sort((a, b) => b.rank - a.rank || a.name.localeCompare(b.name))
  }

  speak(text: string, preferredVoice?: string | null, options: { rate?: number; volume?: number; lang?: string } = {}) {
    if (!text || typeof window === "undefined" || !window.speechSynthesis) return false
    const voices = window.speechSynthesis.getVoices()
    const selected =
      voices.find((voice) => voice.voiceURI === preferredVoice || voice.name === preferredVoice) ??
      voices.sort((a, b) => rankVoice(b) - rankVoice(a))[0]
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    if (selected) utterance.voice = selected
    utterance.lang = selected?.lang || options.lang || "en"
    utterance.rate = options.rate ?? 1
    utterance.pitch = 1
    utterance.volume = options.volume ?? 1
    window.speechSynthesis.speak(utterance)
    return true
  }
}

export class ElevenLabsProvider {
  canUse(audioBase64?: string | null) {
    return Boolean(audioBase64)
  }

  play(audioBase64: string, contentType = "audio/mpeg") {
    const audio = new Audio(`data:${contentType};base64,${audioBase64}`)
    void audio.play()
  }
}

function rankVoice(voice: SpeechSynthesisVoice) {
  const name = voice.name.toLowerCase()
  const lang = voice.lang.toLowerCase()
  if (name.includes("aria")) return 100
  if (name.includes("jenny")) return 95
  if (name.includes("guy")) return 90
  if (name.includes("natural") || name.includes("neural") || name.includes("online")) return 80
  if (lang.startsWith("en")) return 60
  return 10
}
