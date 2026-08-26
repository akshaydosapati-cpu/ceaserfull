import type { VoiceSettingsRecord } from "@/lib/api/voice"

export function VoiceSettings({ settings }: { settings?: VoiceSettingsRecord | null }) {
  if (!settings) return null
  return (
    <div className="rounded-lg border border-border bg-secondary/20 p-3 text-sm">
      <p className="font-medium">Voice</p>
      <p className="mt-1 text-xs text-muted-foreground">Language: {settings.language}</p>
    </div>
  )
}
