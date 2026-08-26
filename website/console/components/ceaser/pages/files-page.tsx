"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import type { ChangeEvent, ReactNode } from "react"
import { draftsApi, type DraftRecord } from "@/lib/api/drafts"
import { filesApi, type DocumentAction, type FileContentRecord, type FileRecord } from "@/lib/api/files"
import { getAccessToken, getApiBaseUrl } from "@/lib/api/client"
import { useApp } from "@/lib/app-context"
import { memoryApi, type MemoryRecord } from "@/lib/api/memory"
import { projectsApi, type ProjectRecord } from "@/lib/api/projects"
import { cn } from "@/lib/utils"
import {
  ChevronDown,
  CloudUpload,
  Copy,
  Download,
  FileArchive,
  FileImage,
  FileSpreadsheet,
  FileText,
  Grid,
  Image as ImageIcon,
  List,
  Loader2,
  MessageSquarePlus,
  Music,
  Presentation,
  Search,
  Send,
  Sparkles,
  Trash2,
  ZoomIn,
} from "lucide-react"

const API_BASE_URL = getApiBaseUrl()

const intelligencePanels = [
  "Executive Summary",
  "Key Insights",
  "Important Concepts",
  "AI Suggestions",
  "Questions Generated",
  "Flashcards",
  "Action Items",
  "Related Memories",
  "Related Projects",
]

type FileFilter = "all" | "pdf" | "document" | "image" | "audio"

