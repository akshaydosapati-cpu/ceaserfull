"use client"

import { useEffect, useMemo, useState, type ReactNode } from "react"
import { agents } from "@/lib/data"
import { useApp } from "@/lib/app-context"
import { ApiError } from "@/lib/api/client"
import { automationsApi, type AutomationFrequency, type AutomationRecord, type AutomationRunRecord, type AutomationStatus, type AutomationTemplateRecord, type AutomationType, type AutomationWorkerHealth } from "@/lib/api/automations"
import { AgentAvatar } from "../agent-avatar"
import { CeaserSelect } from "../ceaser-select"
import { GlowCard } from "../glow-card"
import { cn } from "@/lib/utils"
import { Bell, Bookmark, BookOpen, Briefcase, Calendar, Check, CheckCircle2, Clock, Code2, Copy, ExternalLink, FileText, GraduationCap, History, Lightbulb, ListChecks, Loader2, MoreHorizontal, Newspaper, Pause, Play, Plus, RefreshCw, Search, Share2, Sparkles, Target, Trash2, TrendingUp, X, Zap, type LucideIcon } from "lucide-react"
import { AnimatePresence, motion } from "framer-motion"

const categoryLabels: Record<AutomationType, string> = {
  research: "Research",
  news: "News",
  business: "Business",
  content: "Content",
  learning: "Learning",
  execution: "Execution",
  engineering: "Engineering",
}

const categoryIcons: Record<AutomationType, typeof Search> = {
  research: Search,
  news: Newspaper,
  business: Briefcase,
  content: Sparkles,
  learning: GraduationCap,
  execution: Zap,
  engineering: Code2,
}

const frequencyLabels: Record<AutomationFrequency, string> = {
  once: "Once",
  daily: "Daily",
  weekly: "Weekly",
  monthly: "Monthly",
  every_weekday: "Every Weekday",
  custom: "Custom",
}

const agentByType: Record<AutomationType, string> = {
  research: "nova",
  news: "nova",
  business: "zeus",
  content: "friday",
  learning: "alex",
  execution: "bolt",
  engineering: "atlas",
}

type DraftAutomation = {
  name: string
  description: string
  automation_type: AutomationType
  trigger_frequency: AutomationFrequency
  trigger_time: string
  custom_time: string
  status: AutomationStatus
  prompt: string
}

const emptyDraft: DraftAutomation = {
  name: "",
  description: "",
  automation_type: "research",
  trigger_frequency: "daily",
  trigger_time: "morning",
  custom_time: "09:00",
  status: "active",
  prompt: "",
}

