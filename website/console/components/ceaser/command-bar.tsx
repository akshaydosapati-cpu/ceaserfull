"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import type { ReactNode } from "react"
import { chatApi, type ConversationRecord } from "@/lib/api/chat"
import { desktopApi } from "@/lib/api/desktop"
import { voiceApi, type VoiceRespondResponse, type VoiceSettingsRecord, type VoiceStatus } from "@/lib/api/voice"
import { ceaserAgents } from "@/lib/ceaser"
import { cn } from "@/lib/utils"
import { playVoiceAudio, speakWithBrowserVoice } from "@/components/voice/VoicePlayer"
import { BrowserTTSProvider } from "@/components/voice/providers"
import { Activity, ArrowRight, Bot, Clock3, Loader2, Mic, MessageSquare, X } from "lucide-react"
import type { LucideIcon } from "lucide-react"
import { CeaserLogo } from "./ceaser-logo"

type ActivityItem = {
  id: string
  type: "voice" | "chat" | "system"
  title: string
  description: string
  timestamp: string
  status?: string
}

const ACTIVITY_STORAGE_KEY = "ceaser_recent_activity"
const FOOTER_VOICE_EVENT = "ceaser:footer-voice-response"
const WEB_VOICE_HOTKEY_EVENT = "ceaser:start-web-voice"
const DESKTOP_ACTIONS = new Set(["desktop_action", "blocked"])

function readStoredActivity(): ActivityItem[] {
  if (typeof window === "undefined") return []
  try {
    const value = window.localStorage.getItem(ACTIVITY_STORAGE_KEY)
    return value ? JSON.parse(value) as ActivityItem[] : []
  } catch {
    return []
  }
}

function storeActivity(items: ActivityItem[]) {
  if (typeof window === "undefined") return
  window.localStorage.setItem(ACTIVITY_STORAGE_KEY, JSON.stringify(items.slice(0, 30)))
}

function formatActivityTime(value?: string) {
  const date = value ? new Date(value) : new Date()
  if (Number.isNaN(date.getTime())) return "now"
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
}

