"use client"

import { cn } from "@/lib/utils"
import type { ReactNode } from "react"

interface SpatialCardProps {
  children: ReactNode
  className?: string
  elevated?: boolean
  interactive?: boolean
}

export function SpatialCard({ children, className, elevated = false, interactive = false }: SpatialCardProps) {
  return (
    <section
      className={cn(
        elevated ? "spatial-panel-elevated" : "spatial-panel",
        "rounded-2xl transition-all duration-300",
        interactive && "hover:-translate-y-0.5 hover:border-primary/35 hover:shadow-[0_28px_80px_rgba(0,0,0,0.38)]",
        className,
      )}
    >
      {children}
    </section>
  )
}

interface StatusBadgeProps {
  children: ReactNode
  tone?: "blue" | "purple" | "green" | "amber" | "red" | "muted"
  className?: string
}

export function StatusBadge({ children, tone = "blue", className }: StatusBadgeProps) {
  const tones = {
    blue: "border-primary/25 bg-primary/10 text-primary",
    purple: "border-accent/25 bg-accent/10 text-[#a99cff]",
    green: "border-emerald-400/25 bg-emerald-400/10 text-emerald-300",
    amber: "border-amber-400/25 bg-amber-400/10 text-amber-300",
    red: "border-red-400/25 bg-red-400/10 text-red-300",
    muted: "border-slate-400/15 bg-slate-400/10 text-slate-300",
  }
  return (
    <span className={cn("inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium", tones[tone], className)}>
      {children}
    </span>
  )
}
