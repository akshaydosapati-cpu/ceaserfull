import { cn } from "@/lib/utils"
import type { VoiceStatus as VoiceState } from "@/lib/api/voice"

const labels: Record<VoiceState, string> = {
  idle: "Ready",
  listening: "Listening",
  transcribing: "Transcribing",
  processing: "Processing",
  speaking: "Speaking",
  ready: "Ready",
  error: "Voice unavailable",
}

export function VoiceStatus({ status, message }: { status: VoiceState; message?: string }) {
  return (
    <span className={cn("text-xs text-muted-foreground", status === "listening" && "text-primary", status === "error" && "text-destructive")}>
      {message || labels[status]}
    </span>
  )
}
