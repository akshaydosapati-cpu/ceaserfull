"use client"

import { CheckCircle2, Clock, AlertCircle, Loader2, ChevronDown, ChevronUp } from "lucide-react"
import { useState } from "react"
import type { WorkflowResult } from "@/lib/api/chat"

interface WorkflowCardProps {
  workflow: WorkflowResult
  isStreaming?: boolean
}

export function WorkflowCard({ workflow, isStreaming }: WorkflowCardProps) {
  const [expanded, setExpanded] = useState(false)

  const statusIcon = {
    pending: <Clock className="h-4 w-4 text-slate-400" />,
    running: <Loader2 className="h-4 w-4 animate-spin text-blue-400" />,
    completed: <CheckCircle2 className="h-4 w-4 text-emerald-400" />,
    failed: <AlertCircle className="h-4 w-4 text-rose-400" />,
    waiting_for_user: <Clock className="h-4 w-4 text-amber-400" />,
  } as const

  const statusColor = {
    pending: "text-slate-400",
    running: "text-blue-400",
    completed: "text-emerald-400",
    failed: "text-rose-400",
    waiting_for_user: "text-amber-400",
  } as const

  const stepStatusLabel = (status: string) => {
    switch (status) {
      case "pending":
        return "Pending"
      case "running":
        return "Running"
      case "completed":
        return "Completed"
      case "failed":
        return "Failed"
      case "waiting_for_user":
        return "Waiting for confirmation"
      default:
        return status
    }
  }

  const completedSteps = workflow.steps?.filter((s) => s.status === "completed").length || 0
  const totalSteps = workflow.steps?.length || 0
  const progressPercent = totalSteps > 0 ? (completedSteps / totalSteps) * 100 : 0

  return (
    <div className="rounded-lg border border-blue-400/20 bg-blue-500/[0.05] overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between gap-3 px-4 py-3 hover:bg-blue-500/[0.08] transition-colors"
      >
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <div className="flex items-center gap-2">
            {isStreaming || workflow.status === "running" ? (
              <Loader2 className="h-4 w-4 animate-spin text-blue-400 flex-shrink-0" />
            ) : workflow.status === "completed" ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-400 flex-shrink-0" />
            ) : workflow.status === "failed" ? (
              <AlertCircle className="h-4 w-4 text-rose-400 flex-shrink-0" />
            ) : (
              <Clock className="h-4 w-4 text-slate-400 flex-shrink-0" />
            )}
          </div>
          <div className="min-w-0 flex-1 text-left">
            <p className="text-sm font-medium text-white truncate">
              {workflow.type?.replace(/_/g, " ") || "Workflow"}
            </p>
            <p className="text-xs text-white/55 mt-0.5">
              {completedSteps} of {totalSteps} steps complete
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <div className="text-right">
            <div className="w-12 h-1 bg-white/10 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-400 transition-all duration-300"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>
          {expanded ? (
            <ChevronUp className="h-4 w-4 text-white/50" />
          ) : (
            <ChevronDown className="h-4 w-4 text-white/50" />
          )}
        </div>
      </button>

      {expanded && (
        <div className="border-t border-blue-400/10 px-4 py-3 space-y-3 bg-blue-500/[0.02]">
          {workflow.summary && (
            <div>
              <p className="text-xs text-white/50 uppercase tracking-wide mb-1">Status</p>
              <p className="text-sm text-white/75">{workflow.summary}</p>
            </div>
          )}

          {workflow.steps && workflow.steps.length > 0 && (
            <div>
              <p className="text-xs text-white/50 uppercase tracking-wide mb-2">Steps</p>
              <div className="space-y-2">
                {workflow.steps.map((step, index) => (
                  <div key={step.id || index} className="flex items-start gap-3">
                    <div className="pt-0.5 flex-shrink-0">
                      {statusIcon[step.status as keyof typeof statusIcon] || (
                        <div className="h-4 w-4 rounded-full border border-slate-400" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <p className="text-sm text-white/75">
                          {step.agent_name || `Step ${index + 1}`}
                        </p>
                        <span
                          className={`text-xs ${statusColor[step.status as keyof typeof statusColor] || "text-slate-400"}`}
                        >
                          {stepStatusLabel(step.status)}
                        </span>
                      </div>
                      {step.output_summary && (
                        <p className="text-xs text-white/50 mt-1 line-clamp-2">{step.output_summary}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
