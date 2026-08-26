export function VoiceTranscript({ transcript }: { transcript?: string }) {
  if (!transcript) return null
  return <p className="truncate text-xs text-muted-foreground">Heard: {transcript}</p>
}
