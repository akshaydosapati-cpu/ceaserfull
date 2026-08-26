import { cn } from "@/lib/utils"
import type { VoiceStatus } from "@/lib/api/voice"

export function VoiceVisualizer({ status }: { status: VoiceStatus }) {
  const active = status === "listening" || status === "transcribing" || status === "speaking" || status === "processing"
  return (
    <div className="flex h-5 items-center gap-0.5">
      {[0, 1, 2, 3].map((item) => (
        <span
          key={item}
          className={cn("h-1 w-1 rounded-full bg-muted-foreground/60 transition-all", active && "animate-pulse bg-primary", active && item % 2 === 0 && "h-4", active && item % 2 === 1 && "h-3")}
        />
      ))}
    </div>
  )
}