export function CommandBar() {
  const [status, setStatus] = useState<VoiceStatus>("idle")
  const [statusMessage, setStatusMessage] = useState("Tap to speak")
  const [isActivityOpen, setIsActivityOpen] = useState(false)
  const [activities, setActivities] = useState<ActivityItem[]>([])
  const [conversations, setConversations] = useState<ConversationRecord[]>([])
  const [settings, setSettings] = useState<VoiceSettingsRecord | null>(null)
  const [browserVoices, setBrowserVoices] = useState(() => new BrowserTTSProvider().getVoices())
  const [activityError, setActivityError] = useState("")
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const streamRef = useRef<MediaStream | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const silenceLoopRef = useRef<number | null>(null)
  const stoppedRef = useRef(false)
  const selectedVoice = settings?.preferred_voice ?? browserVoices[0]?.id ?? null

  const activeAgents = useMemo(
    () => ceaserAgents.filter((agent) => agent.id !== "ceaser" && (agent.status === "active" || agent.status === "busy")).slice(0, 4),
    [],
  )

  useEffect(() => {
    setActivities(readStoredActivity())
    void voiceApi.getSettings().then(setSettings).catch(() => setSettings(null))
    if (typeof window === "undefined" || !window.speechSynthesis) return
    const loadVoices = () => setBrowserVoices(new BrowserTTSProvider().getVoices())
    loadVoices()
    window.speechSynthesis.onvoiceschanged = loadVoices
    return () => {
      window.speechSynthesis.onvoiceschanged = null
      stopRecording()
    }
  }, [])

  useEffect(() => {
    const onStartVoice = () => {
      if (status !== "listening") void startListening()
    }
    window.addEventListener(WEB_VOICE_HOTKEY_EVENT, onStartVoice)
    return () => window.removeEventListener(WEB_VOICE_HOTKEY_EVENT, onStartVoice)
  }, [status, settings])

  async function refreshActivity() {
    setActivityError("")
    setActivities(readStoredActivity())
    try {
      const [chatRecords] = await Promise.all([
        chatApi.listConversations(false).catch(() => []),
      ])
      setConversations(chatRecords)
    } catch {
      setActivityError("Recent activity could not fully refresh.")
    }
  }

  function addActivity(item: Omit<ActivityItem, "id" | "timestamp">) {
    const next = [
      {
        ...item,
        id: `${item.type}-${Date.now()}`,
        timestamp: new Date().toISOString(),
      },
      ...readStoredActivity(),
    ].slice(0, 30)
    storeActivity(next)
    setActivities(next)
  }

  function cleanupAudio() {
    if (silenceLoopRef.current) {
      window.cancelAnimationFrame(silenceLoopRef.current)
      silenceLoopRef.current = null
    }
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    void audioContextRef.current?.close().catch(() => undefined)
    audioContextRef.current = null
  }

  function stopRecording() {
    if (stoppedRef.current) return
    stoppedRef.current = true
    if (recorderRef.current?.state === "recording") {
      recorderRef.current.stop()
    } else {
      cleanupAudio()
    }
  }

  function monitorSilence(stream: MediaStream) {
    const AudioContextClass = window.AudioContext || (window as Window & typeof globalThis & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!AudioContextClass) return
    const audioContext = new AudioContextClass()
    const analyser = audioContext.createAnalyser()
    analyser.fftSize = 1024
    audioContext.createMediaStreamSource(stream).connect(analyser)
    audioContextRef.current = audioContext
    const data = new Uint8Array(analyser.frequencyBinCount)
    const startedAt = Date.now()
    let speechStarted = false
    let lastVoiceAt = Date.now()

    const tick = () => {
      analyser.getByteFrequencyData(data)
      const average = data.reduce((sum, value) => sum + value, 0) / data.length
      const now = Date.now()
      if (average > 8) {
        speechStarted = true
        lastVoiceAt = now
      }
      const heardCommandAndQuiet = speechStarted && now - lastVoiceAt > 1100
      const waitedForSpeech = !speechStarted && now - startedAt > 5000
      const maxReached = now - startedAt > 15000
      if (heardCommandAndQuiet || waitedForSpeech || maxReached) {
        stopRecording()
        return
      }
      silenceLoopRef.current = window.requestAnimationFrame(tick)
    }
    silenceLoopRef.current = window.requestAnimationFrame(tick)
  }

  async function handleVoiceResponse(response: VoiceRespondResponse) {
    setStatus("processing")
    addActivity({
      type: "voice",
      title: response.transcript || "Voice command",
      description: response.chat.response.slice(0, 160),
      status: response.chat.selected_agents.join(", ") || "CEASER",
    })
    window.dispatchEvent(new CustomEvent<VoiceRespondResponse>(FOOTER_VOICE_EVENT, { detail: response }))

    const useElevenLabs = settings?.voice_provider !== "browser" && response.audio_base64
    if (useElevenLabs) {
      setStatus("speaking")
      playVoiceAudio(response.audio_base64, response.audio_content_type ?? "audio/mpeg")
    } else if (response.spoken_summary) {
      const fallbackStarted = speakWithBrowserVoice(response.spoken_summary, selectedVoice, {
        rate: settings?.speech_speed ?? 1,
        volume: settings?.speech_volume ?? 1,
        lang: settings?.language ?? "en",
      })
      if (fallbackStarted) setStatus("speaking")
    }
    setStatus("ready")
    setStatusMessage("Ready")
  }

  async function handleTranscript(transcript: string) {
    setStatus("processing")
    setStatusMessage("Routing command...")
    const intent = await desktopApi.classify(transcript).catch(() => null)
    if (intent && DESKTOP_ACTIONS.has(intent.intent)) {
      const title = String(intent.result_preview?.title || intent.action.replace(/_/g, " "))
      const summary = String(intent.result_preview?.summary || "Local desktop actions run from the CEASER overlay.")
      addActivity({
        type: intent.intent === "blocked" ? "system" : "voice",
        title: transcript,
        description: intent.intent === "blocked" ? summary : `${title}: open this from the CEASER desktop overlay to execute locally.`,
        status: intent.intent,
      })
      setStatus(intent.intent === "blocked" ? "error" : "ready")
      setStatusMessage(intent.intent === "blocked" ? "Action blocked" : "Use desktop overlay")
      return
    }

    const chat = await chatApi.sendCeaserMessage(transcript)
    await handleVoiceResponse({
      session_id: `footer-${Date.now()}`,
      transcript,
      chat,
      spoken_summary: chat.response,
      audio_base64: null,
      audio_content_type: null,
      voice_warning: null,
    })
  }

  async function startListening() {
    if (status === "listening") {
      stopRecording()
      return
    }
    if (settings?.voice_enabled === false) {
      setStatus("error")
      setStatusMessage("Voice is disabled")
      return
    }
    setStatus("listening")
    setStatusMessage("Listening...")
    stoppedRef.current = false
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      const mimeType = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : ""
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream)
      chunksRef.current = []
      recorder.ondataavailable = (event) => {
        if (event.data.size) chunksRef.current.push(event.data)
      }
      recorder.onstop = async () => {
        cleanupAudio()
        if (!chunksRef.current.length) {
          setStatus("ready")
          setStatusMessage("No command heard")
          return
        }
        setStatus("transcribing")
        setStatusMessage("Understanding command...")
        try {
          const audio = new Blob(chunksRef.current, { type: mimeType || "audio/webm" })
          const { transcript } = await voiceApi.transcribe(audio, settings?.language)
          if (!transcript.trim()) {
            setStatus("ready")
            setStatusMessage("No command heard")
            return
          }
          await handleTranscript(transcript.trim())
        } catch {
          setStatus("error")
          setStatusMessage("Voice command failed")
          addActivity({
            type: "system",
            title: "Voice command failed",
            description: "Check backend voice service and microphone permission.",
            status: "error",
          })
        }
      }
      recorderRef.current = recorder
      recorder.start()
      monitorSilence(stream)
    } catch {
      cleanupAudio()
      setStatus("error")
      setStatusMessage("Microphone permission denied")
    }
  }

  const isBusy = status === "listening" || status === "transcribing" || status === "processing" || status === "speaking"

  return (
    <>
      <div className="border-t border-border bg-background/80 backdrop-blur-sm">
        <div className="flex items-center justify-between px-6 py-3">
          <div className="flex items-center gap-3">
            <CeaserLogo size="sm" showText={false} />
            <div>
              <p className="text-sm font-medium">CEASER OS</p>
              <p className="text-xs text-muted-foreground">v1.0.0</p>
            </div>
          </div>

          <div className="flex flex-1 items-center justify-center gap-8">
            {activeAgents.map((agent) => (
              <div key={agent.id} className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: agent.color }} />
                <span className="text-sm font-medium">{agent.name}</span>
                <span className="max-w-32 truncate text-xs text-muted-foreground">
                  {agent.currentTask?.split(" ").slice(0, 3).join(" ")}...
                </span>
              </div>
            ))}
          </div>

          <div className="flex items-center gap-4">
            <button
              onClick={() => void startListening()}
              className="group relative flex flex-col items-center"
              aria-label={status === "listening" ? "Stop listening" : "Start voice command"}
            >
              <div className="mb-1 flex h-4 items-end gap-0.5">
                {[...Array(12)].map((_, i) => (
                  <div
                    key={i}
                    className={cn("w-0.5 rounded-full transition-all", isBusy ? "animate-pulse bg-primary" : "bg-primary/40 group-hover:bg-primary")}
                    style={{ height: `${8 + Math.sin(i * 0.5) * 6}px`, animationDelay: `${i * 50}ms` }}
                  />
                ))}
              </div>
              <div className={cn(
                "flex h-14 w-14 items-center justify-center rounded-full border-2 transition-all",
                isBusy
                  ? "border-primary bg-primary/20 shadow-lg shadow-primary/20"
                  : "border-primary/30 bg-primary/10 group-hover:border-primary group-hover:bg-primary/20 group-hover:shadow-lg group-hover:shadow-primary/20",
              )}>
                {status === "transcribing" || status === "processing" ? <Loader2 className="h-6 w-6 animate-spin text-primary" /> : <Mic className="h-6 w-6 text-primary" />}
              </div>
              <span className="mt-1 max-w-24 truncate text-xs text-muted-foreground">{statusMessage}</span>
            </button>

            <button
              onClick={() => {
                setIsActivityOpen(true)
                void refreshActivity()
              }}
              className="flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm transition-colors hover:bg-secondary"
            >
              <span>View Full Activity</span>
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {isActivityOpen && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/35 backdrop-blur-sm">
          <aside className="flex h-full w-full max-w-md flex-col border-l border-white/10 bg-[#050816]/95 shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/10 p-5">
              <div>
                <p className="text-lg font-semibold">Full Activity</p>
                <p className="text-xs text-muted-foreground">Recent CEASER commands and chats</p>
              </div>
              <button onClick={() => setIsActivityOpen(false)} className="rounded-xl p-2 text-muted-foreground transition hover:bg-white/10 hover:text-foreground">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="min-h-0 flex-1 space-y-6 overflow-y-auto p-5">
              {activityError && <p className="rounded-xl border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{activityError}</p>}
              <ActivitySection title="Recent Commands" icon={Activity}>
                {activities.length ? activities.slice(0, 8).map((item) => <ActivityRow key={item.id} item={item} />) : <EmptyActivity text="No footer commands yet." />}
              </ActivitySection>
              <ActivitySection title="Recent Chats" icon={MessageSquare}>
                {conversations.slice(0, 8).map((conversation) => (
                  <ActivityRow
                    key={conversation.id}
                    item={{
                      id: conversation.id,
                      type: "chat",
                      title: conversation.title,
                      description: `Chat created ${formatActivityTime(conversation.created_at)}`,
                      timestamp: conversation.created_at,
                      status: conversation.pinned ? "pinned" : "chat",
                    }}
                  />
                ))}
                {!conversations.length && <EmptyActivity text="No recent chats found." />}
              </ActivitySection>
            </div>
          </aside>
        </div>
      )}
    </>
  )
}

function ActivitySection({ title, icon: Icon, children }: { title: string; icon: LucideIcon; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2 text-sm font-semibold">
        <Icon className="h-4 w-4 text-primary" />
        {title}
      </div>
      <div className="space-y-2">{children}</div>
    </section>
  )
}

function ActivityRow({ item }: { item: ActivityItem }) {
  const icon = item.type === "chat" ? <MessageSquare className="h-4 w-4" /> : item.type === "voice" ? <Mic className="h-4 w-4" /> : <Bot className="h-4 w-4" />
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">{icon}</span>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <p className="line-clamp-1 text-sm font-medium">{item.title}</p>
            <span className="flex shrink-0 items-center gap-1 text-[11px] text-muted-foreground">
              <Clock3 className="h-3 w-3" />
              {formatActivityTime(item.timestamp)}
            </span>
          </div>
          <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{item.description}</p>
          {item.status && <p className="mt-2 text-[11px] uppercase tracking-wide text-primary">{item.status}</p>}
        </div>
      </div>
    </div>
  )
}

function EmptyActivity({ text }: { text: string }) {
  return <p className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm text-muted-foreground">{text}</p>
}

export { FOOTER_VOICE_EVENT }
