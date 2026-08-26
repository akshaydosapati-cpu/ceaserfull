"use client"

import { useEffect, useRef, useState } from "react"
import { voiceApi, type VoiceRespondResponse, type VoiceSettingsRecord, type VoiceStatus as VoiceState } from "@/lib/api/voice"
import { VoiceButton } from "./VoiceButton"
import { VoiceStatus } from "./VoiceStatus"
import { VoiceTranscript } from "./VoiceTranscript"
import { VoiceVisualizer } from "./VoiceVisualizer"
import { playVoiceAudio, speakWithBrowserVoice } from "./VoicePlayer"
import { BrowserTTSProvider } from "./providers"

export function VoiceControls({
  conversationId,
  disabled,
  onResponse,
}: {
  conversationId?: string | null
  disabled?: boolean
  onResponse: (response: VoiceRespondResponse) => void
}) {
  const [status, setStatus] = useState<VoiceState>("idle")
  const [transcript, setTranscript] = useState("")
  const [statusMessage, setStatusMessage] = useState("")
  const [settings, setSettings] = useState<VoiceSettingsRecord | null>(null)
  const [browserVoices, setBrowserVoices] = useState(() => new BrowserTTSProvider().getVoices())
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const provider = settings?.voice_provider ?? "auto"
  const selectedVoice = settings?.preferred_voice ?? browserVoices[0]?.id ?? null

  useEffect(() => {
    void voiceApi.getSettings().then(setSettings).catch(() => setSettings(null))
    if (typeof window === "undefined" || !window.speechSynthesis) return
    const loadVoices = () => setBrowserVoices(new BrowserTTSProvider().getVoices())
    loadVoices()
    window.speechSynthesis.onvoiceschanged = loadVoices
    return () => {
      window.speechSynthesis.onvoiceschanged = null
    }
  }, [])

  const stop = () => {
    recorderRef.current?.stop()
  }

  const start = async () => {
    setTranscript("")
    setStatusMessage("")
    setStatus("listening")
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      setStatusMessage("Microphone permission denied")
      setStatus("error")
      return
    }
    const mimeType = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : ""
    const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream)
    chunksRef.current = []
    recorder.ondataavailable = (event) => {
      if (event.data.size) chunksRef.current.push(event.data)
    }
    recorder.onstop = async () => {
      stream.getTracks().forEach((track) => track.stop())
      setStatus("transcribing" as VoiceState)
      try {
        const audio = new Blob(chunksRef.current, { type: mimeType || "audio/webm" })
        const response = await voiceApi.respond(audio, conversationId)
        setStatus("processing")
        setTranscript(response.transcript)
        onResponse(response)
        const useElevenLabs = provider !== "browser" && response.audio_base64
        if (useElevenLabs) {
          setStatus("speaking")
          playVoiceAudio(response.audio_base64, response.audio_content_type ?? "audio/mpeg")
        } else if (response.spoken_summary) {
          const fallbackStarted = speakWithBrowserVoice(response.spoken_summary, selectedVoice, {
            rate: settings?.speech_speed ?? 1,
            volume: settings?.speech_volume ?? 1,
            lang: settings?.language ?? "en",
          })
          if (fallbackStarted) {
            setStatus("speaking")
            setStatusMessage(response.voice_warning ? "Voice playback unavailable. Using fallback voice." : "")
          }
        }
        if (response.voice_warning) {
          setStatusMessage(response.audio_base64 ? "Ready" : "Voice playback unavailable. Using fallback voice.")
        }
        setStatus("ready")
      } catch {
        setStatusMessage("Voice playback unavailable. Using fallback voice.")
        setStatus("error")
      }
    }
    recorderRef.current = recorder
    recorder.start()
  }

  return (
    <div className="flex min-w-0 items-center gap-2">
      <VoiceButton status={status} disabled={disabled || settings?.voice_enabled === false} onClick={status === "listening" ? stop : start} />
      <VoiceVisualizer status={status} />
      <div className="hidden min-w-0 flex-col sm:flex">
        <VoiceStatus status={status} message={statusMessage} />
        <VoiceTranscript transcript={transcript} />
      </div>
    </div>
  )
}
