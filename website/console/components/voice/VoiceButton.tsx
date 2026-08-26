import { Loader2, Mic, Square } from "lucide-react"
import { cn } from "@/lib/utils"
import type { VoiceStatus } from "@/lib/api/voice"

export function VoiceButton({ status, disabled, onClick }: { status: VoiceStatus; disabled?: boolean; onClick: () => void }) {
  const listening = status === "listening"
  const busy = status === "processing" || status === "speaking"
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || busy}
      className={cn(
        "flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground disabled:opacity-50",
        listening && "bg-primary/15 text-primary",
      )}
      aria-label={listening ? "Stop voice input" : "Start voice input"}
    >
      {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : listening ? <Square className="h-4 w-4" /> : <Mic className="h-5 w-5" />}
    </button>
  )
}