export function FilesPage() {
  const { confirmDialog } = useApp()
  const inputRef = useRef<HTMLInputElement>(null)
  const [files, setFiles] = useState<FileRecord[]>([])
  const [drafts, setDrafts] = useState<DraftRecord[]>([])
  const [projects, setProjects] = useState<ProjectRecord[]>([])
  const [memories, setMemories] = useState<MemoryRecord[]>([])
  const [selectedFile, setSelectedFile] = useState<FileContentRecord | null>(null)
  const [analysisByPanel, setAnalysisByPanel] = useState<Record<string, string>>({})
  const [activePanel, setActivePanel] = useState("Executive Summary")
  const [documentQuestion, setDocumentQuestion] = useState("")
  const [searchQuery, setSearchQuery] = useState("")
  const [activeFilter, setActiveFilter] = useState<FileFilter>("all")
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid")
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [activeAction, setActiveAction] = useState<DocumentAction | "question" | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [previewError, setPreviewError] = useState(false)
  const [previewPage, setPreviewPage] = useState(1)
  const [zoomLevel, setZoomLevel] = useState(100)
  const [isProjectPickerOpen, setIsProjectPickerOpen] = useState(false)
  const [isAssigningProject, setIsAssigningProject] = useState(false)

  const filteredFiles = useMemo(() => {
    const query = searchQuery.toLowerCase().trim()
    return files.filter((file) => {
      const type = file.file_type.toLowerCase()
      const matchesQuery = !query || file.name.toLowerCase().includes(query) || type.includes(query)
      const matchesFilter =
        activeFilter === "all" ||
        (activeFilter === "pdf" && type === "pdf") ||
        (activeFilter === "document" && ["docx", "pptx", "xlsx", "txt", "document"].includes(type)) ||
        (activeFilter === "image" && ["png", "jpg", "jpeg"].includes(type)) ||
        (activeFilter === "audio" && ["mp3", "wav", "m4a", "audio"].includes(type))
      return matchesQuery && matchesFilter
    })
  }, [activeFilter, files, searchQuery])

  const selectedType = selectedFile?.file_type.toLowerCase() ?? ""
  const canPreview = ["pdf", "png", "jpg", "jpeg", "txt"].includes(selectedType)
  const pageCount = Number(selectedFile?.extraction_metadata?.pages ?? 1)
  const linkedProject = useMemo(() => projects.find((project) => project.id === selectedFile?.project_id), [projects, selectedFile?.project_id])
  const relatedMemories = useMemo(() => {
    if (!selectedFile) return []
    const name = selectedFile.name.toLowerCase()
    const base = name.replace(/\.[^.]+$/, "").toLowerCase()
    return memories.filter((memory) => {
      const content = memory.content.toLowerCase()
      return content.includes(name) || (base.length > 3 && content.includes(base))
    }).slice(0, 3)
  }, [memories, selectedFile])

  useEffect(() => {
    const boot = async () => {
      setIsLoading(true)
      setLoadError(null)
      try {
        // These sources do not depend on one another. Fetch them together so
        // a slow draft or memory request does not block the file library.
        const [records, draftRecords, projectRecords, memoryRecords] = await Promise.all([
          filesApi.list(),
          draftsApi.list(),
          projectsApi.list(),
          memoryApi.list(),
        ])
        setFiles(records)
        setDrafts(draftRecords)
        setProjects(projectRecords)
        setMemories(memoryRecords)
        if (records[0]) setSelectedFile(await filesApi.get(records[0].id))
      } catch (error) {
        setLoadError(error instanceof Error ? error.message : "Files could not be loaded. Please try again.")
      } finally {
        setIsLoading(false)
      }
    }
    void boot()
  }, [])

  useEffect(() => {
    setPreviewPage(1)
  }, [selectedFile?.id])

  useEffect(() => {
    let objectUrl: string | null = null
    const loadPreview = async () => {
      setPreviewUrl(null)
      setPreviewError(false)
      if (!selectedFile || !canPreview) return
      try {
        const token = getAccessToken()
        const response = await fetch(`${API_BASE_URL}/files/${selectedFile.id}/preview`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        })
        if (!response.ok) throw new Error("Preview unavailable")
        const rawBlob = await response.blob()
        const blob = new Blob([rawBlob], { type: previewMimeType(selectedFile.file_type) })
        objectUrl = URL.createObjectURL(blob)
        setPreviewUrl(objectUrl)
      } catch {
        setPreviewError(true)
      }
    }
    void loadPreview()
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [selectedFile, canPreview])

  const handleUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    setIsUploading(true)
    try {
      const uploaded = await filesApi.upload(file)
      setFiles((current) => [uploaded, ...current])
      setSelectedFile(await filesApi.get(uploaded.id))
      setAnalysisByPanel({})
      setActivePanel("Executive Summary")
    } finally {
      setIsUploading(false)
      event.target.value = ""
    }
  }

  const handleView = async (file: FileRecord) => {
    setSelectedFile(await filesApi.get(file.id))
    setAnalysisByPanel({})
    setActivePanel("Executive Summary")
  }

  const handleAnalyze = async (action: DocumentAction, question?: string) => {
    if (!selectedFile) return
    setActiveAction(question ? "question" : action)
    try {
      const result = await filesApi.analyze(selectedFile.id, action, question)
      const panel = question ? "AI Suggestions" : panelForAction(action)
      setAnalysisByPanel((current) => ({ ...current, [panel]: normalizeAiText(result.response) }))
      setActivePanel(panel)
    } catch (error) {
      const panel = question ? "AI Suggestions" : panelForAction(action)
      const message = error instanceof Error ? error.message : "Analysis could not be completed. Please try again."
      setAnalysisByPanel((current) => ({ ...current, [panel]: message }))
      setActivePanel(panel)
    } finally {
      setActiveAction(null)
    }
  }

  const toggleSummary = () => {
    if (analysisByPanel["Executive Summary"]) {
      setAnalysisByPanel((current) => {
        const next = { ...current }
        delete next["Executive Summary"]
        return next
      })
      return
    }
    void handleAnalyze("summarize")
  }

  const askDocument = async () => {
    if (!documentQuestion.trim()) return
    const question = documentQuestion.trim()
    setDocumentQuestion("")
    await handleAnalyze("explain", question)
  }

  const assignToProject = async (projectId: string | null) => {
    if (!selectedFile) return
    setIsAssigningProject(true)
    try {
      const updated = await filesApi.updateProject(selectedFile.id, projectId)
      setFiles((current) => current.map((file) => file.id === updated.id ? { ...file, project_id: updated.project_id } : file))
      setSelectedFile({ ...selectedFile, project_id: updated.project_id })
      setIsProjectPickerOpen(false)
    } finally {
      setIsAssigningProject(false)
    }
  }

  const deleteFile = async (file: FileRecord) => {
    const confirmed = await confirmDialog({
      title: "Delete file?",
      description: `Delete "${file.name}" from CEASER files? This cannot be undone.`,
      confirmLabel: "Delete",
      tone: "danger",
    })
    if (!confirmed) return
    await filesApi.delete(file.id)
    const remaining = files.filter((item) => item.id !== file.id)
    setFiles(remaining)
    if (selectedFile?.id === file.id) {
      setSelectedFile(remaining[0] ? await filesApi.get(remaining[0].id) : null)
      setAnalysisByPanel({})
      setActivePanel("Executive Summary")
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col spatial-shell p-4">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Files & Knowledge</h1>
          <p className="text-sm text-muted-foreground">Everything CEASER knows about your documents.</p>
        </div>
        <div className="flex items-center gap-2">
          <input ref={inputRef} type="file" className="hidden" accept=".pdf,.docx,.pptx,.xlsx,.txt,.png,.jpg,.jpeg" onChange={(event) => void handleUpload(event)} />
          <button onClick={() => inputRef.current?.click()} disabled={isUploading} className="flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-[0_18px_45px_rgba(79,140,255,0.24)] hover:bg-primary/90 disabled:opacity-50">
            {isUploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <CloudUpload className="h-4 w-4" />}
            Upload File
          </button>
        </div>
      </div>

      <div className="grid min-h-0 flex-1 gap-4 xl:grid-cols-[22rem_minmax(0,1fr)]">
        <aside className="flex min-h-0 flex-col rounded-2xl border border-border bg-card/55 p-3">
          <div className="mb-3 flex items-center justify-between">
            <p className="text-sm font-semibold">File Library</p>
          </div>
          <div className="mb-3 flex items-center gap-2 rounded-xl border border-border bg-background/50 px-3 py-2">
            <Search className="h-4 w-4 text-muted-foreground" />
            <input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="Search" className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground" />
          </div>
          <div className="mb-3 space-y-1 rounded-xl bg-background/35 p-2 text-sm">
            <SmartFilter icon={<Grid className="h-4 w-4" />} label="All Files" active={activeFilter === "all"} onClick={() => setActiveFilter("all")} />
            <SmartFilter icon={<FileText className="h-4 w-4" />} label="PDFs" active={activeFilter === "pdf"} onClick={() => setActiveFilter("pdf")} />
            <SmartFilter icon={<FileArchive className="h-4 w-4" />} label="Documents" active={activeFilter === "document"} onClick={() => setActiveFilter("document")} />
            <SmartFilter icon={<ImageIcon className="h-4 w-4" />} label="Images" active={activeFilter === "image"} onClick={() => setActiveFilter("image")} />
            <SmartFilter icon={<Music className="h-4 w-4" />} label="Audio" active={activeFilter === "audio"} onClick={() => setActiveFilter("audio")} />
          </div>
          <div className="mb-2 flex items-center justify-between text-xs text-muted-foreground">
            <span>File Cards</span>
            <span>{filteredFiles.length}</span>
          </div>
          <div className="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
            {isLoading ? (
              <div className="py-8 text-center text-sm text-muted-foreground">Loading files...</div>
            ) : loadError ? (
              <div className="rounded-xl border border-amber-400/20 bg-amber-400/10 p-4 text-center text-sm text-amber-100">
                {loadError}
              </div>
            ) : filteredFiles.length ? filteredFiles.map((file) => (
              <div key={file.id} className={cn("group flex w-full items-center gap-2 rounded-xl border p-2 transition-all", selectedFile?.id === file.id ? "border-primary bg-primary/12 shadow-[0_0_35px_rgba(79,140,255,0.16)]" : "border-border bg-background/30 hover:border-primary/40 hover:bg-primary/5")}>
                <button onClick={() => void handleView(file)} className="flex min-w-0 flex-1 gap-3 rounded-lg p-1 text-left">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-secondary/70">{getFileIcon(file.file_type)}</div>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold">{file.name}</span>
                    <span className="mt-1 block text-xs text-muted-foreground">{file.file_type.toUpperCase()} / {String(file.extraction_metadata?.pages ?? 1)} page</span>
                    <span className="mt-1 block text-[11px] text-muted-foreground">Last opened {new Date(file.created_at).toLocaleDateString()}</span>
                  </span>
                </button>
                <button onClick={() => void deleteFile(file)} title="Delete file" className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground opacity-70 transition hover:bg-red-500/10 hover:text-red-400 group-hover:opacity-100">
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            )) : (
              <div className="rounded-xl border border-dashed border-border p-5 text-center text-sm text-muted-foreground">No files yet.</div>
            )}
          </div>
        </aside>

        <main className="flex min-h-0 flex-col overflow-hidden rounded-2xl border border-border bg-card/55">
          {selectedFile ? (
            <>
              <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-muted-foreground">Files / {selectedFile.name}</p>
                  <div className="relative max-w-full overflow-hidden">
                    <h2 className="ceaser-marquee text-lg font-semibold">
                      <span>{selectedFile.name}</span>
                    </h2>
                  </div>
                  <p className="text-xs text-muted-foreground">Reading time: {Math.max(1, Math.ceil((selectedFile.extracted_content?.split(/\s+/).length ?? 0) / 180))} min - Pages: {pageCount}</p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <button onClick={() => setZoomLevel((value) => value >= 140 ? 90 : value + 10)} className="flex h-9 items-center gap-2 rounded-xl border border-border bg-background/40 px-3 text-xs font-medium text-muted-foreground hover:bg-secondary hover:text-foreground">
                    <ZoomIn className="h-4 w-4" /> {zoomLevel}%
                  </button>
                  <IconButton label="Copy" icon={<Copy className="h-4 w-4" />} onClick={() => void navigator.clipboard?.writeText(selectedFile.extracted_content)} />
                  <button onClick={() => setIsProjectPickerOpen(true)} className="flex items-center gap-2 rounded-xl border border-border bg-background/40 px-3 py-2 text-xs font-medium hover:bg-secondary">
                    <MessageSquarePlus className="h-4 w-4" /> Add to Project
                  </button>
                  <button onClick={toggleSummary} disabled={Boolean(activeAction)} className="flex items-center gap-2 rounded-xl border border-border bg-background/40 px-3 py-2 text-xs font-medium hover:bg-secondary disabled:opacity-50">
                    {activeAction === "summarize" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                    {activeAction === "summarize" ? "Summarizing..." : analysisByPanel["Executive Summary"] ? "Hide Summary" : "Summarize"}
                  </button>
                  <button onClick={() => void filesApi.download(selectedFile)} className="flex items-center gap-2 rounded-xl border border-border bg-background/40 px-3 py-2 text-xs font-medium hover:bg-secondary">
                    <Download className="h-4 w-4" /> Download
                  </button>
                </div>
              </div>
              {analysisByPanel["Executive Summary"] && (
                <div className="max-h-44 overflow-y-auto border-b border-border bg-primary/5 px-4 py-3">
                  <p className="mb-1 text-xs font-semibold uppercase tracking-[0.14em] text-primary">Summary</p>
                  <p className="text-sm leading-relaxed text-muted-foreground">{analysisByPanel["Executive Summary"]}</p>
                </div>
              )}

              <div className="grid min-h-0 flex-1 grid-cols-[6.5rem_minmax(0,1fr)]">
                <div className="min-h-0 space-y-3 overflow-y-auto border-r border-border bg-background/20 p-3">
                  {Array.from({ length: pageCount }).map((_, index) => (
                    <button key={index} onClick={() => setPreviewPage(index + 1)} className={cn("flex aspect-[3/4] w-full flex-col items-center justify-center rounded-lg border text-xs transition", previewPage === index + 1 ? "border-primary bg-primary/10 text-primary" : "border-border bg-card/60 text-muted-foreground hover:border-primary/40")}>
                      {getFileIcon(selectedFile.file_type)}
                      <span className="mt-2">Page {index + 1}</span>
                    </button>
                  ))}
                </div>
                <DocumentPreview file={selectedFile} previewUrl={previewUrl} previewError={previewError} previewPage={previewPage} zoomLevel={zoomLevel} />
              </div>
            </>
          ) : (
            <div className="flex h-full min-h-96 flex-col items-center justify-center text-center text-muted-foreground">
              <FileText className="mb-3 h-10 w-10" />
              <p className="font-medium text-foreground">Select a document</p>
              <p className="mt-1 text-sm">Upload or choose a file to read and analyze it.</p>
            </div>
          )}
        </main>

      </div>
      {isProjectPickerOpen && selectedFile && (
        <ProjectPicker
          fileName={selectedFile.name}
          projects={projects}
          currentProjectId={selectedFile.project_id ?? null}
          isSaving={isAssigningProject}
          onClose={() => setIsProjectPickerOpen(false)}
          onAssign={(projectId) => void assignToProject(projectId)}
        />
      )}
    </div>
  )
}

function DocumentPreview({ file, previewUrl, previewError, previewPage, zoomLevel }: { file: FileContentRecord; previewUrl: string | null; previewError: boolean; previewPage: number; zoomLevel: number }) {
  const type = file.file_type.toLowerCase()
  const content = formatDocumentPreview(file.extracted_content)
  return (
    <section className="min-h-0 overflow-y-auto bg-[#050B18]/60 p-6">
      <div className="relative mx-auto min-h-full rounded-xl border border-border bg-white p-6 text-slate-950 shadow-[0_24px_80px_rgba(0,0,0,0.32)]" style={{ width: `${zoomLevel}%`, maxWidth: "72rem" }}>
        {previewUrl && type === "pdf" ? (
          <iframe key={`${previewUrl}-${previewPage}`} src={`${previewUrl}#page=${previewPage}&toolbar=0&navpanes=0`} title={file.name} className="h-[72vh] w-full rounded-lg border border-slate-200 bg-white" />
        ) : previewUrl && ["png", "jpg", "jpeg"].includes(type) ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={previewUrl} alt={file.name} className="mx-auto max-h-[72vh] rounded-lg object-contain" />
        ) : (
          <article className="prose prose-slate max-w-none">
            <h1>{file.name.replace(/\.[^.]+$/, "")}</h1>
            {previewError && <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800">{file.extraction_metadata?.generated ? "CEASER restored this generated document from its saved content." : "The original uploaded file is unavailable, so CEASER is showing its saved text. Upload the original again to restore the visual preview."}</p>}
            {content.length ? (
              content.slice(0, 36).map((block, index) => block.kind === "heading" ? (
                <h2 key={index}>{block.text}</h2>
              ) : block.kind === "list" ? (
                <ul key={index}>{block.items.map((item, itemIndex) => <li key={itemIndex}>{item}</li>)}</ul>
              ) : (
                <p key={index}>{block.text}</p>
              ))
            ) : (
              <p>No readable text has been extracted from this file yet.</p>
            )}
          </article>
        )}
      </div>
    </section>
  )
}

type PreviewBlock = { kind: "heading"; text: string } | { kind: "paragraph"; text: string } | { kind: "list"; items: string[] }

function formatDocumentPreview(raw: string): PreviewBlock[] {
  if (!raw.trim()) return []
  let content = raw.trim()
  try {
    const parsed = JSON.parse(content) as Record<string, unknown>
    if (parsed.type === "project_report") {
      const labels: Record<string, string> = {
        executive_summary: "Executive Summary", objective: "Objective", context: "Context",
        key_requirements: "Key Requirements", scope: "Scope", proposed_solution: "Proposed Solution",
        system_workflow: "System / Workflow", components: "Components / Resources",
        implementation: "Implementation Plan", tasks: "Task Breakdown", timeline: "Timeline",
        testing: "Testing & Validation", risks: "Risks & Constraints", expected_outcome: "Expected Outcome",
        next_steps: "Next Steps",
      }
      const blocks: PreviewBlock[] = []
      for (const [key, label] of Object.entries(labels)) {
        const value = parsed[key]
        if (value == null || value === "") continue
        blocks.push({ kind: "heading", text: label })
        blocks.push(...structuredPreviewBlocks(value))
      }
      return blocks
    }
  } catch {
    // Existing plain-text and Markdown documents continue through the parser below.
  }
  return content.split(/\n{2,}/).flatMap((part): PreviewBlock[] => {
    const lines = part.split("\n").map((line) => line.trim()).filter(Boolean)
    if (!lines.length) return []
    if (lines.every((line) => /^[-*]\s+/.test(line))) return [{ kind: "list", items: lines.map((line) => line.replace(/^[-*]\s+/, "")) }]
    if (lines.length === 1 && lines[0].length < 90 && !/[.!?]$/.test(lines[0])) return [{ kind: "heading", text: lines[0].replace(/^#+\s*/, "") }]
    return [{ kind: "paragraph", text: lines.join(" ").replace(/\*\*/g, "") }]
  })
}

function structuredPreviewBlocks(value: unknown): PreviewBlock[] {
  if (Array.isArray(value)) return [{ kind: "list", items: value.map((item) => typeof item === "string" ? item : readableStructuredValue(item)) }]
  if (value && typeof value === "object") return [{ kind: "list", items: Object.entries(value as Record<string, unknown>).map(([key, item]) => `${humanizeKey(key)}: ${readableStructuredValue(item)}`) }]
  return [{ kind: "paragraph", text: String(value) }]
}

function readableStructuredValue(value: unknown): string {
  if (Array.isArray(value)) return value.map(readableStructuredValue).join("; ")
  if (value && typeof value === "object") return Object.entries(value as Record<string, unknown>).map(([key, item]) => `${humanizeKey(key)}: ${readableStructuredValue(item)}`).join("; ")
  return String(value ?? "")
}

function humanizeKey(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function SmartFilter({ icon, label, active = false, onClick }: { icon: ReactNode; label: string; active?: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} className={cn("flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-muted-foreground hover:bg-primary/10 hover:text-foreground", active && "bg-primary/15 text-foreground")}>
      {icon}
      <span>{label}</span>
    </button>
  )
}

function IconButton({ label, icon, onClick }: { label: string; icon: ReactNode; onClick?: () => void }) {
  return (
    <button onClick={onClick} title={label} className="flex h-9 items-center gap-2 rounded-xl border border-border bg-background/40 px-3 text-xs font-medium text-muted-foreground hover:bg-secondary hover:text-foreground">
      {icon}
      <span className="hidden 2xl:inline">{label}</span>
    </button>
  )
}

function FormattedPanelOutput({ content, panel }: { content: string; panel: string }) {
  const blocks = formatPanelBlocks(content, panel)
  return (
    <div className="space-y-3 text-sm leading-relaxed text-foreground/90">
      {blocks.map((block, index) => {
        if (block.type === "heading") {
          return <p key={index} className="font-semibold text-foreground">{block.text}</p>
        }
        if (block.type === "answer") {
          return <p key={index} className="rounded-lg border border-primary/20 bg-primary/10 px-3 py-2 font-medium text-primary">{block.text}</p>
        }
        if (block.type === "bullet") {
          return (
            <div key={index} className="flex gap-2">
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
              <p className="text-muted-foreground">{block.text}</p>
            </div>
          )
        }
        return <p key={index} className="text-muted-foreground">{block.text}</p>
      })}
    </div>
  )
}

function RelatedProjectPanel({ linkedProject, onAdd }: { linkedProject?: ProjectRecord; onAdd: () => void }) {
  if (!linkedProject) {
    return (
      <div className="space-y-3">
        <p className="text-sm leading-relaxed text-muted-foreground">This file is not linked to a project yet.</p>
        <button onClick={onAdd} className="w-full rounded-xl border border-primary/40 bg-primary/10 px-3 py-2 text-sm font-semibold text-primary hover:bg-primary/15">
          Add to Project
        </button>
      </div>
    )
  }
  return (
    <div className="rounded-xl border border-primary/25 bg-primary/10 p-3">
      <p className="text-sm font-semibold text-foreground">{linkedProject.name}</p>
      <p className="mt-1 text-xs text-muted-foreground">{linkedProject.description || "Project context linked to this file."}</p>
      <span className="mt-3 inline-flex rounded-full bg-primary/15 px-2 py-1 text-xs font-medium text-primary">{linkedProject.status}</span>
    </div>
  )
}

function RelatedMemoryPanel({ memories }: { memories: MemoryRecord[] }) {
  if (!memories.length) {
    return <p className="text-sm leading-relaxed text-muted-foreground">No memory has referenced this file yet. When CEASER uses this document in chat, related memories will appear here.</p>
  }
  return (
    <div className="space-y-2">
      {memories.map((memory) => (
        <div key={memory.id} className="rounded-xl border border-border bg-background/40 p-3">
          <p className="text-xs font-semibold uppercase text-primary">{memory.memory_type}</p>
          <p className="mt-1 line-clamp-3 text-sm text-muted-foreground">{memory.content}</p>
        </div>
      ))}
    </div>
  )
}

function ProjectPicker({ fileName, projects, currentProjectId, isSaving, onClose, onAssign }: { fileName: string; projects: ProjectRecord[]; currentProjectId: string | null; isSaving: boolean; onClose: () => void; onAssign: (projectId: string | null) => void }) {
  const [selectedProjectId, setSelectedProjectId] = useState(currentProjectId ?? projects[0]?.id ?? "")
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <section className="w-full max-w-lg rounded-3xl border border-border bg-card p-5 shadow-[0_30px_100px_rgba(0,0,0,0.45)]">
        <div className="mb-5">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">Add to Project</p>
          <h2 className="mt-2 text-xl font-semibold">Link this file to a project</h2>
          <p className="mt-1 truncate text-sm text-muted-foreground">{fileName}</p>
        </div>
        <div className="max-h-72 space-y-2 overflow-y-auto pr-1">
          {projects.length ? projects.map((project) => (
            <button key={project.id} onClick={() => setSelectedProjectId(project.id)} className={cn("flex w-full items-start gap-3 rounded-2xl border p-3 text-left transition", selectedProjectId === project.id ? "border-primary bg-primary/12" : "border-border bg-background/35 hover:border-primary/40")}>
              <span className={cn("mt-1 h-3 w-3 rounded-full border", selectedProjectId === project.id ? "border-primary bg-primary" : "border-muted-foreground")} />
              <span>
                <span className="block font-semibold">{project.name}</span>
                <span className="mt-1 block text-sm text-muted-foreground">{project.description || "No description yet."}</span>
                <span className="mt-2 inline-flex rounded-full bg-secondary px-2 py-1 text-xs text-muted-foreground">{project.status}</span>
              </span>
            </button>
          )) : (
            <div className="rounded-2xl border border-dashed border-border p-5 text-center text-sm text-muted-foreground">No projects found. Create a project first, then come back here.</div>
          )}
        </div>
        <div className="mt-5 flex flex-wrap justify-between gap-2">
          <button onClick={() => onAssign(null)} disabled={isSaving || !currentProjectId} className="rounded-xl border border-border px-4 py-2 text-sm font-medium text-muted-foreground hover:bg-secondary disabled:opacity-50">
            Remove Link
          </button>
          <div className="flex gap-2">
            <button onClick={onClose} className="rounded-xl border border-border px-4 py-2 text-sm font-medium hover:bg-secondary">Cancel</button>
            <button onClick={() => onAssign(selectedProjectId)} disabled={isSaving || !selectedProjectId} className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50">
              {isSaving ? "Adding..." : "Add"}
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}

function panelForAction(action: DocumentAction) {
  if (action === "summarize") return "Executive Summary"
  if (action === "explain") return "AI Suggestions"
  if (action === "notes") return "Key Insights"
  if (action === "mcqs") return "Questions Generated"
  if (action === "flashcards") return "Flashcards"
  if (action === "actions") return "Action Items"
  return "AI Suggestions"
}

function normalizeAiText(value: string) {
  return value
    .replace(/\r/g, "")
    .replace(/#{1,6}\s*/g, "")
    .replace(/\*\*/g, "")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\s+(?=\d+\.\s)/g, "\n\n")
    .replace(/\s+(?=[a-d]\)\s)/gi, "\n")
    .replace(/\s+(?=Answer:\s)/gi, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim()
}

function formatPanelBlocks(content: string, panel: string) {
  const lines = content.split("\n").map((line) => line.trim()).filter(Boolean)
  if (!lines.length) return [{ type: "body", text: "No output generated yet." }]

  return lines.map((line) => {
    const cleaned = line.replace(/^[-*]\s*/, "").trim()
    if (/^answer:/i.test(cleaned)) return { type: "answer", text: cleaned }
    if (/^\d+[.)]\s/.test(cleaned)) return { type: panel === "Questions Generated" ? "heading" : "bullet", text: cleaned }
    if (/^[a-d]\)\s/i.test(cleaned)) return { type: "bullet", text: cleaned }
    if (/^(question|front|back|action|task|step|concept|summary|key insight)s?:/i.test(cleaned)) return { type: "heading", text: cleaned }
    if (cleaned.length < 72 && /:$/.test(cleaned)) return { type: "heading", text: cleaned.replace(/:$/, "") }
    return { type: "body", text: cleaned }
  })
}

function getFileIcon(type: string) {
  const normalized = type.toLowerCase()
  if (normalized === "pdf") return <FileText className="h-5 w-5 text-red-400" />
  if (normalized === "xlsx") return <FileSpreadsheet className="h-5 w-5 text-emerald-400" />
  if (normalized === "pptx") return <Presentation className="h-5 w-5 text-orange-400" />
  if (["png", "jpg", "jpeg"].includes(normalized)) return <FileImage className="h-5 w-5 text-green-400" />
  return <FileText className="h-5 w-5 text-primary" />
}

function previewMimeType(fileType: string) {
  const normalized = fileType.toLowerCase()
  if (normalized === "pdf") return "application/pdf"
  if (normalized === "png") return "image/png"
  if (normalized === "jpg" || normalized === "jpeg") return "image/jpeg"
  if (normalized === "txt") return "text/plain"
  return "application/octet-stream"
}

function getPanelContent(panel: string, file: FileContentRecord | null, draftCount: number) {
  if (!file) return "Select a document to activate this intelligence panel."
  const wordCount = file.extracted_content?.split(/\s+/).filter(Boolean).length ?? 0
  if (panel === "Executive Summary") return file.extracted_content ? `CEASER has extracted about ${wordCount} words from this file. Use Explain or Summarize to create a polished brief.` : "No readable text extracted yet."
  if (panel === "Key Insights") return "Run Summarize or Generate Notes to extract the most important ideas."
  if (panel === "Important Concepts") return "CEASER will identify concepts, definitions, and themes from this document."
  if (panel === "Questions Generated") return "Use Quiz to generate question-and-answer practice from this file."
  if (panel === "Flashcards") return "Use Flashcards to convert the document into revision cards."
  if (panel === "Action Items") return "Use Action Plan to extract next steps, owners, and decisions."
  if (panel === "Related Memories") return "Memory links will appear here when this document is referenced in chat."
  if (panel === "Related Projects") return `Generated workflows available: ${draftCount}. Add this file to a project when you want project context.`
  return "Choose an action from the dock to generate intelligence."
}
