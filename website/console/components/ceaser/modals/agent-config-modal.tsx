"use client"

import { useApp } from "@/lib/app-context"
import { agents } from "@/lib/data"
import { useAgentStore, agentModuleRegistry } from "@/lib/stores/agent-store"
import { cn } from "@/lib/utils"
import { motion, AnimatePresence } from "framer-motion"
import { X, ChevronLeft, ChevronRight, Check, Power } from "lucide-react"
import { useState, useEffect } from "react"

// Module icons mapping
const moduleIcons: Record<string, string> = {
  // Zeus
  ceo: "👔", cto: "💻", cfo: "📊", coo: "⚙️", marketing: "📣", hr: "👥", sales: "💰", analytics: "📈",
  // Alex
  goals: "🎯", learning: "📚", productivity: "⏱️", health: "💪", travel: "✈️", finance: "💵",
  // Friday
  instagram: "📸", linkedin: "💼", youtube: "🎬", email: "📧", blog: "✍️", "content-planning": "📅",
  // Nova
  research: "🔬", "competitor-analysis": "🔍", "market-analysis": "📈", "trend-monitoring": "📡", reports: "📑",
  // Atlas
  coding: "👨‍💻", architecture: "🏗️", infrastructure: "☁️", devops: "🔧", "code-review": "👀", debugging: "🐛",
  // Bolt
  tasks: "✅", scheduling: "📆", automation: "⚡", reminders: "🔔", "workflow-execution": "🔄"
}

