"use client"

import { type CeaserAgent } from "@/lib/ceaser"
import { cn } from "@/lib/utils"

interface AgentAvatarProps {
  agent: CeaserAgent
  size?: "sm" | "md" | "lg" | "xl"
  showStatus?: boolean
  enabled?: boolean
  showGlow?: boolean
  className?: string
}

const sizeClasses = {
  sm: "h-8 w-8",
  md: "h-10 w-10",
  lg: "h-12 w-12",
  xl: "h-16 w-16",
}

const iconSizeClasses = {
  sm: "h-4 w-4",
  md: "h-5 w-5",
  lg: "h-6 w-6",
  xl: "h-8 w-8",
}

const statusSizeClasses = {
  sm: "h-2 w-2",
  md: "h-2.5 w-2.5",
  lg: "h-3 w-3",
  xl: "h-3.5 w-3.5",
}

export function AgentAvatar({
  agent,
  size = "md",
  showStatus = false,
  enabled = true,
  showGlow = false,
  className,
}: AgentAvatarProps) {
  const Icon = agent.icon

  return (
    <div className={cn("relative", className)}>
      <div
        className={cn(
          "flex items-center justify-center rounded-xl transition-all duration-300",
          sizeClasses[size],
          showGlow && enabled && "shadow-lg",
        )}
        style={{
          backgroundColor: `${agent.color}20`,
          boxShadow:
            showGlow && enabled
              ? `0 0 20px ${agent.color}40, 0 0 40px ${agent.color}20`
              : undefined,
        }}
      >
        <Icon className={iconSizeClasses[size]} style={{ color: agent.color }} />
      </div>
      {showStatus && enabled && (
        <div
          className={cn(
            "absolute -bottom-0.5 -right-0.5 rounded-full border-2 border-background bg-emerald-500",
            statusSizeClasses[size],
          )}
        />
      )}
    </div>
  )
}

