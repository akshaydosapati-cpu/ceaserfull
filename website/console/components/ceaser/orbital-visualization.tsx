"use client"

import { agents, type Agent } from "@/lib/data"
import { useAgentStore } from "@/lib/stores/agent-store"
import { cn } from "@/lib/utils"
import { motion } from "framer-motion"

interface OrbitalVisualizationProps {
  className?: string
  selectedAgentId?: string | null
  onAgentClick?: (agent: Agent) => void
}

export function OrbitalVisualization({ className, selectedAgentId, onAgentClick }: OrbitalVisualizationProps) {
  const { isAgentEnabled } = useAgentStore()
  const activeAgents = agents.filter((agent) => isAgentEnabled(agent.id))

  const agentPositions = [
    { angle: -60, radius: 172, agent: agents.find((agent) => agent.id === "bolt") },
    { angle: -120, radius: 172, agent: agents.find((agent) => agent.id === "alex") },
    { angle: 180, radius: 172, agent: agents.find((agent) => agent.id === "friday") },
    { angle: 120, radius: 188, agent: agents.find((agent) => agent.id === "zeus") },
    { angle: 60, radius: 172, agent: agents.find((agent) => agent.id === "atlas") },
    { angle: 0, radius: 188, agent: agents.find((agent) => agent.id === "nova") },
  ]

  return (
    <div className={cn("relative flex items-center justify-center", className)}>
      <div className="absolute inset-0 neural-grid opacity-30" />

      <svg className="absolute inset-0 h-full w-full" viewBox="0 0 440 440">
        <defs>
          <linearGradient id="ringGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#0284c7" stopOpacity="0.48" />
            <stop offset="45%" stopColor="#4f8cff" stopOpacity="0.24" />
            <stop offset="100%" stopColor="#7c5cff" stopOpacity="0.48" />
          </linearGradient>
          <linearGradient id="sweepGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#00d4ff" stopOpacity="0" />
            <stop offset="55%" stopColor="#00d4ff" stopOpacity="0.55" />
            <stop offset="100%" stopColor="#7c5cff" stopOpacity="0.85" />
          </linearGradient>
          <filter id="glow">
            <feGaussianBlur stdDeviation="4" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <circle
          cx="220"
          cy="220"
          r="188"
          fill="none"
          stroke="url(#ringGradient)"
          strokeWidth="1.7"
          strokeDasharray="5 5"
          className="animate-[spin_36s_linear_infinite]"
          style={{ transformOrigin: "center" }}
        />

        <circle
          cx="220"
          cy="220"
          r="144"
          fill="none"
          stroke="url(#ringGradient)"
          strokeWidth="1.35"
          strokeDasharray="3 7"
          className="animate-[spin_28s_linear_infinite_reverse]"
          style={{ transformOrigin: "center" }}
        />

        <circle
          cx="220"
          cy="220"
          r="188"
          fill="none"
          stroke="url(#sweepGradient)"
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray="82 925"
          filter="url(#glow)"
          className="animate-[spin_12s_linear_infinite]"
          style={{ transformOrigin: "center" }}
        />

        {activeAgents.map((agent) => {
          const pos = agentPositions.find((item) => item.agent?.id === agent.id)
          if (!pos || selectedAgentId === agent.id) return null
          const x = 220 + pos.radius * Math.cos((pos.angle * Math.PI) / 180)
          const y = 220 + pos.radius * Math.sin((pos.angle * Math.PI) / 180)
          return (
            <line
              key={agent.id}
              x1="220"
              y1="220"
              x2={x}
              y2={y}
              stroke={agent.color}
              strokeWidth="1.4"
              strokeOpacity="0.48"
              strokeDasharray="4 4"
              filter="url(#glow)"
            />
          )
        })}
      </svg>

      <motion.div
        className="relative z-10 flex h-32 w-32 items-center justify-center"
        animate={{ scale: [1, 1.02, 1] }}
        transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
      >
        <div className="absolute inset-0 rounded-full bg-gradient-to-br from-primary/20 to-primary/5 blur-xl" />
        <div className="absolute inset-2 rounded-full bg-gradient-to-br from-primary/30 to-transparent" />
        <div className="relative flex h-24 w-24 items-center justify-center rounded-full border border-primary/30 bg-background/80 backdrop-blur-sm glow-primary">
          <span className="text-4xl font-bold text-primary glow-text-primary">C</span>
        </div>
      </motion.div>

      {agentPositions.map(({ angle, radius, agent }) => {
        if (!agent) return null
        const Icon = agent.icon
        const x = radius * Math.cos((angle * Math.PI) / 180)
        const y = radius * Math.sin((angle * Math.PI) / 180)
        const isSelected = selectedAgentId === agent.id
        const showStatusDot = isAgentEnabled(agent.id)

        return (
          <motion.button
            key={agent.id}
            type="button"
            className={cn("absolute z-20 cursor-pointer", isSelected && "z-30")}
            initial={false}
            animate={{ x, y: y - (isSelected ? 8 : 0), scale: isSelected ? 1.18 : 1 }}
            transition={{ type: "spring", stiffness: 260, damping: 24 }}
            whileHover={{ scale: isSelected ? 1.26 : 1.06 }}
            onClick={() => onAgentClick?.(agent)}
          >
            <div className={cn("flex flex-col items-center gap-1", isSelected && "gap-2") }>
              <div
                className={cn(
                  "relative flex h-12 w-12 items-center justify-center rounded-xl transition-all duration-300",
                  isSelected && "h-14 w-14 rounded-2xl ring-2 ring-primary ring-offset-2 ring-offset-background",
                )}
                style={{
                  backgroundColor: `${agent.color}20`,
                  boxShadow:
                    isAgentEnabled(agent.id)
                      ? `0 0 20px ${agent.color}40, 0 0 40px ${agent.color}20`
                      : undefined,
                }}
              >
                <Icon className="h-6 w-6" style={{ color: agent.color }} />
                {showStatusDot && (
                  <div className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-background bg-emerald-500" />
                )}
              </div>
              <span className={cn("text-xs font-medium text-foreground transition-all duration-300", isSelected && "text-sm font-semibold")}>{agent.name}</span>
            </div>
          </motion.button>
        )
      })}
    </div>
  )
}