export function AutomationsPage() {
  const { confirmDialog } = useApp()
  const [templates, setTemplates] = useState<AutomationTemplateRecord[]>([])
  const [automations, setAutomations] = useState<AutomationRecord[]>([])
  const [runs, setRuns] = useState<AutomationRunRecord[]>([])
  const [selectedAutomation, setSelectedAutomation] = useState<AutomationRecord | null>(null)
  const [filter, setFilter] = useState<"all" | AutomationStatus>("all")
  const [categoryFilter, setCategoryFilter] = useState<"all" | AutomationType>("all")
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const [isHistoryOpen, setIsHistoryOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [runningId, setRunningId] = useState<string | null>(null)
  const [isRunningDue, setIsRunningDue] = useState(false)
  const [workerHealth, setWorkerHealth] = useState<AutomationWorkerHealth | null>(null)
  const [draft, setDraft] = useState<DraftAutomation>(emptyDraft)
  const [errorMessage, setErrorMessage] = useState("")

  const selectedTemplate = useMemo(
    () => templates.find((template) => template.name === draft.name && template.category === draft.automation_type),
    [draft.automation_type, draft.name, templates],
  )

  const filteredAutomations = automations.filter((automation) => {
    if (filter !== "all" && automation.status !== filter) return false
    if (categoryFilter !== "all" && automation.automation_type !== categoryFilter) return false
    return true
  })

  const activeCount = automations.filter((automation) => automation.status === "active").length
  const completedRuns = runs.filter((run) => run.status === "completed").length
  const failedRuns = runs.filter((run) => run.status === "failed").length

  useEffect(() => {
    void loadData()
  }, [])

  async function loadData() {
    setIsLoading(true)
    setErrorMessage("")
    try {
      const [templateRecords, automationRecords, health] = await Promise.all([automationsApi.templates(), automationsApi.list(), automationsApi.workerHealth().catch(() => null)])
      setTemplates(templateRecords)
      setAutomations(automationRecords)
      setWorkerHealth(health)
      const runGroups = await Promise.all(automationRecords.slice(0, 8).map((automation) => automationsApi.runs(automation.id).catch(() => [])))
      setRuns(runGroups.flat())
    } catch (error) {
      setErrorMessage(automationErrorMessage(error, "Could not load automations."))
    } finally {
      setIsLoading(false)
    }
  }

  function applyTemplate(template: AutomationTemplateRecord) {
    setDraft({
      name: template.name,
      description: template.description,
      automation_type: template.category,
      trigger_frequency: template.supported_frequencies[0] ?? "daily",
      trigger_time: "morning",
      custom_time: "09:00",
      status: "active",
      prompt: template.default_prompt,
    })
  }

  async function createAutomation() {
    if (!draft.name.trim()) return
    setIsSaving(true)
    setErrorMessage("")
    try {
      const triggerTime = draft.trigger_time === "custom" ? draft.custom_time : draft.trigger_time
      const created = await automationsApi.create({
        name: draft.name.trim(),
        description: draft.description.trim(),
        automation_type: draft.automation_type,
        trigger_frequency: draft.trigger_frequency,
        trigger_time: triggerTime,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
        status: draft.status,
        config_json: {
          prompt: draft.prompt.trim() || selectedTemplate?.default_prompt || draft.description,
          template_id: selectedTemplate?.id,
        },
      })
      setAutomations((current) => [created, ...current])
      setDraft(emptyDraft)
      setIsAddModalOpen(false)
    } catch (error) {
      setErrorMessage(automationErrorMessage(error, "Could not create automation."))
    } finally {
      setIsSaving(false)
    }
  }

  async function runNow(automation: AutomationRecord) {
    setRunningId(automation.id)
    setErrorMessage("")
    try {
      const run = await automationsApi.runNow(automation.id)
      setRuns((current) => [run, ...current.filter((item) => item.id !== run.id)])
      setSelectedAutomation(automation)
      setIsHistoryOpen(true)
      setAutomations(await automationsApi.list())
    } catch (error) {
      if (handleAutomationGone(error, automation)) return
      setErrorMessage(automationErrorMessage(error, "Could not run automation."))
    } finally {
      setRunningId(null)
    }
  }

  async function runDue() {
    setIsRunningDue(true)
    setErrorMessage("")
    try {
      const dueRuns = await automationsApi.runDue()
      setRuns((current) => [...dueRuns, ...current])
      const [automationRecords, health] = await Promise.all([automationsApi.list(), automationsApi.workerHealth().catch(() => null)])
      setAutomations(automationRecords)
      setWorkerHealth(health)
    } catch (error) {
      setErrorMessage(automationErrorMessage(error, "Could not run due automations."))
    } finally {
      setIsRunningDue(false)
    }
  }

  async function toggleStatus(automation: AutomationRecord) {
    setErrorMessage("")
    try {
      const updated = automation.status === "active" ? await automationsApi.pause(automation.id) : await automationsApi.resume(automation.id)
      setAutomations((current) => current.map((item) => (item.id === updated.id ? updated : item)))
    } catch (error) {
      if (handleAutomationGone(error, automation)) return
      setErrorMessage(automationErrorMessage(error, "Could not update automation."))
    }
  }

  async function deleteAutomation(automation: AutomationRecord) {
    const confirmed = await confirmDialog({
      title: `Delete "${automation.name}"?`,
      description: "This automation and its run history will be removed from CEASER.",
      confirmLabel: "Delete",
      tone: "danger",
    })
    if (!confirmed) return
    setErrorMessage("")
    try {
      await automationsApi.delete(automation.id)
      setAutomations((current) => current.filter((item) => item.id !== automation.id))
      setRuns((current) => current.filter((item) => item.automation_id !== automation.id))
    } catch (error) {
      if (handleAutomationGone(error, automation)) return
      setErrorMessage(automationErrorMessage(error, "Could not delete automation."))
    }
  }

  async function openHistory(automation: AutomationRecord) {
    setErrorMessage("")
    try {
      const automationRuns = await automationsApi.runs(automation.id)
      setSelectedAutomation(automation)
      setIsHistoryOpen(true)
      setRuns(automationRuns)
    } catch (error) {
      if (handleAutomationGone(error, automation)) return
      setErrorMessage(automationErrorMessage(error, "Could not load automation results."))
    }
  }

  function handleAutomationGone(error: unknown, automation: AutomationRecord) {
    if (!(error instanceof ApiError) || error.status !== 404) return false
    setErrorMessage(`"${automation.name}" no longer exists. I refreshed the automation list.`)
    setSelectedAutomation((current) => (current?.id === automation.id ? null : current))
    setIsHistoryOpen(false)
    setAutomations((current) => current.filter((item) => item.id !== automation.id))
    setRuns((current) => current.filter((item) => item.automation_id !== automation.id))
    void loadData()
    return true
  }

  const groupedTemplates = templates.reduce<Record<string, AutomationTemplateRecord[]>>((groups, template) => {
    groups[template.category] = [...(groups[template.category] ?? []), template]
    return groups
  }, {})

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Automations</h1>
          <p className="text-sm text-muted-foreground">Safe agent automations for research, study, strategy, content, execution, and technical planning.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => void runDue()} disabled={isRunningDue} className="flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground disabled:opacity-50">
            {isRunningDue ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Run Due
          </button>
          <button onClick={() => setIsAddModalOpen(true)} className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90">
            <Plus className="h-4 w-4" />
            New Automation
          </button>
        </div>
      </div>

      {errorMessage && (
        <div className="mb-4 rounded-2xl border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-100">
          {errorMessage}
        </div>
      )}

      <div className="mb-6 grid gap-4 md:grid-cols-4">
        <Metric icon={<Zap className="h-5 w-5" />} label="Active Automations" value={activeCount} tone="emerald" />
        <Metric icon={<RefreshCw className="h-5 w-5" />} label="Completed Runs" value={completedRuns} tone="cyan" />
        <Metric icon={<Bell className="h-5 w-5" />} label="Failed Runs" value={failedRuns} tone="red" />
        <Metric icon={<Calendar className="h-5 w-5" />} label={workerHealth?.running ? "Worker Running" : "Worker Status"} value={workerHealth?.running ? workerHealth.total_runs : templates.length} tone="amber" />
      </div>

      <div className="mb-6 flex flex-wrap gap-2">
        {(["all", "active", "paused"] as const).map((value) => (
          <button key={value} onClick={() => setFilter(value)} className={cn("rounded-lg px-4 py-2 text-sm capitalize transition-colors", filter === value ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground hover:text-foreground")}>
            {value}
          </button>
        ))}
        <span className="mx-1 h-9 w-px bg-border" />
        {(["all", "research", "news", "business", "content", "learning", "execution", "engineering"] as const).map((value) => (
          <button key={value} onClick={() => setCategoryFilter(value)} className={cn("rounded-lg px-4 py-2 text-sm capitalize transition-colors", categoryFilter === value ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground hover:text-foreground")}>
            {value === "all" ? "All Types" : categoryLabels[value]}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20 text-muted-foreground">
          <Loader2 className="mr-2 h-5 w-5 animate-spin" />
          Loading automations...
        </div>
      ) : (
        <div className="grid gap-4">
          {filteredAutomations.map((automation) => {
            const agent = agents.find((item) => item.id === automation.assigned_agent)
            const Icon = categoryIcons[automation.automation_type]
            return (
              <GlowCard key={automation.id} hover glowColor={agent?.color}>
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center">
                  <div className="flex flex-1 items-start gap-4">
                    {agent ? <AgentAvatar agent={agent} size="lg" showGlow /> : <Icon className="mt-2 h-8 w-8 text-primary" />}
                    <div className="min-w-0 flex-1">
                      <div className="mb-1 flex flex-wrap items-center gap-3">
                        <h3 className="font-semibold">{automation.name}</h3>
                        <StatusPill status={automation.status} />
                        <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary">{categoryLabels[automation.automation_type]}</span>
                      </div>
                      <p className="line-clamp-2 text-sm text-muted-foreground">{automation.description || "No description provided."}</p>
                      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-xs text-muted-foreground">
                        <span>Agent: {agent?.name ?? automation.assigned_agent}</span>
                        <span>Frequency: {frequencyLabels[automation.trigger_frequency]}</span>
                        <span>Next: {formatDate(automation.next_run_at)}</span>
                        <span>Last: {formatDate(automation.last_run_at)}</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2 lg:justify-end">
                    <ActionButton label="Run Now" disabled={runningId === automation.id} onClick={() => void runNow(automation)}>
                      {runningId === automation.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                    </ActionButton>
                    <ActionButton label={automation.status === "active" ? "Pause" : "Resume"} onClick={() => void toggleStatus(automation)}>
                      {automation.status === "active" ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                    </ActionButton>
                    <ActionButton label="History" onClick={() => void openHistory(automation)}>
                      <History className="h-4 w-4" />
                    </ActionButton>
                    <ActionButton label="Delete" danger onClick={() => void deleteAutomation(automation)}>
                      <Trash2 className="h-4 w-4" />
                    </ActionButton>
                  </div>
                </div>
              </GlowCard>
            )
          })}

          {filteredAutomations.length === 0 && (
            <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border py-16 text-center">
              <Zap className="mb-3 h-9 w-9 text-muted-foreground" />
              <p className="text-lg font-medium">No automations found</p>
              <p className="text-sm text-muted-foreground">Create your first agent automation from a CEASER template.</p>
            </div>
          )}
        </div>
      )}

      <AnimatePresence>
        {isAddModalOpen && (
          <Modal title="Create Agent Automation" onClose={() => setIsAddModalOpen(false)}>
            <div className="grid max-h-[76vh] gap-5 overflow-y-auto p-6 lg:grid-cols-[1fr_1.1fr]">
              <div>
                <p className="mb-3 text-sm font-medium">Automation Templates</p>
                <div className="space-y-4">
                  {Object.entries(groupedTemplates).map(([category, items]) => (
                    <div key={category}>
                      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{categoryLabels[category as AutomationType]}</p>
                      <div className="grid gap-2">
                        {items.map((template) => (
                          <button key={template.id} onClick={() => applyTemplate(template)} className={cn("rounded-lg border p-3 text-left transition-colors hover:border-primary/60 hover:bg-primary/5", selectedTemplate?.id === template.id ? "border-primary bg-primary/10" : "border-border bg-background/40")}>
                            <p className="font-medium">{template.name}</p>
                            <p className="mt-1 text-xs text-muted-foreground">{template.description}</p>
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-4">
                <Field label="Automation Name">
                  <input value={draft.name} onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))} placeholder="Daily AI Research Brief" className="w-full rounded-lg border border-border bg-background px-4 py-2 outline-none focus:border-primary" />
                </Field>
                <Field label="Description">
                  <textarea value={draft.description} onChange={(event) => setDraft((current) => ({ ...current, description: event.target.value }))} rows={3} placeholder="Research AI startup updates every morning." className="w-full resize-none rounded-lg border border-border bg-background px-4 py-2 outline-none focus:border-primary" />
                </Field>
                <Field label="Automation Type">
                  <CeaserSelect
                    value={draft.automation_type}
                    onValueChange={(value) => setDraft((current) => ({ ...current, automation_type: value as AutomationType }))}
                    options={Object.entries(categoryLabels).map(([value, label]) => ({ value, label }))}
                  />
                </Field>
                <Field label="Assigned Agent">
                  <div className="rounded-lg border border-border bg-secondary/40 px-4 py-2 text-sm">
                    {agents.find((agent) => agent.id === agentByType[draft.automation_type])?.name ?? agentByType[draft.automation_type]}
                    <span className="ml-2 text-muted-foreground">auto-selected</span>
                  </div>
                </Field>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="Frequency">
                    <CeaserSelect
                      value={draft.trigger_frequency}
                      onValueChange={(value) => setDraft((current) => ({ ...current, trigger_frequency: value as AutomationFrequency }))}
                      options={(Object.keys(frequencyLabels) as AutomationFrequency[]).map((value) => ({ value, label: frequencyLabels[value] }))}
                    />
                  </Field>
                  <Field label="Trigger Time">
                    <CeaserSelect
                      value={draft.trigger_time}
                      onValueChange={(value) => setDraft((current) => ({ ...current, trigger_time: value }))}
                      options={["morning", "afternoon", "evening", "custom"].map((value) => ({ value, label: titleCase(value) }))}
                    />
                  </Field>
                </div>
                {draft.trigger_time === "custom" && (
                  <Field label="Custom Time">
                    <input type="time" value={draft.custom_time} onChange={(event) => setDraft((current) => ({ ...current, custom_time: event.target.value }))} className="w-full rounded-lg border border-border bg-background px-4 py-2 outline-none focus:border-primary" />
                  </Field>
                )}
                <Field label="Automation Prompt">
                  <textarea value={draft.prompt} onChange={(event) => setDraft((current) => ({ ...current, prompt: event.target.value }))} rows={4} className="w-full resize-none rounded-lg border border-border bg-background px-4 py-2 outline-none focus:border-primary" />
                </Field>
                <Field label="Status">
                  <CeaserSelect
                    value={draft.status}
                    onValueChange={(value) => setDraft((current) => ({ ...current, status: value as AutomationStatus }))}
                    options={[
                      { value: "active", label: "Active" },
                      { value: "paused", label: "Paused" },
                    ]}
                  />
                </Field>
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 border-t border-border px-6 py-4">
              <button onClick={() => setIsAddModalOpen(false)} className="rounded-lg border border-border px-4 py-2 text-sm transition-colors hover:bg-secondary">Cancel</button>
              <button onClick={() => void createAutomation()} disabled={!draft.name.trim() || isSaving} className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50">
                {isSaving ? "Creating..." : "Create Automation"}
              </button>
            </div>
          </Modal>
        )}

        {isHistoryOpen && selectedAutomation && (
          <Modal title={`${selectedAutomation.name} Results`} onClose={() => setIsHistoryOpen(false)} wide>
            <div className="max-h-[82vh] space-y-5 overflow-y-auto p-6">
              {runs.filter((run) => run.automation_id === selectedAutomation.id).length === 0 ? (
                <p className="text-sm text-muted-foreground">No runs yet.</p>
              ) : (
                runs.filter((run) => run.automation_id === selectedAutomation.id).map((run) => (
                  <div key={run.id}>
                    <AutomationRunBriefing run={run} automation={selectedAutomation} />
                    <div className="hidden rounded-xl border border-border bg-background/60 p-4">
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <div>
                        <p className="font-medium">{run.output_title || selectedAutomation.name}</p>
                        <p className="text-xs text-muted-foreground">{formatDate(run.started_at)} · {run.assigned_agent}</p>
                      </div>
                      <RunStatus status={run.status} />
                    </div>
                    {run.output_summary && <p className="mb-3 text-sm text-muted-foreground">{run.output_summary}</p>}
                    {run.output_content && <div className="max-h-[52vh] overflow-y-auto whitespace-pre-wrap rounded-xl border border-white/10 bg-black/30 p-4 text-sm leading-relaxed text-foreground">{run.output_content}</div>}
                    {run.error_message && <p className="text-sm text-red-400">{run.error_message}</p>}
                    </div>
                  </div>
                ))
              )}
            </div>
          </Modal>
        )}
      </AnimatePresence>
    </div>
  )
}

function AutomationRunBriefing({ run, automation }: { run: AutomationRunRecord; automation: AutomationRecord }) {
  const news = run.metadata_json?.news
  const articles = news?.articles ?? []
  const isNews = automation.automation_type === "news" || articles.length > 0
  const Icon = categoryIcons[automation.automation_type]
  const agent = agents.find((item) => item.id === automation.assigned_agent)
  const summaryBullets = makeSummaryBullets(run.output_summary || run.output_content, articles)
  const contentSections = splitAutomationContent(run.output_content)

  async function copyResult() {
    await navigator.clipboard?.writeText(run.output_content || run.output_summary || automation.name)
  }

  async function shareResult() {
    const text = run.output_summary || run.output_content || automation.name
    if (navigator.share) {
      await navigator.share({ title: run.output_title || automation.name, text })
      return
    }
    await copyResult()
  }

  function saveResult() {
    const blob = new Blob([run.output_content || run.output_summary || ""], { type: "text/plain;charset=utf-8" })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = `${slugify(run.output_title || automation.name)}.txt`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="overflow-hidden rounded-3xl border border-white/10 bg-[radial-gradient(circle_at_top_right,rgba(124,58,237,0.16),transparent_38%),linear-gradient(180deg,rgba(15,23,42,0.96),rgba(2,6,23,0.96))] shadow-2xl">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-white/10 p-6">
        <div className="flex items-start gap-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/20 text-primary shadow-[0_0_36px_rgba(124,58,237,0.25)]">
            <Icon className="h-7 w-7" />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-primary">{categoryLabels[automation.automation_type]} Update</p>
            <h3 className="mt-1 text-2xl font-bold">{run.output_title || automation.name}</h3>
            <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
              <span className="inline-flex items-center gap-1"><Clock className="h-4 w-4" /> {formatDate(run.started_at)}</span>
              <span>Agent: {agent?.name ?? run.assigned_agent}</span>
              <RunStatus status={run.status} />
            </div>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm hover:bg-white/10">
            <Check className="h-4 w-4" />
            Mark as read
          </button>
          <button onClick={() => void shareResult()} className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm hover:bg-white/10">
            <Share2 className="h-4 w-4" />
            Share
          </button>
          <button className="rounded-xl border border-white/10 bg-white/5 p-2 text-muted-foreground hover:bg-white/10 hover:text-foreground">
            <MoreHorizontal className="h-5 w-5" />
          </button>
        </div>
      </div>

      <div className="grid gap-5 p-6 xl:grid-cols-[1fr_380px]">
        <div className="space-y-5">
          <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03] p-6">
            <div className="absolute right-0 top-0 h-36 w-72 rounded-full bg-primary/20 blur-3xl" />
            <p className="relative text-xs font-semibold uppercase tracking-[0.2em] text-primary">{isNews ? "Top Headlines" : "Automation Result"}</p>
            <h4 className="relative mt-3 text-3xl font-bold">{isNews ? "Your Automated Briefing" : run.output_title || automation.name}</h4>
            <p className="relative mt-3 line-clamp-3 max-w-3xl text-sm leading-relaxed text-muted-foreground">
              {run.output_summary || "CEASER completed this automation and prepared the result below."}
            </p>
          </div>

          {isNews && articles.length > 0 ? (
            <div className="overflow-hidden rounded-2xl border border-white/10 bg-black/20">
              {articles.slice(0, 8).map((article, index) => (
                <a key={`${article.title}-${index}`} href={article.url || undefined} target="_blank" rel="noreferrer" className="group grid gap-4 border-b border-white/10 p-4 transition-colors last:border-b-0 hover:bg-white/[0.04] sm:grid-cols-[128px_1fr_auto]">
                  <div className="flex h-24 items-center justify-center overflow-hidden rounded-xl bg-white/5">
                    {article.image_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={article.image_url} alt="" className="h-full w-full object-cover" />
                    ) : (
                      <Newspaper className="h-8 w-8 text-primary" />
                    )}
                  </div>
                  <div className="min-w-0">
                    <h5 className="font-semibold leading-snug text-foreground group-hover:text-primary">{article.title}</h5>
                    {article.summary && <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-muted-foreground">{article.summary}</p>}
                    <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <span>{article.source || "News source"}</span>
                      {article.published_at && <span>{article.published_at}</span>}
                    </div>
                  </div>
                  <div className="flex items-start gap-2">
                    <span className="rounded-full bg-primary/15 px-3 py-1 text-xs text-primary">{news?.mode?.replace("category:", "") || "News"}</span>
                    {article.url && <ExternalLink className="h-4 w-4 text-muted-foreground" />}
                  </div>
                </a>
              ))}
            </div>
          ) : (
            <AutomationStructuredOutput automation={automation} sections={contentSections} errorMessage={run.error_message} />
          )}
        </div>

        <div className="space-y-4">
          <SidePanel title="Summary" icon={<Sparkles className="h-5 w-5 text-primary" />}>
            <ul className="space-y-3 text-sm text-muted-foreground">
              {summaryBullets.map((bullet) => (
                <li key={bullet} className="flex gap-2">
                  <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  <span>{bullet}</span>
                </li>
              ))}
            </ul>
          </SidePanel>

          <SidePanel title="About This Automation">
            <div className="space-y-3 text-sm text-muted-foreground">
              <InfoRow label="Schedule" value={`${frequencyLabels[automation.trigger_frequency]}${automation.trigger_time ? ` at ${titleCase(automation.trigger_time)}` : ""}`} />
              <InfoRow label="Sources" value={articles.length ? `${articles.length} selected` : "Generated by agent"} />
              <InfoRow label="Provider" value={news?.provider || "CEASER"} />
              <InfoRow label="Agent" value={agent?.name ?? run.assigned_agent} />
            </div>
          </SidePanel>

          <SidePanel title="Actions">
            <div className="grid gap-2">
              <button onClick={() => void copyResult()} className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm hover:bg-white/10">
                <Copy className="h-4 w-4" />
                Copy Result
              </button>
              <button onClick={() => void shareResult()} className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm hover:bg-white/10">
                <Share2 className="h-4 w-4" />
                Share
              </button>
              <button onClick={saveResult} className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/10 bg-primary px-4 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90">
                <Bookmark className="h-4 w-4" />
                Save Text
              </button>
            </div>
          </SidePanel>
        </div>
      </div>
    </div>
  )
}

function AutomationStructuredOutput({ automation, sections, errorMessage }: { automation: AutomationRecord; sections: Array<{ title: string; body: string }>; errorMessage?: string | null }) {
  const primarySections = sections.slice(0, 4)
  const actionItems = extractActionItems(sections)
  const config = automationLayoutConfig[automation.automation_type]
  const MainIcon = config.mainIcon

  return (
    <div className="grid gap-5">
      <div className="grid gap-4 lg:grid-cols-3">
        {primarySections.slice(0, 3).map((section, index) => {
          const Icon = config.cardIcons[index] ?? FileText
          const bullets = parseBullets(section.body).slice(0, 4)
          return (
            <div key={`${section.title}-${index}`} className={cn("rounded-2xl border p-5", config.cardClass)}>
              <div className="mb-4 flex items-center gap-3">
                <div className={cn("flex h-10 w-10 items-center justify-center rounded-xl", config.iconClass)}>
                  <Icon className="h-5 w-5" />
                </div>
                <h5 className="line-clamp-2 font-semibold">{cleanSectionTitle(section.title)}</h5>
              </div>
              <ul className="space-y-3 text-sm text-muted-foreground">
                {bullets.map((bullet) => (
                  <li key={bullet} className="flex gap-2">
                    <CheckCircle2 className={cn("mt-0.5 h-4 w-4 shrink-0", config.checkClass)} />
                    <span>{bullet}</span>
                  </li>
                ))}
              </ul>
            </div>
          )
        })}
      </div>

      <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
        <div className="rounded-2xl border border-white/10 bg-black/20 p-5">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">{config.mainLabel}</p>
              <h5 className="mt-1 text-lg font-semibold">{config.mainTitle}</h5>
            </div>
            <div className={cn("flex h-10 w-10 items-center justify-center rounded-xl", config.iconClass)}>
              <MainIcon className="h-5 w-5" />
            </div>
          </div>
          <div className="grid gap-3">
            {sections.map((section, index) => (
              <div key={`${section.title}-${index}`} className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                <p className="font-medium">{cleanSectionTitle(section.title)}</p>
                <div className="mt-2 grid gap-2 text-sm text-muted-foreground">
                  {parseBullets(section.body).slice(0, 4).map((bullet) => (
                    <div key={bullet} className="flex gap-2">
                      <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                      <span>{bullet}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">Action Queue</p>
            <div className="mt-4 space-y-3">
              {actionItems.slice(0, 6).map((item, index) => (
                <div key={item} className="flex gap-3 rounded-xl border border-white/10 bg-black/20 p-3">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/15 text-xs font-semibold text-primary">{index + 1}</div>
                  <p className="text-sm text-muted-foreground">{item}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">Best Use</p>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{config.bestUse}</p>
          </div>
        </div>
      </div>

      {errorMessage && <div className="rounded-2xl border border-red-400/20 bg-red-500/10 p-4 text-sm text-red-100">{errorMessage}</div>}
    </div>
  )
}

const automationLayoutConfig: Record<
  AutomationType,
  {
    mainLabel: string
    mainTitle: string
    bestUse: string
    mainIcon: LucideIcon
    cardIcons: LucideIcon[]
    cardClass: string
    iconClass: string
    checkClass: string
  }
> = {
  research: {
    mainLabel: "Research Brief",
    mainTitle: "Findings & Recommendations",
    bestUse: "Use this brief to review market signals, choose follow-up research questions, and save useful findings into CEASER memory.",
    mainIcon: Search,
    cardIcons: [Search, TrendingUp, Lightbulb],
    cardClass: "border-cyan-400/15 bg-cyan-400/[0.04]",
    iconClass: "bg-cyan-400/15 text-cyan-300",
    checkClass: "text-cyan-300",
  },
  news: {
    mainLabel: "News Brief",
    mainTitle: "Headlines & Signals",
    bestUse: "Use this briefing to scan what changed today, then open the original sources for deeper reading.",
    mainIcon: Newspaper,
    cardIcons: [Newspaper, TrendingUp, Lightbulb],
    cardClass: "border-violet-400/15 bg-violet-400/[0.04]",
    iconClass: "bg-violet-400/15 text-violet-300",
    checkClass: "text-violet-300",
  },
  business: {
    mainLabel: "Strategy Brief",
    mainTitle: "Business Plan & Decisions",
    bestUse: "Use this as a strategy canvas: review assumptions, pick decisions, and turn next actions into tasks or drafts.",
    mainIcon: Briefcase,
    cardIcons: [Target, TrendingUp, ListChecks],
    cardClass: "border-amber-400/15 bg-amber-400/[0.04]",
    iconClass: "bg-amber-400/15 text-amber-300",
    checkClass: "text-amber-300",
  },
  content: {
    mainLabel: "Content Plan",
    mainTitle: "Campaign Assets & Calendar",
    bestUse: "Use this to approve content angles, schedule posts, and hand the best ideas to Friday for drafting.",
    mainIcon: Sparkles,
    cardIcons: [Sparkles, Calendar, ListChecks],
    cardClass: "border-pink-400/15 bg-pink-400/[0.04]",
    iconClass: "bg-pink-400/15 text-pink-300",
    checkClass: "text-pink-300",
  },
  learning: {
    mainLabel: "Study Plan",
    mainTitle: "Learning Path & Practice Tasks",
    bestUse: "Use this as your study dashboard: follow the sessions, complete practice tasks, and convert weak areas into revision notes.",
    mainIcon: GraduationCap,
    cardIcons: [BookOpen, Calendar, ListChecks],
    cardClass: "border-emerald-400/15 bg-emerald-400/[0.04]",
    iconClass: "bg-emerald-400/15 text-emerald-300",
    checkClass: "text-emerald-300",
  },
  execution: {
    mainLabel: "Execution Plan",
    mainTitle: "Tasks, Deadlines & Follow-ups",
    bestUse: "Use this to drive work forward: assign owners, track blockers, and run the automation again for a status review.",
    mainIcon: Zap,
    cardIcons: [Zap, ListChecks, Calendar],
    cardClass: "border-blue-400/15 bg-blue-400/[0.04]",
    iconClass: "bg-blue-400/15 text-blue-300",
    checkClass: "text-blue-300",
  },
  engineering: {
    mainLabel: "Technical Brief",
    mainTitle: "Architecture, Risks & Build Steps",
    bestUse: "Use this as technical planning context before creating implementation tickets, docs, or architecture drafts.",
    mainIcon: Code2,
    cardIcons: [Code2, FileText, ListChecks],
    cardClass: "border-indigo-400/15 bg-indigo-400/[0.04]",
    iconClass: "bg-indigo-400/15 text-indigo-300",
    checkClass: "text-indigo-300",
  },
}

function Metric({ icon, label, value, tone }: { icon: ReactNode; label: string; value: number; tone: "emerald" | "cyan" | "red" | "amber" }) {
  const tones = {
    emerald: "bg-emerald-500/10 text-emerald-400",
    cyan: "bg-cyan-500/10 text-cyan-400",
    red: "bg-red-500/10 text-red-400",
    amber: "bg-amber-500/10 text-amber-400",
  }
  return (
    <GlowCard>
      <div className="flex items-center gap-3">
        <div className={cn("flex h-11 w-11 items-center justify-center rounded-xl", tones[tone])}>{icon}</div>
        <div>
          <p className="text-2xl font-bold">{value}</p>
          <p className="text-sm text-muted-foreground">{label}</p>
        </div>
      </div>
    </GlowCard>
  )
}

function StatusPill({ status }: { status: AutomationStatus }) {
  return <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", status === "active" ? "bg-emerald-500/20 text-emerald-400" : "bg-amber-500/20 text-amber-400")}>{titleCase(status)}</span>
}

function RunStatus({ status }: { status: AutomationRunRecord["status"] }) {
  const classes = status === "completed" ? "bg-emerald-500/20 text-emerald-400" : status === "failed" ? "bg-red-500/20 text-red-400" : "bg-cyan-500/20 text-cyan-400"
  return <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", classes)}>{titleCase(status)}</span>
}

function ActionButton({ children, label, onClick, disabled, danger }: { children: ReactNode; label: string; onClick: () => void; disabled?: boolean; danger?: boolean }) {
  return (
    <button onClick={onClick} disabled={disabled} title={label} className={cn("flex items-center gap-2 rounded-lg border px-3 py-2 text-xs transition-colors disabled:opacity-50", danger ? "border-red-500/20 text-red-400 hover:bg-red-500/10" : "border-border text-muted-foreground hover:bg-secondary hover:text-foreground")}>
      {children}
      <span className="hidden xl:inline">{label}</span>
    </button>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-medium">{label}</span>
      {children}
    </label>
  )
}

function SidePanel({ title, icon, children }: { title: string; icon?: ReactNode; children: ReactNode }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
      <div className="mb-4 flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">{title}</p>
        {icon}
      </div>
      {children}
    </div>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span>{label}</span>
      <span className="text-right text-foreground">{value}</span>
    </div>
  )
}

function splitAutomationContent(content: string) {
  const cleaned = content?.trim()
  if (!cleaned) return [{ title: "Result", body: "No output content was generated for this run." }]
  const normalized = cleaned
    .replace(/\r\n/g, "\n")
    .replace(/^#{1,4}\s*/gm, "")
  const sections = normalized
    .split(/\n(?=[A-Z][A-Za-z &/]{2,48}\n)/g)
    .map((section) => section.trim())
    .filter(Boolean)
    .map((section) => {
      const [firstLine, ...rest] = section.split("\n")
      const title = firstLine.replace(/^#+\s*/, "").trim()
      return { title: title || "Result", body: rest.join("\n").trim() || section }
    })
  return sections.length ? sections.slice(0, 6) : [{ title: "Result", body: cleaned }]
}

function parseBullets(body: string) {
  const lines = body
    .split("\n")
    .map((line) => line.replace(/^[-*•]\s*/, "").replace(/^\d+[.)]\s*/, "").replace(/\*\*/g, "").trim())
    .filter(Boolean)

  if (lines.length > 1) return lines.filter((line) => line.length > 8)

  const sentences = body
    .replace(/\*\*/g, "")
    .split(/(?<=[.!?])\s+/)
    .map((sentence) => sentence.trim())
    .filter((sentence) => sentence.length > 8)

  return sentences.length ? sentences : [body.replace(/\*\*/g, "").trim()]
}

function extractActionItems(sections: Array<{ title: string; body: string }>) {
  const actionSection = sections.find((section) => /action|next|recommend|task|todo|plan|schedule/i.test(section.title))
  const source = actionSection ?? sections[sections.length - 1] ?? sections[0]
  return parseBullets(source?.body ?? "").slice(0, 8)
}

function cleanSectionTitle(title: string) {
  return title
    .replace(/^\d+[.)]\s*/, "")
    .replace(/\*\*/g, "")
    .replace(/[:\-]+$/, "")
    .trim() || "Result"
}

function makeSummaryBullets(content: string, articles: Array<{ title: string; summary?: string | null }>) {
  if (articles.length) {
    return articles.slice(0, 5).map((article) => article.title)
  }
  const sentences = (content || "")
    .replace(/#+/g, "")
    .split(/(?<=[.!?])\s+/)
    .map((sentence) => sentence.trim())
    .filter((sentence) => sentence.length > 24)
  return (sentences.length ? sentences : ["Automation completed successfully."]).slice(0, 5)
}

function slugify(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "") || "automation-result"
}

function Modal({ title, children, onClose, wide }: { title: string; children: ReactNode; onClose: () => void; wide?: boolean }) {
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4 backdrop-blur-sm" onClick={onClose}>
      <motion.div initial={{ scale: 0.96, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.96, opacity: 0 }} className={cn("relative w-full overflow-hidden rounded-xl border border-border bg-card shadow-2xl", wide ? "max-w-7xl" : "max-w-5xl")} onClick={(event) => event.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground"><X className="h-5 w-5" /></button>
        </div>
        {children}
      </motion.div>
    </motion.div>
  )
}

function formatDate(value?: string | null) {
  if (!value) return "Not scheduled"
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value))
}

function titleCase(value: string) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function automationErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError && error.status === 401) {
    return "Your CEASER session expired. Please sign in again, then create or run the automation."
  }
  if (error instanceof Error && error.message) return error.message
  return fallback
}
