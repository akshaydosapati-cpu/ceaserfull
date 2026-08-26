"use client"

import { useEffect, useState, type ReactNode } from "react"
import { draftsApi, type DraftRecord, type DraftSection } from "@/lib/api/drafts"
import { ApiError } from "@/lib/api/client"
import { documentsApi, type GeneratedDocument } from "@/lib/api/documents"
import { workflowsApi, type WorkflowRunRecord, type WorkflowStepRecord } from "@/lib/api/workflows"
import { agents } from "@/lib/data"
import { useApp } from "@/lib/app-context"
import { AgentAvatar } from "../agent-avatar"
import { CheckCircle2, FileText, Loader2, RotateCcw, Trash2 } from "lucide-react"

export function DraftsPage() {
  const { confirmDialog, setCurrentPage } = useApp()
  const [drafts, setDrafts] = useState<DraftRecord[]>([])
  const [documents, setDocuments] = useState<GeneratedDocument[]>([])
  const [workflowRuns, setWorkflowRuns] = useState<WorkflowRunRecord[]>([])
  const [activeDraft, setActiveDraft] = useState<DraftRecord | null>(null)
  const [activeDocument, setActiveDocument] = useState<GeneratedDocument | null>(null)
  const [activeWorkflow, setActiveWorkflow] = useState<WorkflowRunRecord | null>(null)
  const [activeSectionIndex, setActiveSectionIndex] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [actionError, setActionError] = useState<string | null>(null)
  const [isTransitioning, setIsTransitioning] = useState(false)

  const load = async () => {
    setIsLoading(true)
    try {
      const [draftResult, documentResult, workflowResult] = await Promise.allSettled([draftsApi.list(), documentsApi.list(), workflowsApi.list()])
      const draftRecords = draftResult.status === "fulfilled" ? draftResult.value : []
      const documentRecords = documentResult.status === "fulfilled" ? documentResult.value : []
      const workflowRecords = workflowResult.status === "fulfilled" ? workflowResult.value : []
      setDrafts(draftRecords)
      setDocuments(documentRecords)
      setWorkflowRuns(workflowRecords)
      setActiveWorkflow(workflowRecords[0] ?? null)
      setActiveDraft(workflowRecords[0] ? null : draftRecords[0] ?? null)
      setActiveDocument(workflowRecords[0] || draftRecords[0] ? null : documentRecords[0] ?? null)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const transition = async (draft: DraftRecord, action: "approved" | "regenerated" | "archived") => {
    setActionError(null)
    setIsTransitioning(true)
    try {
      const updated = await draftsApi.action(draft.id, action)
      setActiveDraft(updated)
      setDrafts(await draftsApi.list())
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        await load()
        setActionError("That workflow was already removed. The workflow list has been refreshed.")
        return
      }
      setActionError(error instanceof Error ? error.message : "Could not update this workflow.")
    } finally {
      setIsTransitioning(false)
    }
  }

  const deleteDraft = async (draft: DraftRecord) => {
    const confirmed = await confirmDialog({
      title: `Delete "${draft.title}"?`,
      description: "This draft will be permanently removed from CEASER. This cannot be undone.",
      confirmLabel: "Delete",
      tone: "danger",
    })
    if (!confirmed) return
    setIsTransitioning(true)
    setActionError(null)
    try {
      await draftsApi.delete(draft.id)
      const records = await draftsApi.list()
      setDrafts(records)
      setActiveDraft(records[0] ?? null)
      setActiveDocument(records[0] ? null : documents[0] ?? null)
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        await load()
        setActionError("That workflow was already removed. The workflow list has been refreshed.")
      } else {
        setActionError(error instanceof Error ? error.message : "Could not delete this workflow.")
      }
    } finally {
      setIsTransitioning(false)
    }
  }

  return (
    <div className="grid h-full min-h-0 gap-5 p-6 lg:grid-cols-[340px_1fr]">
      <aside className="min-h-0 overflow-hidden rounded-lg border border-border bg-secondary/20">
        <div className="border-b border-border p-4">
          <h1 className="text-xl font-semibold">Workflows</h1>
          <p className="text-sm text-muted-foreground">Agent-created outputs, reports, decks, and execution-ready work.</p>
        </div>
        <div className="max-h-full overflow-y-auto p-3">
          {isLoading ? (
            <div className="flex items-center justify-center py-10 text-sm text-muted-foreground"><Loader2 className="mr-2 h-4 w-4 animate-spin" />Loading workflows...</div>
          ) : (
            <>
              {drafts.map((draft) => {
            const agent = agents.find((item) => item.id === draft.agent_id)
            return (
                  <button key={draft.id} onClick={() => { setActiveDraft(draft); setActiveDocument(null); setActiveSectionIndex(0) }} className="mb-2 flex w-full gap-3 rounded-lg border border-border bg-background/40 p-3 text-left hover:bg-secondary">
                {agent ? <AgentAvatar agent={agent} size="sm" /> : <FileText className="h-5 w-5 text-primary" />}
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{draft.title}</span>
                  <span className="text-xs capitalize text-muted-foreground">{draft.draft_type.replace("_", " ")} / {draft.status}</span>
                </span>
              </button>
            )
          })}
              {workflowRuns.map((workflow) => (
                <button key={workflow.id} onClick={() => { setActiveWorkflow(workflow); setActiveDraft(null); setActiveDocument(null); setActiveSectionIndex(0) }} className="mb-2 flex w-full gap-3 rounded-lg border border-border bg-background/40 p-3 text-left hover:bg-secondary">
                  <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-400" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">Generated {workflow.workflow_type.replaceAll("_", " ")} workflow</span>
                    <span className="text-xs capitalize text-muted-foreground">{workflow.status} / {workflow.result_summary || "Ready"}</span>
                  </span>
                </button>
              ))}
              {documents.map((document) => {
                const agent = agents.find((item) => item.id === document.agent_id)
                return (
                  <button key={document.id} onClick={() => { setActiveDocument(document); setActiveDraft(null) }} className="mb-2 flex w-full gap-3 rounded-lg border border-border bg-background/40 p-3 text-left hover:bg-secondary">
                    {agent ? <AgentAvatar agent={agent} size="sm" /> : <FileText className="h-5 w-5 text-primary" />}
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">{document.file_name || document.source_prompt}</span>
                      <span className="text-xs capitalize text-muted-foreground">Generated {document.export_format.toUpperCase()} / document</span>
                    </span>
                  </button>
                )
              })}
            </>
          )}
          {!isLoading && !drafts.length && !documents.length && !workflowRuns.length && <p className="py-10 text-center text-sm text-muted-foreground">No workflows yet.</p>}
        </div>
      </aside>

      <main className="min-h-0 overflow-hidden rounded-lg border border-border bg-secondary/20">
        {activeWorkflow ? (
          <WorkflowRunPreview workflow={activeWorkflow} onChanged={load} />
        ) : activeDraft ? (
          <div className="flex h-full min-h-0 flex-col">
            <div className="border-b border-border p-5">
              <h2 className="text-2xl font-semibold">{activeDraft.title}</h2>
              <p className="text-sm capitalize text-muted-foreground">{activeDraft.draft_type.replace("_", " ")} / {activeDraft.status} / {activeDraft.progress}%</p>
              <div className="mt-4 flex gap-2">
                <button disabled={isTransitioning} onClick={() => void transition(activeDraft, "approved")} className="flex items-center gap-2 rounded-lg border border-emerald-500/50 px-3 py-2 text-sm text-emerald-400 disabled:opacity-50"><CheckCircle2 className="h-4 w-4" />{isTransitioning ? "Updating..." : "Approve"}</button>
                <button disabled={isTransitioning} onClick={() => void transition(activeDraft, "regenerated")} className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm hover:bg-secondary disabled:opacity-50"><RotateCcw className={isTransitioning ? "h-4 w-4 animate-spin" : "h-4 w-4"} />Regenerate</button>
                <button disabled={isTransitioning} onClick={() => void transition(activeDraft, "archived")} className="rounded-lg border border-border px-3 py-2 text-sm hover:bg-secondary disabled:opacity-50">Archive</button>
                <button disabled={isTransitioning} onClick={() => void deleteDraft(activeDraft)} className="flex items-center gap-2 rounded-lg border border-red-500/40 px-3 py-2 text-sm text-red-400 hover:bg-red-500/10 disabled:opacity-50"><Trash2 className="h-4 w-4" />Delete</button>
              </div>
              {actionError && <p className="mt-3 text-sm text-amber-300">{actionError}</p>}
            </div>
            <div className="grid min-h-0 flex-1 gap-4 p-5 lg:grid-cols-[280px_1fr]">
              <div className="space-y-2">
                {draftOutline(activeDraft).map((title, index) => (
                  <button
                    key={`${title}-${index}`}
                    onClick={() => {
                      setActiveSectionIndex(index)
                      document.getElementById(`workflow-section-${index}`)?.scrollIntoView({ behavior: "smooth", block: "center" })
                    }}
                    className={`w-full rounded-lg border px-3 py-2 text-left text-sm transition ${activeSectionIndex === index ? "border-primary bg-primary/15 text-primary shadow-[0_0_20px_rgba(124,58,237,0.18)]" : "border-border bg-background/40 hover:bg-secondary"}`}
                  >
                    {index + 1}. {title}
                  </button>
                ))}
              </div>
              <div className="overflow-y-auto rounded-lg border border-border bg-background/40 p-5">
                <DraftPreview draft={activeDraft} activeSectionIndex={activeSectionIndex} />
              </div>
            </div>
          </div>
        ) : activeDocument ? (
          <div className="flex h-full min-h-0 flex-col">
            <div className="border-b border-border p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">Generated Document</p>
              <h2 className="mt-1 text-2xl font-semibold">{activeDocument.file_name || activeDocument.source_prompt}</h2>
              <p className="text-sm text-muted-foreground">{activeDocument.export_format.toUpperCase()} / Generated by {activeDocument.generated_by}</p>
              <div className="mt-4 flex gap-2">
                <button onClick={() => setCurrentPage("files")} className="rounded-lg border border-border px-3 py-2 text-sm hover:bg-secondary">Open in Files</button>
              </div>
            </div>
            <div className="grid min-h-0 flex-1 gap-4 p-5 lg:grid-cols-[280px_1fr]">
              <div className="space-y-2">
                <div className="rounded-lg border border-border bg-background/40 px-3 py-2 text-sm">1. Generated document</div>
                <div className="rounded-lg border border-border bg-background/40 px-3 py-2 text-sm">2. Linked file record</div>
                <div className="rounded-lg border border-border bg-background/40 px-3 py-2 text-sm">3. Available in Files</div>
              </div>
              <div className="overflow-y-auto rounded-lg border border-border bg-background/40 p-5">
                <section className="rounded-lg border border-border bg-background/50 p-4">
                  <h3 className="font-semibold">Source Prompt</h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{activeDocument.source_prompt}</p>
                </section>
                <section className="mt-3 rounded-lg border border-border bg-background/50 p-4">
                  <h3 className="font-semibold">Workflow Link</h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">This generated document is now part of CEASER workflows and is available in Files for review, download, and project context.</p>
                </section>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">Select a workflow.</div>
        )}
      </main>
    </div>
  )
}

