"use client"

import { cn } from "@/lib/utils"
import { type ReactNode } from "react"

interface GlowCardProps {
  children: ReactNode
  className?: string
  glowColor?: string
  hover?: boolean
  onClick?: () => void
}

export function GlowCard({ 
  children, 
  className, 
  glowColor,
  hover = false,
  onClick
}: GlowCardProps) {
  return (
    <div
      className={cn(
        "glass-card rounded-2xl p-4 transition-all duration-300",
        hover && "glass-card-hover cursor-pointer",
        onClick && "cursor-pointer",
        className
      )}
      style={glowColor ? {
        boxShadow: `0 0 20px ${glowColor}20, inset 0 1px 0 rgba(255,255,255,0.05)`
      } : undefined}
      onClick={onClick}
    >
      {children}
    </div>
  )
}

interface StatCardProps {
  icon: ReactNode
  label: string
  value: string | number
  className?: string
}

export function StatCard({ icon, label, value, className }: StatCardProps) {
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-secondary/50">
        {icon}
      </div>
      <div>
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-xl font-semibold">{value}</p>
      </div>
    </div>
  )
}
