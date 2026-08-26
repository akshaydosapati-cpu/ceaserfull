"use client"

import { useEffect, useState, type ReactNode } from "react"
import { draftsApi, type DraftRecord } from "@/lib/api/drafts"
import { documentsApi, type GeneratedDocument } from "@/lib/api/documents"
import { agents } from "@/lib/data"
import { useApp } from "@/lib/app-context"
import { AgentAvatar } from "../agent-avatar"
import { CheckCircle2, FileText, Loader2, RotateCcw, Trash2 } from "lucide-react"

export function DraftsPage() {
  const { confirmDialog, setCurrentPage } = useApp()
  const [drafts, setDrafts] = useState<DraftRecord[]>([])
  const [documents, setDocuments] = useState<GeneratedDocument[]>([])
  const [activeDraft, setActiveDraft] = useState<DraftRecord | null>(null)
  const [activeDocument, setActiveDocument] = useState<GeneratedDocument | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const load = async () => {
    setIsLoading(true)
    try {
      const [draftResult, documentResult] = await Promise.allSettled([draftsApi.list(), documentsApi.list()])
      const draftRecords = draftResult.status === "fulfilled" ? draftResult.value : []
      const documentRecords = documentResult.status === "fulfilled" ? documentResult.value : []
      setDrafts(draftRecords)
      setDocuments(documentRecords)
      setActiveDraft(draftRecords[0] ?? null)
      setActiveDocument(draftRecords[0] ? null : documentRecords[0] ?? null)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const transition = async (draft: DraftRecord, action: "approved" | "regenerated" | "archived") => {
    const updated = await draftsApi.action(draft.id, action)
    setActiveDraft(updated)
    setDrafts(await draftsApi.list())
  }

  const deleteDraft = async (draft: DraftRecord) => {
    const confirmed = await confirmDialog({
      title: `Delete "${draft.title}"?`,
      description: "This draft will be permanently removed from CEASER. This cannot be undone.",
      confirmLabel: "Delete",
      tone: "danger",
    })
    if (!confirmed) return
    await draftsApi.delete(draft.id)
    const records = await draftsApi.list()
    setDrafts(records)
    setActiveDraft(records[0] ?? null)
    setActiveDocument(records[0] ? null : documents[0] ?? null)
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
              <button key={draft.id} onClick={() => { setActiveDraft(draft); setActiveDocument(null) }} className="mb-2 flex w-full gap-3 rounded-lg border border-border bg-background/40 p-3 text-left hover:bg-secondary">
                {agent ? <AgentAvatar agent={agent} size="sm" /> : <FileText className="h-5 w-5 text-primary" />}
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{draft.title}</span>
                  <span className="text-xs capitalize text-muted-foreground">{draft.draft_type.replace("_", " ")} / {draft.status}</span>
                </span>
              </button>
            )
          })}
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
          {!isLoading && !drafts.length && !documents.length && <p className="py-10 text-center text-sm text-muted-foreground">No workflows yet.</p>}
        </div>
      </aside>

      <main className="min-h-0 overflow-hidden rounded-lg border border-border bg-secondary/20">
        {activeDraft ? (
          <div className="flex h-full min-h-0 flex-col">
            <div className="border-b border-border p-5">
              <h2 className="text-2xl font-semibold">{activeDraft.title}</h2>
              <p className="text-sm capitalize text-muted-foreground">{activeDraft.draft_type.replace("_", " ")} / {activeDraft.status} / {activeDraft.progress}%</p>
              <div className="mt-4 flex gap-2">
                <button onClick={() => void transition(activeDraft, "approved")} className="flex items-center gap-2 rounded-lg border border-emerald-500/50 px-3 py-2 text-sm text-emerald-400"><CheckCircle2 className="h-4 w-4" />Approve</button>
                <button onClick={() => void transition(activeDraft, "regenerated")} className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm hover:bg-secondary"><RotateCcw className="h-4 w-4" />Regenerate</button>
                <button onClick={() => void transition(activeDraft, "archived")} className="rounded-lg border border-border px-3 py-2 text-sm hover:bg-secondary">Archive</button>
                <button onClick={() => void deleteDraft(activeDraft)} className="flex items-center gap-2 rounded-lg border border-red-500/40 px-3 py-2 text-sm text-red-400 hover:bg-red-500/10"><Trash2 className="h-4 w-4" />Delete</button>
              </div>
            </div>
            <div className="grid min-h-0 flex-1 gap-4 p-5 lg:grid-cols-[280px_1fr]">
              <div className="space-y-2">
                {draftOutline(activeDraft).map((title, index) => <div key={`${title}-${index}`} className="rounded-lg border border-border bg-background/40 px-3 py-2 text-sm">{index + 1}. {title}</div>)}
              </div>
              <div className="overflow-y-auto rounded-lg border border-border bg-background/40 p-5">
                <DraftPreview draft={activeDraft} />
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

function draftOutline(draft: DraftRecord): string[] {
  const content = draft.content
  if (content.slides?.length) return content.slides.map((slide) => slide.title)
  if (content.key_findings?.length) return content.key_findings.map((finding) => finding.finding)
  if (content.modules?.length) return content.modules.map((module) => module.name)
  if (content.calendar_items?.length) return content.calendar_items.map((item) => `${item.date ?? "Date"} - ${item.platform ?? "Platform"}`)
  if (content.daily_plan?.length) return content.daily_plan.map((day) => `${day.day}: ${day.focus}`)
  if (content.milestones?.length) return content.milestones.map((milestone) => milestone.name)
  if (content.sections?.length) return content.sections.map((section) => "title" in section ? section.title : section.heading ?? "Section")
  return [draft.title]
}

function DraftPreview({ draft }: { draft: DraftRecord }) {
  const content = draft.content
  if (content.slides?.length) {
    return (
      <div className="space-y-3">
        {content.slides.map((slide) => (
          <section key={slide.slide_number} className="rounded-lg border border-border bg-background/50 p-4">
            <p className="text-xs text-primary">Slide {slide.slide_number}</p>
            <h3 className="mt-1 font-semibold">{slide.title}</h3>
            <p className="mt-1 text-sm text-muted-foreground">{slide.purpose}</p>
            <ul className="mt-3 space-y-1 text-sm">
              {slide.bullets.map((bullet) => <li key={bullet}>- {bullet}</li>)}
            </ul>
            <p className="mt-3 text-xs text-muted-foreground"><span className="text-foreground">Visual:</span> {slide.visual_suggestion}</p>
            <p className="mt-1 text-xs text-muted-foreground"><span className="text-foreground">Speaker notes:</span> {slide.speaker_notes}</p>
          </section>
        ))}
      </div>
    )
  }
  if (content.key_findings?.length) {
    return (
      <div className="space-y-3">
        {typeof content.executive_summary === "string" && <p className="rounded-lg border border-border bg-background/50 p-4 text-sm text-muted-foreground">{content.executive_summary}</p>}
        {content.key_findings.map((finding) => (
          <section key={finding.finding} className="rounded-lg border border-border bg-background/50 p-4">
            <h3 className="font-semibold">{finding.finding}</h3>
            <p className="mt-1 text-sm text-muted-foreground">{finding.evidence}</p>
          </section>
        ))}
      </div>
    )
  }
  if (content.modules?.length) {
    return (
      <div className="space-y-3">
        {content.modules.map((module) => (
          <section key={module.name} className="rounded-lg border border-border bg-background/50 p-4">
            <h3 className="font-semibold">{module.name}</h3>
            <p className="mt-1 text-sm text-muted-foreground">{module.purpose}</p>
            <ul className="mt-2 space-y-1 text-sm text-muted-foreground">{(module.responsibilities ?? []).map((item) => <li key={item}>- {item}</li>)}</ul>
          </section>
        ))}
      </div>
    )
  }
  if (content.calendar_items?.length) {
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
            {content.calendar_items.map((item, index) => (
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
  if (content.daily_plan?.length) {
    return (
      <div className="space-y-3">
        {content.daily_plan.map((day) => (
          <section key={`${day.day}-${day.focus}`} className="rounded-lg border border-border bg-background/50 p-4">
            <p className="text-xs text-primary">{day.day}</p>
            <h3 className="mt-1 font-semibold">{day.focus}</h3>
            <ul className="mt-2 space-y-1 text-sm text-muted-foreground">{(day.tasks ?? []).map((task) => <li key={task}>- {task}</li>)}</ul>
          </section>
        ))}
      </div>
    )
  }
  if (content.milestones?.length) {
    return (
      <div className="grid gap-3 md:grid-cols-2">
        {content.milestones.map((milestone) => (
          <section key={milestone.name} className="rounded-lg border border-border bg-background/50 p-4">
            <h3 className="font-semibold">{milestone.name}</h3>
            <p className="mt-1 text-xs text-muted-foreground">Priority: {milestone.priority ?? "medium"} / Deadline: {milestone.deadline ?? "TBD"}</p>
            <ul className="mt-2 space-y-1 text-sm text-muted-foreground">{milestone.tasks.map((task) => <li key={task}>- {task}</li>)}</ul>
          </section>
        ))}
      </div>
    )
  }
  return <GenericWorkflowPreview content={content} />
}

function GenericWorkflowPreview({ content }: { content: Record<string, unknown> }) {
  const entries = Object.entries(content).filter(([key, value]) => !["draft_type", "target_app", "type"].includes(key) && value !== null && value !== undefined && value !== "")
  return (
    <div className="space-y-3">
      {entries.map(([key, value]) => (
        <section key={key} className="rounded-lg border border-border bg-background/50 p-4">
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