function WorkflowRunPreview({ workflow, onChanged }: { workflow: WorkflowRunRecord; onChanged: () => Promise<void> }) {
  const { confirmDialog } = useApp()
  const [steps, setSteps] = useState<WorkflowStepRecord[]>([])
  const [isActionRunning, setIsActionRunning] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  useEffect(() => {
    void workflowsApi.steps(workflow.id).then(setSteps).catch(() => setSteps([]))
  }, [workflow.id])

  const generatedOutput = String(workflow.metadata_json.generated_response || workflow.result_summary || "CEASER generated this workflow. Review the completed steps below.")
  const nextActions = Array.isArray(workflow.metadata_json.next_actions) ? workflow.metadata_json.next_actions : []

  const runAction = async (action: "approved" | "archived" | "regenerate" | "delete") => {
    if (action === "delete") {
      const confirmed = await confirmDialog({ title: "Delete workflow?", description: "This removes the generated workflow and its steps permanently.", confirmLabel: "Delete", tone: "danger" })
      if (!confirmed) return
    }
    setIsActionRunning(true)
    setActionError(null)
    try {
      if (action === "regenerate") await workflowsApi.regenerate(workflow.id)
      else if (action === "delete") await workflowsApi.delete(workflow.id)
      else await workflowsApi.action(workflow.id, action)
      await onChanged()
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Could not update this workflow.")
    } finally {
      setIsActionRunning(false)
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="border-b border-border p-5">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">Generated workflow</p>
        <h2 className="mt-1 text-2xl font-semibold capitalize">{workflow.workflow_type.replaceAll("_", " ")} workflow</h2>
        <p className="text-sm capitalize text-muted-foreground">{workflow.status} / {workflow.result_summary || "Generated by CEASER"}</p>
        <div className="mt-4 flex flex-wrap gap-2">
          <button disabled={isActionRunning} onClick={() => void runAction("approved")} className="rounded-lg border border-emerald-500/50 px-3 py-2 text-sm text-emerald-400 disabled:opacity-50">Approve</button>
          <button disabled={isActionRunning} onClick={() => void runAction("regenerate")} className="rounded-lg border border-border px-3 py-2 text-sm hover:bg-secondary disabled:opacity-50">Regenerate</button>
          <button disabled={isActionRunning} onClick={() => void runAction("archived")} className="rounded-lg border border-border px-3 py-2 text-sm hover:bg-secondary disabled:opacity-50">Archive</button>
          <button disabled={isActionRunning} onClick={() => void runAction("delete")} className="rounded-lg border border-red-500/40 px-3 py-2 text-sm text-red-400 hover:bg-red-500/10 disabled:opacity-50">Delete</button>
        </div>
        {actionError && <p className="mt-3 text-sm text-amber-300">{actionError}</p>}
      </div>
      <div className="grid min-h-0 flex-1 gap-4 p-5 lg:grid-cols-[280px_1fr]">
        <div className="space-y-2 overflow-y-auto">
          {steps.map((step, index) => (
            <div key={step.id} className="rounded-lg border border-border bg-background/40 px-3 py-2 text-sm">
              {index + 1}. {step.agent_name} <span className="text-muted-foreground">/ {step.status}</span>
            </div>
          ))}
          {!steps.length && <p className="text-sm text-muted-foreground">Loading workflow steps...</p>}
        </div>
        <div className="overflow-y-auto rounded-lg border border-border bg-background/40 p-5">
          <section className="rounded-lg border border-primary/25 bg-primary/5 p-4">
            <h3 className="font-semibold">Generated workflow output</h3>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">{generatedOutput}</p>
          </section>
          {nextActions.length > 0 && (
            <section className="mt-3 rounded-lg border border-border bg-background/50 p-4">
              <h3 className="font-semibold">Next actions</h3>
              <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
                {nextActions.map((action, index) => <li key={`${String(action)}-${index}`}>- {String(action)}</li>)}
              </ul>
            </section>
          )}
          <section className="mt-3 grid gap-3 md:grid-cols-2">
            {steps.map((step) => (
              <div key={`${step.id}-output`} className="rounded-lg border border-border bg-background/50 p-4">
                <h3 className="font-semibold">{step.agent_name}</h3>
                <p className="mt-2 text-sm text-muted-foreground">{step.output_summary || "Completed workflow step."}</p>
              </div>
            ))}
          </section>
        </div>
      </div>
    </div>
  )
}

function draftOutline(draft: DraftRecord): string[] {
  const content = workflowContent(draft.content)
  const slides = asArray<{ title?: string }>(content.slides)
  const keyFindings = asArray<{ finding?: string }>(content.key_findings)
  const modules = asArray<{ name?: string }>(content.modules)
  const calendarItems = asArray<Record<string, string>>(content.calendar_items)
  const dailyPlan = asArray<{ day?: string; focus?: string }>(content.daily_plan)
  const milestones = asArray<{ name?: string }>(content.milestones)
  const sections = asArray<DraftSection | { title?: string; heading?: string }>(content.sections)
  if (slides.length) return slides.map((slide) => slide.title || "Slide")
  if (keyFindings.length) return keyFindings.map((finding) => finding.finding || "Finding")
  if (modules.length) return modules.map((module) => module.name || "Module")
  if (calendarItems.length) return calendarItems.map((item) => `${item.date ?? "Date"} - ${item.platform ?? "Platform"}`)
  if (dailyPlan.length) return dailyPlan.map((day) => `${day.day ?? "Day"}: ${day.focus ?? "Focus"}`)
  if (milestones.length) return milestones.map((milestone) => milestone.name || "Milestone")
  if (sections.length) return sections.map((section) => "title" in section ? section.title || "Section" : section.heading ?? "Section")
  return [draft.title]
}

function DraftPreview({ draft, activeSectionIndex }: { draft: DraftRecord; activeSectionIndex: number }) {
  const content = workflowContent(draft.content)
  const slides = asArray<{ slide_number?: number; title?: string; purpose?: string; bullets?: string[]; visual_suggestion?: string; speaker_notes?: string }>(content.slides)
  const keyFindings = asArray<{ finding?: string; evidence?: string }>(content.key_findings)
  const modules = asArray<{ name?: string; purpose?: string; responsibilities?: string[] }>(content.modules)
  const calendarItems = asArray<Record<string, string>>(content.calendar_items)
  const dailyPlan = asArray<{ day?: string; focus?: string; tasks?: string[] }>(content.daily_plan)
  const milestones = asArray<{ name?: string; tasks?: string[]; priority?: string; deadline?: string }>(content.milestones)
  if (slides.length) {
    return (
      <div className="space-y-3">
        {slides.map((slide, index) => (
          <section key={`${slide.slide_number ?? index}-${slide.title ?? "slide"}`} className="rounded-lg border border-border bg-background/50 p-4">
            <p className="text-xs text-primary">Slide {slide.slide_number ?? index + 1}</p>
            <h3 className="mt-1 font-semibold">{slide.title ?? "Untitled slide"}</h3>
            <p className="mt-1 text-sm text-muted-foreground">{slide.purpose ?? "No purpose added."}</p>
            <ul className="mt-3 space-y-1 text-sm">
              {asArray<string>(slide.bullets).map((bullet) => <li key={bullet}>- {bullet}</li>)}
            </ul>
            <p className="mt-3 text-xs text-muted-foreground"><span className="text-foreground">Visual:</span> {slide.visual_suggestion ?? "Not specified"}</p>
            <p className="mt-1 text-xs text-muted-foreground"><span className="text-foreground">Speaker notes:</span> {slide.speaker_notes ?? "Not specified"}</p>
          </section>
        ))}
      </div>
    )
  }
  if (keyFindings.length) {
    return (
      <div className="space-y-3">
        {typeof content.executive_summary === "string" && <p className="rounded-lg border border-border bg-background/50 p-4 text-sm text-muted-foreground">{content.executive_summary}</p>}
        {keyFindings.map((finding, index) => (
          <section key={`${finding.finding ?? "finding"}-${index}`} className="rounded-lg border border-border bg-background/50 p-4">
            <h3 className="font-semibold">{finding.finding ?? "Finding"}</h3>
            <p className="mt-1 text-sm text-muted-foreground">{finding.evidence ?? "No evidence added."}</p>
          </section>
        ))}
      </div>
    )
  }
  if (modules.length) {
    return (
      <div className="space-y-3">
        {modules.map((module, index) => (
          <section key={`${module.name ?? "module"}-${index}`} className="rounded-lg border border-border bg-background/50 p-4">
            <h3 className="font-semibold">{module.name ?? "Module"}</h3>
            <p className="mt-1 text-sm text-muted-foreground">{module.purpose ?? "No purpose added."}</p>
            <ul className="mt-2 space-y-1 text-sm text-muted-foreground">{asArray<string>(module.responsibilities).map((item) => <li key={item}>- {item}</li>)}</ul>
          </section>
        ))}
      </div>
    )
  }
  if (calendarItems.length) {
    return (
      <div className="overflow-hidden rounded-lg border border-border">
        <table className="w-full text-left text-sm">
          <thead className="bg-secondary/60 text-xs uppercase text-muted-foreground">
            <tr>
              <th className="px-3 py-2">Date</th>
              <th className="px-3 py-2">Platform</th>
              <th className="px-3 py-2">Topic</th>
              <th className="px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {calendarItems.map((item, index) => (
              <tr key={`${item.date}-${item.topic}-${index}`} className="border-t border-border">
                <td className="px-3 py-2 text-muted-foreground">{item.date ?? "TBD"}</td>
                <td className="px-3 py-2">{item.platform ?? "Channel"}</td>
                <td className="px-3 py-2">{item.topic ?? item.format ?? "Content idea"}</td>
                <td className="px-3 py-2 text-primary">{item.status ?? "Planned"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }
  if (dailyPlan.length) {
    return (
      <div className="space-y-3">
        {dailyPlan.map((day, index) => (
          <section key={`${day.day ?? "day"}-${day.focus ?? index}`} className="rounded-lg border border-border bg-background/50 p-4">
            <p className="text-xs text-primary">{day.day ?? `Day ${index + 1}`}</p>
            <h3 className="mt-1 font-semibold">{day.focus ?? "Focus"}</h3>
            <ul className="mt-2 space-y-1 text-sm text-muted-foreground">{asArray<string>(day.tasks).map((task) => <li key={task}>- {task}</li>)}</ul>
          </section>
        ))}
      </div>
    )
  }
  if (milestones.length) {
    return (
      <div className="grid gap-3 md:grid-cols-2">
        {milestones.map((milestone, index) => (
          <section id={`workflow-section-${index}`} key={`${milestone.name ?? "milestone"}-${index}`} className={`rounded-lg border bg-background/50 p-4 transition ${activeSectionIndex === index ? "border-primary ring-2 ring-primary/35 shadow-[0_0_24px_rgba(124,58,237,0.18)]" : "border-border"}`}>
            <h3 className="font-semibold">{milestone.name ?? "Milestone"}</h3>
            <p className="mt-1 text-xs text-muted-foreground">Priority: {milestone.priority ?? "medium"} / Deadline: {milestone.deadline ?? "TBD"}</p>
            <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
              {asArray<unknown>(milestone.tasks).map((task, taskIndex) => (
                <li key={`${milestone.name ?? "milestone"}-${index}-task-${taskIndex}`}>- {workflowTaskLabel(task)}</li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    )
  }
  return <GenericWorkflowPreview content={content} activeSectionIndex={activeSectionIndex} />
}

function GenericWorkflowPreview({ content, activeSectionIndex }: { content: Record<string, unknown>; activeSectionIndex: number }) {
  const entries = Object.entries(content).filter(([key, value]) => !["draft_type", "target_app", "type"].includes(key) && value !== null && value !== undefined && value !== "")
  return (
    <div className="space-y-3">
      {entries.map(([key, value], index) => (
        <section id={`workflow-section-${index}`} key={key} className={`rounded-lg border bg-background/50 p-4 transition ${activeSectionIndex === index ? "border-primary ring-2 ring-primary/35 shadow-[0_0_24px_rgba(124,58,237,0.18)]" : "border-border"}`}>
          <h3 className="font-semibold capitalize">{key.replaceAll("_", " ")}</h3>
          <div className="mt-2 text-sm leading-relaxed text-muted-foreground">
            {renderValue(value)}
          </div>
        </section>
      ))}
    </div>
  )
}

function renderValue(value: unknown): ReactNode {
  if (Array.isArray(value)) {
    return (
      <div className="space-y-2">
        {value.map((item, index) => (
          <div key={index} className="rounded-md bg-secondary/30 p-2">
            {typeof item === "object" && item !== null ? renderValue(item) : String(item)}
          </div>
        ))}
      </div>
    )
  }
  if (typeof value === "object" && value !== null) {
    return (
      <dl className="space-y-1">
        {Object.entries(value as Record<string, unknown>).map(([key, item]) => (
          <div key={key} className="grid gap-1 sm:grid-cols-[140px_1fr]">
            <dt className="capitalize text-foreground">{key.replaceAll("_", " ")}</dt>
            <dd>{Array.isArray(item) ? item.join(", ") : typeof item === "object" && item !== null ? renderValue(item) : String(item ?? "")}</dd>
          </div>
        ))}
      </dl>
    )
  }
  return <p>{String(value)}</p>
}

function asArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : []
}

function workflowTaskLabel(task: unknown): string {
  if (typeof task === "string") return task
  if (task && typeof task === "object") {
    const record = task as Record<string, unknown>
    return String(record.title ?? record.name ?? record.task ?? record.description ?? "Workflow task")
  }
  return String(task ?? "Workflow task")
}

function workflowContent(content: DraftRecord["content"] | null | undefined): DraftRecord["content"] {
  return content && typeof content === "object" ? content : { title: "Workflow", type: "workflow", owner_agent: "ceaser" }
}
