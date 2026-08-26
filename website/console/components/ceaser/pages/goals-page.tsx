"use client"

import { useState } from "react"
import { agents } from "@/lib/data"
import { useTaskGoalStore } from "@/lib/stores/task-goal-store"
import { AgentAvatar } from "../agent-avatar"
import { CeaserSelect } from "../ceaser-select"
import { GlowCard } from "../glow-card"
import { cn } from "@/lib/utils"
import { Plus, Target, CheckCircle2, Circle, ChevronRight, X, Trash2 } from "lucide-react"
import { motion, AnimatePresence } from "framer-motion"

export function GoalsPage() {
  const { 
    goals, 
    addGoal, 
    updateGoal, 
    deleteGoal, 
    toggleMilestone 
  } = useTaskGoalStore()
  
  const [activeFilter, setActiveFilter] = useState<"all" | "in-progress" | "completed">("all")
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const [selectedGoalId, setSelectedGoalId] = useState<string | null>(null)
  const [newGoal, setNewGoal] = useState({
    title: "",
    description: "",
    targetDate: "",
    agentId: ""
  })

  const filteredGoals = goals.filter(g => {
    if (activeFilter === "all") return true
    if (activeFilter === "completed") return g.progress === 100
    return g.progress < 100
  })

  const selectedGoal = goals.find(g => g.id === selectedGoalId)

  const handleAddGoal = () => {
    if (newGoal.title.trim()) {
      addGoal({
        title: newGoal.title,
        description: newGoal.description,
        progress: 0,
        targetDate: newGoal.targetDate || undefined,
        agentId: newGoal.agentId || undefined,
        milestones: []
      })
      setNewGoal({ title: "", description: "", targetDate: "", agentId: "" })
      setIsAddModalOpen(false)
    }
  }

  return (
    <div className="flex h-full">
      {/* Goals List */}
      <div className={cn(
        "flex flex-col transition-all duration-300",
        selectedGoal ? "w-2/3 border-r border-border" : "flex-1"
      )}>
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <h1 className="text-xl font-semibold">Goals</h1>
          <button 
            onClick={() => setIsAddModalOpen(true)}
            className="flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" />
            New Goal
          </button>
        </div>

        {/* Filter Tabs */}
        <div className="flex gap-2 border-b border-border px-6 py-3">
          {(["all", "in-progress", "completed"] as const).map((filter) => (
            <button
              key={filter}
              onClick={() => setActiveFilter(filter)}
              className={cn(
                "rounded-lg px-4 py-2 text-sm capitalize transition-colors",
                activeFilter === filter
                  ? "bg-primary text-primary-foreground"
                  : "bg-secondary text-muted-foreground hover:text-foreground"
              )}
            >
              {filter === "in-progress" ? "In Progress" : filter}
            </button>
          ))}
        </div>

        {/* Goals List */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="space-y-4">
            {filteredGoals.map((goal) => {
              const agent = goal.agentId ? agents.find(a => a.id === goal.agentId) : null
              const isSelected = goal.id === selectedGoalId
              
              return (
                <GlowCard 
                  key={goal.id} 
                  hover 
                  glowColor={isSelected ? agent?.color : undefined}
                  onClick={() => setSelectedGoalId(goal.id)}
                  className={cn(
                    "cursor-pointer",
                    isSelected && "border-primary/50"
                  )}
                >
                  <div className="flex items-start gap-4">
                    <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
                      <Target className="h-6 w-6 text-primary" />
                    </div>
                    
                    <div className="flex-1">
                      <div className="mb-2 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <h3 className="text-lg font-semibold">{goal.title}</h3>
                          {agent && (
                            <AgentAvatar agent={agent} size="sm" showGlow={isSelected} />
                          )}
                        </div>
                        {goal.targetDate && (
                          <span className="text-sm text-muted-foreground">Due: {goal.targetDate}</span>
                        )}
                      </div>
                      {goal.description && (
                        <p className="mb-4 text-sm text-muted-foreground">{goal.description}</p>
                      )}

                      {/* Progress */}
                      <div className="mb-4 flex items-center gap-3">
                        <div className="h-2 flex-1 rounded-full bg-secondary">
                          <div 
                            className="h-full rounded-full transition-all"
                            style={{ 
                              width: `${goal.progress}%`,
                              backgroundColor: agent?.color || "#00d4ff"
                            }}
                          />
                        </div>
                        <span className="text-sm font-medium">{goal.progress}%</span>
                      </div>

                      {/* Milestones */}
                      {goal.milestones && goal.milestones.length > 0 && !selectedGoal && (
                        <div className="flex flex-wrap gap-2">
                          {goal.milestones.map((milestone) => (
                            <button 
                              key={milestone.id}
                              onClick={(e) => {
                                e.stopPropagation()
                                toggleMilestone(goal.id, milestone.id)
                              }}
                              className={cn(
                                "flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm transition-colors",
                                milestone.completed 
                                  ? "bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20" 
                                  : "bg-secondary text-muted-foreground hover:bg-secondary/80"
                              )}
                            >
                              {milestone.completed ? (
                                <CheckCircle2 className="h-4 w-4" />
                              ) : (
                                <Circle className="h-4 w-4" />
                              )}
                              {milestone.title}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>

                    <ChevronRight className="h-5 w-5 text-muted-foreground" />
                  </div>
                </GlowCard>
              )
            })}
          </div>
        </div>
      </div>

      {/* Goal Detail Panel */}
      {selectedGoal && (
        <div className="flex w-1/3 flex-col">
          <div className="flex items-center justify-between border-b border-border px-6 py-4">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setSelectedGoalId(null)}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
              >
                <X className="h-5 w-5" />
              </button>
              <h2 className="text-lg font-semibold">{selectedGoal.title}</h2>
            </div>
            <button
              onClick={() => {
                deleteGoal(selectedGoal.id)
                setSelectedGoalId(null)
              }}
              className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-red-500/10 hover:text-red-400"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-6">
            <div className="space-y-6">
              {/* Progress */}
              <div>
                <label className="mb-2 block text-sm font-medium">Progress ({selectedGoal.progress}%)</label>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={selectedGoal.progress}
                  onChange={(e) => updateGoal(selectedGoal.id, { progress: parseInt(e.target.value) })}
                  className="w-full accent-primary"
                />
              </div>

              {/* Milestones */}
              {selectedGoal.milestones && selectedGoal.milestones.length > 0 && (
                <div>
                  <label className="mb-3 block text-sm font-medium">Milestones</label>
                  <div className="space-y-2">
                    {selectedGoal.milestones.map((milestone) => (
                      <button
                        key={milestone.id}
                        onClick={() => toggleMilestone(selectedGoal.id, milestone.id)}
                        className={cn(
                          "flex w-full items-center gap-3 rounded-lg p-3 text-left transition-colors",
                          milestone.completed 
                            ? "bg-emerald-500/10 text-emerald-500" 
                            : "bg-secondary text-foreground hover:bg-secondary/80"
                        )}
                      >
                        {milestone.completed ? (
                          <CheckCircle2 className="h-5 w-5" />
                        ) : (
                          <Circle className="h-5 w-5" />
                        )}
                        <span className={cn(milestone.completed && "line-through")}>{milestone.title}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Agent */}
              <div>
                <label className="mb-2 block text-sm font-medium">Assigned Agent</label>
                <CeaserSelect
                  value={selectedGoal.agentId || "none"}
                  onValueChange={(value) => updateGoal(selectedGoal.id, { agentId: value === "none" ? undefined : value })}
                  options={[
                    { value: "none", label: "No agent" },
                    ...agents.map((agent) => ({ value: agent.id, label: agent.name, description: agent.role })),
                  ]}
                />
              </div>

              {/* Target Date */}
              <div>
                <label className="mb-2 block text-sm font-medium">Target Date</label>
                <input
                  type="text"
                  defaultValue={selectedGoal.targetDate}
                  className="w-full rounded-lg border border-border bg-background px-4 py-2 outline-none focus:border-primary"
                  placeholder="e.g., Dec 2026"
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Add Goal Modal */}
      <AnimatePresence>
        {isAddModalOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm"
            onClick={() => setIsAddModalOpen(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="relative w-full max-w-md overflow-hidden rounded-xl border border-border bg-card shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between border-b border-border px-6 py-4">
                <h2 className="text-lg font-semibold">Create New Goal</h2>
                <button
                  onClick={() => setIsAddModalOpen(false)}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="p-6 space-y-4">
                <div>
                  <label className="mb-2 block text-sm font-medium">Goal Title</label>
                  <input
                    type="text"
                    value={newGoal.title}
                    onChange={(e) => setNewGoal(prev => ({ ...prev, title: e.target.value }))}
                    placeholder="What do you want to achieve?"
                    className="w-full rounded-lg border border-border bg-background px-4 py-2 outline-none focus:border-primary"
                  />
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium">Description</label>
                  <textarea
                    value={newGoal.description}
                    onChange={(e) => setNewGoal(prev => ({ ...prev, description: e.target.value }))}
                    placeholder="Add more details..."
                    rows={3}
                    className="w-full rounded-lg border border-border bg-background px-4 py-2 outline-none focus:border-primary resize-none"
                  />
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium">Target Date</label>
                  <input
                    type="text"
                    value={newGoal.targetDate}
                    onChange={(e) => setNewGoal(prev => ({ ...prev, targetDate: e.target.value }))}
                    placeholder="e.g., Dec 2026"
                    className="w-full rounded-lg border border-border bg-background px-4 py-2 outline-none focus:border-primary"
                  />
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium">Assign Agent</label>
                  <CeaserSelect
                    value={newGoal.agentId || "none"}
                    onValueChange={(value) => setNewGoal((prev) => ({ ...prev, agentId: value === "none" ? "" : value }))}
                    options={[
                      { value: "none", label: "No agent" },
                      ...agents.map((agent) => ({ value: agent.id, label: agent.name, description: agent.role })),
                    ]}
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 border-t border-border px-6 py-4">
                <button
                  onClick={() => setIsAddModalOpen(false)}
                  className="rounded-lg border border-border px-4 py-2 text-sm transition-colors hover:bg-secondary"
                >
                  Cancel
                </button>
                <button
                  onClick={handleAddGoal}
                  disabled={!newGoal.title.trim()}
                  className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
                >
                  Create Goal
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