export function AgentConfigModal() {
  const { isAgentConfigOpen, setIsAgentConfigOpen, configAgentId } = useApp()
  const { initializeAgent, getAgentModules, toggleModuleEnabled, isAgentEnabled, toggleAgentEnabled, getAgentState, updateAgentSettings } = useAgentStore()
  const [step, setStep] = useState(1)
  const [localModules, setLocalModules] = useState<Record<string, boolean>>({})
  const [customName, setCustomName] = useState("")
  const [customDescription, setCustomDescription] = useState("")
  
  const agent = agents.find(a => a.id === configAgentId)

  // Initialize agent modules when modal opens
  useEffect(() => {
    if (configAgentId && isAgentConfigOpen) {
      initializeAgent(configAgentId)
      const modules = getAgentModules(configAgentId)
      const moduleState: Record<string, boolean> = {}
      modules.forEach(m => { moduleState[m.id] = m.enabled })
      setLocalModules(moduleState)
      const state = getAgentState(configAgentId)
      const selectedAgent = agents.find((item) => item.id === configAgentId)
      setCustomName(state?.customName || selectedAgent?.name || "")
      setCustomDescription(state?.customDescription || selectedAgent?.description || "")
    }
  }, [configAgentId, isAgentConfigOpen, initializeAgent, getAgentModules, getAgentState])

  const agentModules = configAgentId ? agentModuleRegistry[configAgentId] || [] : []

  const toggleModule = (moduleId: string) => {
    setLocalModules(prev => ({
      ...prev,
      [moduleId]: !prev[moduleId]
    }))
  }

  const handleSave = () => {
    if (configAgentId) {
      // Sync local changes to store
      Object.entries(localModules).forEach(([moduleId, enabled]) => {
        const currentState = getAgentModules(configAgentId).find(m => m.id === moduleId)
        if (currentState && currentState.enabled !== enabled) {
          toggleModuleEnabled(configAgentId, moduleId)
        }
      })
      updateAgentSettings(configAgentId, {
        customName: customName.trim(),
        customDescription: customDescription.trim(),
      })
    }
    handleClose()
  }

  const handleClose = () => {
    setIsAgentConfigOpen(false)
    setStep(1)
    setLocalModules({})
  }

  if (!agent) return null

  const agentEnabled = isAgentEnabled(agent.id)
  const selectedCount = Object.values(localModules).filter(Boolean).length

  return (
    <AnimatePresence>
      {isAgentConfigOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm"
          onClick={handleClose}
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
            className="relative w-full max-w-lg overflow-hidden rounded-xl border border-border bg-card shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-border px-6 py-4">
              <button
                onClick={() => step > 1 ? setStep(step - 1) : handleClose()}
                className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
              >
                <ChevronLeft className="h-4 w-4" />
                Configure {agent.name}
              </button>
              <span className="text-sm text-muted-foreground">Step {step} of 2</span>
            </div>

            {/* Content */}
            <div className="max-h-[60vh] overflow-y-auto p-6">
              {step === 1 && (
                <>
                  {/* Agent Enable/Disable Toggle */}
                  <div className="mb-6 flex items-center justify-between rounded-xl border border-border p-4">
                    <div className="flex items-center gap-3">
                      <div 
                        className="flex h-10 w-10 items-center justify-center rounded-lg"
                        style={{ backgroundColor: `${agent.color}20` }}
                      >
                        <Power className="h-5 w-5" style={{ color: agent.color }} />
                      </div>
                      <div>
                        <p className="font-medium">{agent.name} Agent</p>
                        <p className="text-xs text-muted-foreground">
                          {agentEnabled ? "Agent is enabled" : "Agent is disabled"}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => toggleAgentEnabled(agent.id)}
                      className={cn(
                        "relative h-6 w-11 rounded-full transition-colors",
                        agentEnabled ? "bg-primary" : "bg-muted"
                      )}
                    >
                      <div
                        className={cn(
                          "absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform",
                          agentEnabled ? "left-[22px]" : "left-0.5"
                        )}
                      />
                    </button>
                  </div>

                  <h2 className="mb-2 text-xl font-semibold">Select modules for {agent.name}</h2>
                  <p className="mb-4 text-sm text-muted-foreground">
                    Choose the functions {agent.name} should handle. ({selectedCount} selected)
                  </p>
                  
                  <div className="grid grid-cols-2 gap-3">
                    {agentModules.map((module) => {
                      const isSelected = localModules[module.id] ?? true
                      return (
                        <button
                          key={module.id}
                          onClick={() => toggleModule(module.id)}
                          disabled={!agentEnabled}
                          className={cn(
                            "relative flex items-start gap-3 rounded-xl border p-3 text-left transition-all",
                            !agentEnabled && "opacity-50 cursor-not-allowed",
                            isSelected 
                              ? "border-primary bg-primary/10" 
                              : "border-border hover:border-muted-foreground"
                          )}
                        >
                          {isSelected && (
                            <div className="absolute right-2 top-2 flex h-5 w-5 items-center justify-center rounded-full bg-primary">
                              <Check className="h-3 w-3 text-primary-foreground" />
                            </div>
                          )}
                          <div 
                            className="flex h-10 w-10 items-center justify-center rounded-lg"
                            style={{ backgroundColor: `${agent.color}20` }}
                          >
                            <span className="text-lg">{moduleIcons[module.id] || "📦"}</span>
                          </div>
                          <div className="flex-1 pr-6">
                            <p className="font-medium">{module.name}</p>
                            <p className="text-xs text-muted-foreground">{module.description}</p>
                          </div>
                        </button>
                      )
                    })}
                  </div>
                </>
              )}

              {step === 2 && (
                <>
                  <h2 className="mb-2 text-xl font-semibold">Customize {agent.name}</h2>
                  <p className="mb-6 text-sm text-muted-foreground">
                    Fine-tune how {agent.name} operates.
                  </p>
                  
                  <div className="space-y-4">
                    <div>
                      <label className="mb-2 block text-sm font-medium">Agent Name</label>
                      <input
                        type="text"
                        value={customName}
                        onChange={(event) => setCustomName(event.target.value)}
                        className="w-full rounded-lg border border-border bg-background px-4 py-2 outline-none focus:border-primary"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-sm font-medium">Description</label>
                      <textarea
                        value={customDescription}
                        onChange={(event) => setCustomDescription(event.target.value)}
                        rows={3}
                        className="w-full rounded-lg border border-border bg-background px-4 py-2 outline-none focus:border-primary resize-none"
                      />
                    </div>
                  </div>
                </>
              )}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between border-t border-border px-6 py-4">
              <button
                onClick={handleClose}
                className="rounded-lg border border-border px-4 py-2 text-sm transition-colors hover:bg-secondary"
              >
                Cancel
              </button>
              <button
                onClick={() => step === 1 ? setStep(2) : handleSave()}
                className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
              >
                {step === 1 ? "Next: Customize" : "Save Configuration"}
                {step === 1 && <ChevronRight className="h-4 w-4" />}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
