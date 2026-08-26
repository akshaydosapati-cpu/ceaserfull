"use client"

import { agents, type Agent } from "@/lib/data"
import { cn } from "@/lib/utils"
import { motion } from "framer-motion"

interface OrbitalVisualizationProps {
  className?: string
  onAgentClick?: (agent: Agent) => void
}

export function OrbitalVisualization({ className, onAgentClick }: OrbitalVisualizationProps) {
  const activeAgents = agents.filter(a => a.status === "active")
  
  // Position agents in orbital positions around the center
  const agentPositions = [
    { angle: -60, radius: 140, agent: agents.find(a => a.id === "bolt") },
    { angle: -120, radius: 140, agent: agents.find(a => a.id === "alex") },
    { angle: 180, radius: 140, agent: agents.find(a => a.id === "friday") },
    { angle: 120, radius: 160, agent: agents.find(a => a.id === "zeus") },
    { angle: 60, radius: 140, agent: agents.find(a => a.id === "atlas") },
    { angle: 0, radius: 160, agent: agents.find(a => a.id === "nova") },
  ]

  return (
    <div className={cn("relative flex items-center justify-center", className)}>
      {/* Neural network background grid */}
      <div className="absolute inset-0 neural-grid opacity-30" />
      
      {/* Orbital rings */}
      <svg className="absolute inset-0 h-full w-full" viewBox="0 0 400 400">
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
            <feGaussianBlur stdDeviation="4" result="coloredBlur"/>
            <feMerge>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
        </defs>
        
        {/* Outer ring */}
        <circle
          cx="200"
          cy="200"
          r="160"
          fill="none"
          stroke="url(#ringGradient)"
          strokeWidth="1.7"
          strokeDasharray="5 5"
          className="animate-[spin_36s_linear_infinite]"
          style={{ transformOrigin: 'center' }}
        />
        
        {/* Inner ring */}
        <circle
          cx="200"
          cy="200"
          r="120"
          fill="none"
          stroke="url(#ringGradient)"
          strokeWidth="1.35"
          strokeDasharray="3 7"
          className="animate-[spin_28s_linear_infinite_reverse]"
          style={{ transformOrigin: 'center' }}
        />

        {/* Visible rotating sweep */}
        <circle
          cx="200"
          cy="200"
          r="160"
          fill="none"
          stroke="url(#sweepGradient)"
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray="82 925"
          filter="url(#glow)"
          className="animate-[spin_12s_linear_infinite]"
          style={{ transformOrigin: 'center' }}
        />
        
        {/* Neural connection lines */}
        {activeAgents.map((agent, i) => {
          const pos = agentPositions.find(p => p.agent?.id === agent.id)
          if (!pos) return null
          const x = 200 + pos.radius * Math.cos((pos.angle * Math.PI) / 180)
          const y = 200 + pos.radius * Math.sin((pos.angle * Math.PI) / 180)
          return (
            <line
              key={agent.id}
              x1="200"
              y1="200"
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

      {/* Center CEASER logo */}
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

      {/* Agent nodes */}
      {agentPositions.map(({ angle, radius, agent }) => {
        if (!agent) return null
        const x = radius * Math.cos((angle * Math.PI) / 180)
        const y = radius * Math.sin((angle * Math.PI) / 180)
        const Icon = agent.icon
        
        return (
          <motion.div
            key={agent.id}
            className="absolute z-20 cursor-pointer"
            style={{
              transform: `translate(${x}px, ${y}px)`,
            }}
            whileHover={{ scale: 1.1 }}
            onClick={() => onAgentClick?.(agent)}
          >
            <div className="flex flex-col items-center gap-1">
              <div 
                className="relative flex h-12 w-12 items-center justify-center rounded-xl transition-all duration-300"
                style={{ 
                  backgroundColor: `${agent.color}20`,
                  boxShadow: agent.status === "active" 
                    ? `0 0 20px ${agent.color}40, 0 0 40px ${agent.color}20` 
                    : undefined
                }}
              >
                <Icon className="h-6 w-6" style={{ color: agent.color }} />
                {agent.status === "active" && (
                  <div 
                    className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-background bg-emerald-500"
                  />
                )}
              </div>
              <span className="text-xs font-medium text-foreground">{agent.name}</span>
            </div>
          </motion.div>
        )
      })}
    </div>
  )
}
