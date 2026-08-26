"use client"

import { useEffect, useMemo, useState, type ReactNode } from "react"
import { agents } from "@/lib/data"
import { draftsApi, type DraftRecord } from "@/lib/api/drafts"
import { documentsApi, type GeneratedDocument } from "@/lib/api/documents"
import { filesApi, type FileRecord } from "@/lib/api/files"
import { projectsApi, type ProjectRecord } from "@/lib/api/projects"
import { useApp } from "@/lib/app-context"
import { cn } from "@/lib/utils"
import { AgentAvatar } from "../agent-avatar"
import { CeaserSelect } from "../ceaser-select"
import {
  Archive,
  BarChart3,
  CalendarClock,
  Check,
  CheckCircle2,
  Clock3,
  FileText,
  Folder,
  Grid2X2,
  LayoutList,
  Loader2,
  MoreHorizontal,
  Pencil,
  Plus,
  Search,
  Send,
  Star,
  Trash2,
  X,
} from "lucide-react"

type ProjectStatus = "planned" | "active" | "completed" | "archived"
type ProjectTab = "all" | "recent" | "favorites" | "shared" | "archived"
type DetailTab = "overview" | "files" | "tasks" | "activity"
type ViewMode = "grid" | "list"
type SortMode = "recent" | "name" | "status"

const FAVORITES_KEY = "ceaser_favorite_projects"
const PROJECT_WORKFLOW_LINKS_KEY = "ceaser_project_workflow_links"

const statusFilters: { label: string; value: ProjectTab }[] = [
  { label: "All Projects", value: "all" },
  { label: "Recent", value: "recent" },
  { label: "Favorites", value: "favorites" },
  { label: "Shared", value: "shared" },
  { label: "Archived", value: "archived" },
]

const projectStatusOptions: { label: string; value: ProjectStatus; helper: string }[] = [
  { label: "Planned", value: "planned", helper: "Not started yet" },
  { label: "Active", value: "active", helper: "Currently moving" },
  { label: "Completed", value: "completed", helper: "Finished work" },
  { label: "Archived", value: "archived", helper: "Hidden from active flow" },
]

const statusCopy: Record<ProjectStatus, string> = {
  planned: "Planned",
  active: "In Progress",
  completed: "Completed",
  archived: "Archived",
}

const projectAccent = ["#7c3aed", "#3b82f6", "#22c55e", "#f59e0b", "#ec4899", "#06b6d4"]

export function ProjectsPage() {
  const { confirmDialog, promptDialog, setCurrentPage, setIsVoiceModalOpen, setSelectedAgentId } = useApp()
  const [projects, setProjects] = useState<ProjectRecord[]>([])
  const [files, setFiles] = useState<FileRecord[]>([])
  const [drafts, setDrafts] = useState<DraftRecord[]>([])
  const [generatedDocuments, setGeneratedDocuments] = useState<GeneratedDocument[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null)
  const [focusedProjectId, setFocusedProjectId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<ProjectTab>("all")
  const [detailTab, setDetailTab] = useState<DetailTab>("overview")
  const [viewMode, setViewMode] = useState<ViewMode>("grid")
  const [sortMode, setSortMode] = useState<SortMode>("recent")
  const [searchQuery, setSearchQuery] = useState("")
  const [favorites, setFavorites] = useState<string[]>([])
  const [workflowLinks, setWorkflowLinks] = useState<Record<string, string>>({})
  const [isLoading, setIsLoading] = useState(true)
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const [newProject, setNewProject] = useState({ name: "", description: "", status: "planned" as ProjectStatus })

  const selectedProject = projects.find((project) => project.id === selectedProjectId) ?? null

  useEffect(() => {
    try {
      setFavorites(JSON.parse(window.localStorage.getItem(FAVORITES_KEY) || "[]"))
      setWorkflowLinks(JSON.parse(window.localStorage.getItem(PROJECT_WORKFLOW_LINKS_KEY) || "{}"))
    } catch {
      setFavorites([])
    }
  }, [])

  useEffect(() => {
    void loadProjects()
  }, [])

  async function loadProjects() {
    setIsLoading(true)
    try {
      const [projectResult, fileResult, draftResult, documentResult] = await Promise.allSettled([
        projectsApi.list(),
        filesApi.list(),
        draftsApi.list(),
        documentsApi.list(),
      ])
      if (projectResult.status === "fulfilled") {
        setProjects(projectResult.value)
        setSelectedProjectId((current) => current ?? projectResult.value[0]?.id ?? null)
      }
      if (fileResult.status === "fulfilled") setFiles(fileResult.value)
      if (draftResult.status === "fulfilled") setDrafts(draftResult.value)
      if (documentResult.status === "fulfilled") setGeneratedDocuments(documentResult.value)
    } finally {
      setIsLoading(false)
    }
  }

  const filteredProjects = useMemo(() => {
    const query = searchQuery.trim().toLowerCase()
    const now = Date.now()
    const sevenDays = 7 * 24 * 60 * 60 * 1000

    return projects
      .filter((project) => {
        if (focusedProjectId) return project.id === focusedProjectId
        if (activeTab === "archived") return project.status === "archived"
        if (project.status === "archived") return false
        if (activeTab === "favorites") return favorites.includes(project.id)
        if (activeTab === "recent") return now - getProjectTime(project) <= sevenDays
        if (activeTab === "shared") return false
        return true
      })
      .filter((project) => {
        if (!query) return true
        return `${project.name} ${project.description ?? ""} ${project.status}`.toLowerCase().includes(query)
      })
      .sort((a, b) => {
        if (sortMode === "name") return a.name.localeCompare(b.name)
        if (sortMode === "status") return a.status.localeCompare(b.status)
        return getProjectTime(b) - getProjectTime(a)
      })
  }, [activeTab, favorites, focusedProjectId, projects, searchQuery, sortMode])

  const projectFiles = useMemo(() => {
    if (!selectedProject) return []
    return files.filter((file) => file.project_id === selectedProject.id || file.name.toLowerCase().includes(selectedProject.name.toLowerCase()))
  }, [files, selectedProject])

  const projectDrafts = useMemo(() => {
    if (!selectedProject) return []
    return draftsForProject(drafts, selectedProject, projects.length, workflowLinks)
  }, [drafts, projects.length, selectedProject, workflowLinks])

  const projectGeneratedDocuments = useMemo(() => {
    if (!selectedProject) return []
    return documentsForProject(generatedDocuments, selectedProject, projects.length, workflowLinks)
  }, [generatedDocuments, projects.length, selectedProject, workflowLinks])

  const linkedAgents = useMemo(() => {
    const text = `${selectedProject?.name ?? ""} ${selectedProject?.description ?? ""}`.toLowerCase()
    const matched = agents.filter((agent) => {
      if (agent.id === "nova") return /research|market|competitor|analysis|startup|ai/.test(text)
      if (agent.id === "zeus") return /business|strategy|startup|revenue|growth|investor/.test(text)
      if (agent.id === "atlas") return /software|website|platform|app|architecture|technical/.test(text)
      if (agent.id === "friday") return /content|calendar|marketing|social|campaign/.test(text)
      if (agent.id === "alex") return /college|study|learning|exam|personal/.test(text)
      if (agent.id === "bolt") return /task|workflow|execution|launch|plan/.test(text)
      return false
    })
    return matched.length ? matched.slice(0, 3) : agents.slice(0, 3)
  }, [selectedProject])

  const stats = useMemo(
    () => ({
      total: projects.length,
      active: projects.filter((project) => project.status === "active").length,
      completed: projects.filter((project) => project.status === "completed").length,
      archived: projects.filter((project) => project.status === "archived").length,
    }),
    [projects],
  )

  async function createProject() {
    if (!newProject.name.trim()) return
    const project = await projectsApi.create({
      name: newProject.name.trim(),
      description: newProject.description.trim() || null,
      status: newProject.status,
    })
    setProjects((current) => [project, ...current])
    setSelectedProjectId(project.id)
    setDetailTab("overview")
    setNewProject({ name: "", description: "", status: "planned" })
    setIsAddModalOpen(false)
  }

  async function updateProject(projectId: string, updates: Partial<Pick<ProjectRecord, "name" | "description" | "status">>) {
    const updated = await projectsApi.update(projectId, updates)
    setProjects((current) => current.map((project) => (project.id === projectId ? updated : project)))
  }

  async function renameProject(project: ProjectRecord) {
    const name = await promptDialog({
      title: "Rename project",
      description: "Update the project name used across CEASER.",
      defaultValue: project.name,
      confirmLabel: "Rename",
    })
    if (!name) return
    await updateProject(project.id, { name })
  }

  async function deleteProject(project: ProjectRecord) {
    const confirmed = await confirmDialog({
      title: `Delete "${project.name}"?`,
      description: "This removes the project record from CEASER. Linked files and workflows are not deleted.",
      confirmLabel: "Delete",
      tone: "danger",
    })
    if (!confirmed) return
    await projectsApi.delete(project.id)
    setProjects((current) => current.filter((item) => item.id !== project.id))
    setSelectedProjectId((current) => (current === project.id ? null : current))
  }

  function toggleFavorite(projectId: string) {
    setFavorites((current) => {
      const next = current.includes(projectId) ? current.filter((id) => id !== projectId) : [...current, projectId]
      window.localStorage.setItem(FAVORITES_KEY, JSON.stringify(next))
      return next
    })
  }

  return (
    <div className="flex h-full overflow-hidden bg-background text-foreground">
      <main className="min-w-0 flex-1 overflow-y-auto border-r border-border px-6 py-7">
        <div className="mb-7 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">Projects</h1>
            <p className="mt-2 text-sm text-muted-foreground">Organize your work. Connect files, workflows, agents, and progress in one place.</p>
          </div>
          <button onClick={() => setIsAddModalOpen(true)} className="flex h-11 items-center gap-2 rounded-xl bg-gradient-to-r from-violet-500 to-primary px-4 text-sm font-semibold text-white shadow-[0_0_32px_rgba(124,58,237,0.28)]">
            <Plus className="h-4 w-4" />
            New Project
          </button>
        </div>

        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-[280px] flex-1 items-center gap-3 rounded-2xl border border-border bg-card/75 px-4 py-3 text-sm text-muted-foreground shadow-sm">
            <Search className="h-4 w-4" />
            <input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="Search projects, files, agents..." className="min-w-0 flex-1 bg-transparent outline-none placeholder:text-muted-foreground" />
            <kbd className="hidden rounded-md border border-border bg-secondary px-2 py-0.5 text-[11px] md:inline">Ctrl K</kbd>
          </div>
          <div className="flex items-center gap-2">
            <ViewButton active={viewMode === "grid"} onClick={() => setViewMode("grid")}><Grid2X2 className="h-4 w-4" /></ViewButton>
            <ViewButton active={viewMode === "list"} onClick={() => setViewMode("list")}><LayoutList className="h-4 w-4" /></ViewButton>
            <CeaserSelect
              value={sortMode}
              onValueChange={(value) => setSortMode(value as SortMode)}
              options={[
                { value: "recent", label: "Sort: Recent" },
                { value: "name", label: "Sort: Name" },
                { value: "status", label: "Sort: Status" },
              ]}
              triggerClassName="w-[150px]"
            />
          </div>
        </div>

        {focusedProjectId && selectedProject && (
          <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-primary/25 bg-primary/10 px-4 py-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">Project Workspace Open</p>
              <p className="mt-1 text-sm text-slate-200">{selectedProject.name} is focused. Use the side panel tabs for files, draft tasks, and activity.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button onClick={() => setDetailTab("files")} className="rounded-xl border border-border bg-card/70 px-3 py-2 text-xs font-medium transition hover:bg-secondary/70">Files</button>
              <button onClick={() => setDetailTab("tasks")} className="rounded-xl border border-border bg-card/70 px-3 py-2 text-xs font-medium transition hover:bg-secondary/70">Tasks</button>
              <button onClick={() => setDetailTab("activity")} className="rounded-xl border border-border bg-card/70 px-3 py-2 text-xs font-medium transition hover:bg-secondary/70">Activity</button>
              <button onClick={() => setFocusedProjectId(null)} className="rounded-xl bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground transition hover:bg-primary/90">Exit Focus</button>
            </div>
          </div>
        )}

        <div className="mb-6 flex flex-wrap gap-2 rounded-2xl border border-border bg-card/70 p-1 shadow-sm">
          {statusFilters.map((filter) => (
            <button key={filter.value} onClick={() => setActiveTab(filter.value)} className={cn("rounded-xl px-4 py-2 text-sm font-medium transition", activeTab === filter.value ? "bg-primary text-primary-foreground shadow-[0_10px_24px_rgba(79,140,255,0.22)]" : "text-muted-foreground hover:bg-secondary/70 hover:text-foreground")}>
              {filter.label}
            </button>
          ))}
        </div>

        <div className="mb-6 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard icon={<Folder className="h-5 w-5" />} label="Total Projects" value={stats.total} helper="Live DB records" color="#7c3aed" />
          <MetricCard icon={<Clock3 className="h-5 w-5" />} label="Active Projects" value={stats.active} helper="In progress" color="#a855f7" />
          <MetricCard icon={<CheckCircle2 className="h-5 w-5" />} label="Completed" value={stats.completed} helper="Finished" color="#22c55e" />
          <MetricCard icon={<Archive className="h-5 w-5" />} label="Archived" value={stats.archived} helper="View archived" color="#94a3b8" />
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-20 text-sm text-muted-foreground">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Loading projects...
          </div>
        ) : filteredProjects.length ? (
          <div className={cn(viewMode === "grid" ? "grid gap-5 md:grid-cols-2 2xl:grid-cols-3" : "space-y-3")}>
            {filteredProjects.map((project, index) => (
              <ProjectCard
                key={project.id}
                project={project}
                accent={projectAccent[index % projectAccent.length]}
                selected={selectedProject?.id === project.id}
                favorite={favorites.includes(project.id)}
                viewMode={viewMode}
                linkedAgents={agentsForProject(project)}
                filesCount={files.filter((file) => file.project_id === project.id).length}
                draftsCount={draftsForProject(drafts, project, projects.length, workflowLinks).length + documentsForProject(generatedDocuments, project, projects.length, workflowLinks).length}
                onSelect={() => {
                  setSelectedProjectId(project.id)
                  setDetailTab("overview")
                }}
                onFavorite={() => toggleFavorite(project.id)}
                onRename={() => void renameProject(project)}
                onArchive={() => void updateProject(project.id, { status: "archived" })}
                onDelete={() => void deleteProject(project)}
              />
            ))}
          </div>
        ) : (
          <div className="rounded-3xl border border-dashed border-border bg-card/60 p-10 text-center">
            <Folder className="mx-auto h-10 w-10 text-muted-foreground" />
            <p className="mt-4 font-semibold">No projects found</p>
            <p className="mt-1 text-sm text-muted-foreground">Create a project or adjust the current filter.</p>
          </div>
        )}

        <p className="mt-8 text-center text-sm text-muted-foreground">
          Can't find your project? <button onClick={() => setActiveTab("all")} className="text-primary underline">Search all projects</button>
        </p>
      </main>

      <ProjectDetails
        project={selectedProject}
        files={projectFiles}
        drafts={projectDrafts}
        generatedDocuments={projectGeneratedDocuments}
        agents={linkedAgents}
        favorite={Boolean(selectedProject && favorites.includes(selectedProject.id))}
        detailTab={detailTab}
        setDetailTab={setDetailTab}
        statusClass={statusClass}
        onClose={() => setSelectedProjectId(null)}
        onFavorite={() => selectedProject && toggleFavorite(selectedProject.id)}
        onStatus={(status) => selectedProject && void updateProject(selectedProject.id, { status })}
        onRename={() => selectedProject && void renameProject(selectedProject)}
        onDelete={() => selectedProject && void deleteProject(selectedProject)}
        onOpenWorkspace={() => {
          if (!selectedProject) return
          setFocusedProjectId(selectedProject.id)
          setDetailTab("overview")
        }}
        onOpenFiles={() => {
          setDetailTab("files")
          setCurrentPage("files")
        }}
        onCreateWorkflow={async () => {
          if (!selectedProject) return
          const created = await draftsApi.create({
            prompt: `Create a practical workflow for ${selectedProject.name}. Context: ${selectedProject.description || "No description added."}`,
            draft_type: "execution_plan",
            agent_id: "bolt",
            target_app: "keep_as_draft",
            requested_units: 8,
          })
          const nextLinks = { ...workflowLinks, [created.id]: selectedProject.id }
          setWorkflowLinks(nextLinks)
          window.localStorage.setItem(PROJECT_WORKFLOW_LINKS_KEY, JSON.stringify(nextLinks))
          setDrafts((current) => [created, ...current])
          setDetailTab("tasks")
          window.dispatchEvent(new CustomEvent("ceaser:activity-updated"))
        }}
        onContinueResearch={() => {
          if (selectedProject) {
            window.localStorage.setItem(
              "ceaser_chat_seed",
              `Continue research for ${selectedProject.name}. Context: ${selectedProject.description || "No description added."}`,
            )
          }
          setSelectedAgentId("nova")
          setCurrentPage("chat")
        }}
        onVoiceMode={() => setIsVoiceModalOpen(true)}
        onAskProject={(question) => {
          if (selectedProject) window.localStorage.setItem("ceaser_chat_seed", `${question}\n\nProject: ${selectedProject.name}\nContext: ${selectedProject.description || "No description added."}`)
          setCurrentPage("chat")
        }}
      />

      {isAddModalOpen && (
        <CreateProjectModal
          project={newProject}
          setProject={setNewProject}
          onClose={() => setIsAddModalOpen(false)}
          onCreate={() => void createProject()}
        />
      )}
    </div>
  )
}

function ProjectCard({
  project,
  accent,
  selected,
  favorite,
  viewMode,
  linkedAgents,
  filesCount,
  draftsCount,
  onSelect,
  onFavorite,
  onRename,
  onArchive,
  onDelete,
}: {
  project: ProjectRecord
  accent: string
  selected: boolean
  favorite: boolean
  viewMode: ViewMode
  linkedAgents: typeof agents
  filesCount: number
  draftsCount: number
  onSelect: () => void
  onFavorite: () => void
  onRename: () => void
  onArchive: () => void
  onDelete: () => void
}) {
  const compact = viewMode === "list"
  return (
    <article
      onClick={onSelect}
      className={cn(
        "group cursor-pointer rounded-3xl border bg-card/78 p-5 shadow-[0_18px_45px_rgba(15,23,42,0.08)] transition hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-[0_24px_65px_rgba(79,140,255,0.14)]",
        selected ? "border-primary shadow-[0_0_0_1px_rgba(79,140,255,0.32),0_24px_70px_rgba(79,140,255,0.16)]" : "border-border",
        compact && "flex items-center gap-5 rounded-2xl py-4",
      )}
    >
      <div className={cn("flex items-start justify-between gap-3", compact && "w-72 shrink-0")}>
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl text-white shadow-lg" style={{ background: `linear-gradient(135deg, ${accent}, ${accent}88)` }}>
            <Folder className="h-6 w-6" />
          </div>
          <div>
            <h3 className="line-clamp-1 text-lg font-semibold">{project.name}</h3>
            <p className="mt-1 text-xs capitalize text-muted-foreground">{statusCopy[project.status as ProjectStatus] ?? project.status}</p>
          </div>
        </div>
        <ProjectMenu onFavorite={onFavorite} onRename={onRename} onArchive={onArchive} onDelete={onDelete} />
      </div>

      <div className={cn(compact ? "min-w-0 flex-1" : "mt-4")}>
        <p className="line-clamp-2 text-sm leading-relaxed text-muted-foreground">{project.description || "No description added yet."}</p>
        <div className="mt-4 flex flex-wrap gap-2">
          {deriveTags(project).slice(0, 3).map((tag) => <span key={tag} className="rounded-lg bg-secondary px-2.5 py-1 text-xs font-medium text-muted-foreground">{tag}</span>)}
        </div>
      </div>

      <div className={cn("mt-5 flex items-center justify-between gap-4", compact && "mt-0 w-72 shrink-0")}>
        <div className="flex -space-x-2">
          {linkedAgents.slice(0, 3).map((agent) => <AgentAvatar key={agent.id} agent={agent} size="sm" className="rounded-full border-2 border-background" />)}
          {(filesCount + draftsCount) > 0 && <span className="flex h-8 min-w-8 items-center justify-center rounded-full border-2 border-background bg-secondary px-2 text-xs">+{filesCount + draftsCount}</span>}
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation()
              onFavorite()
            }}
            className={cn("transition hover:text-amber-300", favorite && "text-amber-300")}
          >
            <Star className={cn("h-4 w-4", favorite && "fill-current")} />
          </button>
          <span>{formatRelative(project.updated_at || project.created_at)}</span>
        </div>
      </div>
    </article>
  )
}

function ProjectDetails({
  project,
  files,
  drafts,
  generatedDocuments,
  agents: linkedAgents,
  favorite,
  detailTab,
  setDetailTab,
  statusClass,
  onClose,
  onFavorite,
  onStatus,
  onRename,
  onDelete,
  onOpenWorkspace,
  onOpenFiles,
  onCreateWorkflow,
  onContinueResearch,
  onVoiceMode,
  onAskProject,
}: {
  project: ProjectRecord | null
  files: FileRecord[]
  drafts: DraftRecord[]
  generatedDocuments: GeneratedDocument[]
  agents: typeof agents
  favorite: boolean
  detailTab: DetailTab
  setDetailTab: (tab: DetailTab) => void
  statusClass: (status: string) => string
  onClose: () => void
  onFavorite: () => void
  onStatus: (status: ProjectStatus) => void
  onRename: () => void
  onDelete: () => void
  onOpenWorkspace: () => void
  onOpenFiles: () => void
  onCreateWorkflow: () => void | Promise<void>
  onContinueResearch: () => void
  onVoiceMode: () => void
  onAskProject: (question: string) => void
}) {
  const [projectQuestion, setProjectQuestion] = useState("")

  if (!project) {
    return (
      <aside className="hidden w-[390px] shrink-0 items-center justify-center p-6 text-center text-sm text-muted-foreground xl:flex">
        Select a project to view details.
      </aside>
    )
  }

  const nextStep = getSuggestedNextStep(project, files.length, drafts.length + generatedDocuments.length)
  const activity = [
    ...generatedDocuments.slice(0, 3).map((document) => ({ title: `Document: ${document.file_name || document.template_id}`, detail: `${document.agent_id} / ${formatRelative(document.created_at)}` })),
    ...drafts.slice(0, 3).map((draft) => ({ title: `Workflow: ${draft.title}`, detail: `${draft.agent_id} / ${formatRelative(draft.created_at)}` })),
    ...files.slice(0, 3).map((file) => ({ title: `File: ${file.name}`, detail: `${file.file_type} / ${formatRelative(file.created_at)}` })),
  ]

  function submitProjectQuestion() {
    const question = projectQuestion.trim()
    if (!question) return
    setProjectQuestion("")
    onAskProject(question)
  }

  return (
    <aside className="hidden w-[390px] shrink-0 overflow-y-auto border-l border-border bg-card/60 xl:block">
      <div className="border-b border-border p-6">
        <div className="mb-5 flex justify-end">
          <button onClick={onClose} className="flex h-9 w-9 items-center justify-center rounded-xl bg-secondary/70 text-muted-foreground transition hover:bg-secondary hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="flex items-start gap-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500 to-primary text-white shadow-[0_0_28px_rgba(124,58,237,0.35)]">
            <Folder className="h-7 w-7" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-start gap-2">
              <h2 className="line-clamp-2 text-xl font-semibold">{project.name}</h2>
              <button onClick={onFavorite} className={cn("mt-1 text-muted-foreground transition hover:text-amber-300", favorite && "text-amber-300")}>
                <Star className={cn("h-4 w-4", favorite && "fill-current")} />
              </button>
            </div>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{project.description || "No description added."}</p>
          </div>
        </div>
        <div className="mt-5 flex items-center gap-2">
          <button onClick={onOpenWorkspace} className="flex-1 rounded-xl bg-gradient-to-r from-violet-500 to-primary px-4 py-3 text-sm font-semibold text-white">Continue Project</button>
          <button onClick={onRename} className="rounded-xl border border-border bg-card/65 p-3 text-muted-foreground transition hover:bg-secondary/70 hover:text-foreground"><Pencil className="h-4 w-4" /></button>
          <button onClick={onDelete} className="rounded-xl border border-red-400/20 p-3 text-red-300 transition hover:bg-red-500/10"><Trash2 className="h-4 w-4" /></button>
        </div>
      </div>

      <div className="flex border-b border-border px-5">
        {[
          ["overview", "Overview"],
          ["files", `Files (${files.length})`],
          ["tasks", `Workflows (${drafts.length + generatedDocuments.length})`],
          ["activity", "Activity"],
        ].map(([id, label]) => (
          <button key={id} onClick={() => setDetailTab(id as DetailTab)} className={cn("border-b-2 px-3 py-4 text-sm transition", detailTab === id ? "border-violet-400 text-foreground" : "border-transparent text-muted-foreground hover:text-foreground")}>
            {label}
          </button>
        ))}
      </div>

      <div className="space-y-5 p-5">
        {detailTab === "overview" && (
          <>
            <Panel>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">Suggested Next Step</p>
              <h3 className="mt-2 text-base font-semibold">{nextStep.title}</h3>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{nextStep.description}</p>
              <button onClick={nextStep.action === "research" ? onContinueResearch : nextStep.action === "workflow" ? onCreateWorkflow : onOpenWorkspace} className="mt-4 w-full rounded-xl border border-primary/30 bg-primary/10 px-3 py-2 text-sm font-semibold text-primary transition hover:bg-primary/15">
                {nextStep.cta}
              </button>
            </Panel>
            <Panel>
              <p className="mb-4 font-semibold">Quick Actions</p>
              <div className="grid grid-cols-2 gap-2">
                <ActionButton label="Continue Research" onClick={onContinueResearch} />
                <ActionButton label="Create Workflow" onClick={onCreateWorkflow} />
                <ActionButton label="Open Files" onClick={onOpenFiles} />
                <ActionButton label="Voice Mode" onClick={onVoiceMode} />
              </div>
            </Panel>
            <Panel>
              <p className="mb-4 font-semibold">Project Knowledge</p>
              <InfoRow label="Files" value={String(files.length)} />
              <InfoRow label="Workflows" value={String(drafts.length + generatedDocuments.length)} />
              <InfoRow label="Generated Docs" value={String(generatedDocuments.length)} />
              <InfoRow label="Reports" value={String(drafts.filter((draft) => draft.draft_type === "research").length)} />
              <InfoRow label="Agents" value={String(linkedAgents.length)} />
            </Panel>
            <Panel>
              <p className="mb-4 font-semibold">Project Brief</p>
              <InfoRow label="Created" value={formatDate(project.created_at)} />
              <InfoRow label="Last Updated" value={formatRelative(project.updated_at || project.created_at)} />
              <InfoRow label="Owner" value="You" />
              <InfoRow label="Status" value={statusCopy[project.status as ProjectStatus] ?? project.status} badge={statusClass(project.status)} />
              <InfoRow label="Visibility" value="Private" />
            </Panel>
            <Panel>
              <p className="mb-4 font-semibold">Status</p>
              <div className="grid gap-2">
                {projectStatusOptions.map((status) => (
                  <button key={status.value} onClick={() => onStatus(status.value)} className={cn("flex items-center justify-between rounded-xl border px-3 py-2 text-left transition", project.status === status.value ? "border-primary bg-primary/10 text-primary" : "border-border bg-secondary/30 text-muted-foreground hover:bg-secondary/60 hover:text-foreground")}>
                    <span>
                      <span className="block text-sm font-medium">{status.label}</span>
                      <span className="text-xs text-muted-foreground">{status.helper}</span>
                    </span>
                    {project.status === status.value && <Check className="h-4 w-4" />}
                  </button>
                ))}
              </div>
            </Panel>
            <Panel>
              <p className="mb-4 font-semibold">Currently Working</p>
              <div className="space-y-3">
                {linkedAgents.map((agent, index) => (
                  <div key={agent.id} className="flex items-center gap-3">
                    <AgentAvatar agent={agent} size="md" showGlow />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium">{agent.name}</p>
                      <p className="line-clamp-1 text-xs text-muted-foreground">{index === 0 ? getAgentProjectTask(agent.id) : "Ready when needed"}</p>
                    </div>
                    <span className="h-2 w-2 rounded-full bg-emerald-400" />
                  </div>
                ))}
              </div>
            </Panel>
            <Panel>
              <p className="mb-3 font-semibold">Ask CEASER About This Project</p>
              <div className="flex items-center gap-2 rounded-2xl border border-border bg-card/70 px-3 py-2">
                <input
                  value={projectQuestion}
                  onChange={(event) => setProjectQuestion(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") submitProjectQuestion()
                  }}
                  placeholder="Summarize progress, create report, find competitors..."
                  className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
                />
                <button onClick={submitProjectQuestion} className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground transition hover:bg-primary/90">
                  <Send className="h-4 w-4" />
                </button>
              </div>
            </Panel>
          </>
        )}

        {detailTab === "files" && (
          <Panel>
            <p className="mb-4 font-semibold">Linked Files</p>
            <List items={files.map((file) => ({ title: file.name, detail: `${file.file_type} / ${formatRelative(file.created_at)}`, icon: <FileText className="h-4 w-4" /> }))} empty="No linked files yet." />
          </Panel>
        )}

        {detailTab === "tasks" && (
          <Panel>
            <p className="mb-4 font-semibold">Project Workflows</p>
            <List
              items={[
                ...drafts.map((draft) => ({ title: draft.title, detail: `${draft.draft_type} / ${draft.status} / ${draft.progress}%`, icon: <BarChart3 className="h-4 w-4" /> })),
                ...generatedDocuments.map((document) => ({ title: document.file_name || document.template_id, detail: `${document.export_format.toUpperCase()} / ${document.agent_id} / ${formatRelative(document.created_at)}`, icon: <FileText className="h-4 w-4" /> })),
              ]}
              empty="No project workflows yet."
            />
          </Panel>
        )}

        {detailTab === "activity" && (
          <Panel>
            <p className="mb-4 font-semibold">Recent Activity</p>
            <List items={activity.map((item) => ({ ...item, icon: <CalendarClock className="h-4 w-4" /> }))} empty="No activity linked yet." />
          </Panel>
        )}
      </div>
    </aside>
  )
}

function CreateProjectModal({ project, setProject, onClose, onCreate }: { project: { name: string; description: string; status: ProjectStatus }; setProject: (project: { name: string; description: string; status: ProjectStatus }) => void; onClose: () => void; onCreate: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-4 backdrop-blur-sm">
      <section className="w-full max-w-lg rounded-3xl border border-border bg-card p-5 shadow-2xl">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Create Project</h2>
            <p className="text-sm text-muted-foreground">Create a live DB-backed project record.</p>
          </div>
          <button onClick={onClose} className="rounded-xl p-2 text-muted-foreground transition hover:bg-secondary hover:text-foreground"><X className="h-5 w-5" /></button>
        </div>
        <div className="space-y-4">
          <input value={project.name} onChange={(event) => setProject({ ...project, name: event.target.value })} placeholder="Project name" className="h-12 w-full rounded-2xl border border-border bg-secondary/40 px-4 outline-none focus:border-primary" />
          <textarea value={project.description} onChange={(event) => setProject({ ...project, description: event.target.value })} placeholder="Description" rows={4} className="w-full resize-none rounded-2xl border border-border bg-secondary/40 px-4 py-3 outline-none focus:border-primary" />
          <div className="grid grid-cols-2 gap-2">
            {projectStatusOptions.map((status) => (
              <button key={status.value} type="button" onClick={() => setProject({ ...project, status: status.value })} className={cn("rounded-2xl border p-3 text-left transition", project.status === status.value ? "border-primary bg-primary/10 text-primary" : "border-border bg-secondary/35 text-muted-foreground hover:text-foreground")}>
                <span className="block text-sm font-semibold">{status.label}</span>
                <span className="text-xs">{status.helper}</span>
              </button>
            ))}
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-xl border border-border px-4 py-2 text-sm">Cancel</button>
          <button onClick={onCreate} disabled={!project.name.trim()} className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50">Create Project</button>
        </div>
      </section>
    </div>
  )
}

function ProjectMenu({ onFavorite, onRename, onArchive, onDelete }: { onFavorite: () => void; onRename: () => void; onArchive: () => void; onDelete: () => void }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="relative">
      <button type="button" onClick={(event) => { event.stopPropagation(); setOpen((current) => !current) }} className="rounded-xl p-2 text-muted-foreground opacity-70 transition hover:bg-white/10 hover:text-foreground group-hover:opacity-100">
        <MoreHorizontal className="h-4 w-4" />
      </button>
      {open && (
        <div className="absolute right-0 top-9 z-20 w-40 rounded-2xl border border-border bg-popover p-1 shadow-2xl">
          <MenuItem label="Favorite" onClick={onFavorite} />
          <MenuItem label="Rename" onClick={onRename} />
          <MenuItem label="Archive" onClick={onArchive} />
          <MenuItem label="Delete" danger onClick={onDelete} />
        </div>
      )}
    </div>
  )
}

function MenuItem({ label, danger, onClick }: { label: string; danger?: boolean; onClick: () => void }) {
  return <button type="button" onClick={(event) => { event.stopPropagation(); onClick() }} className={cn("w-full rounded-xl px-3 py-2 text-left text-sm transition hover:bg-white/10", danger && "text-red-300 hover:bg-red-500/10")}>{label}</button>
}

function MetricCard({ icon, label, value, helper, color }: { icon: ReactNode; label: string; value: number; helper: string; color: string }) {
  return (
    <section className="rounded-2xl border border-border bg-card/72 p-4 shadow-[0_16px_38px_rgba(15,23,42,0.07)]">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl" style={{ backgroundColor: `${color}22`, color }}>{icon}</span>
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="mt-1 text-2xl font-semibold">{value}</p>
        </div>
      </div>
      <p className="mt-3 text-xs text-muted-foreground">{helper}</p>
    </section>
  )
}

function ViewButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return <button onClick={onClick} className={cn("flex h-11 w-11 items-center justify-center rounded-xl border transition", active ? "border-primary/50 bg-primary/15 text-primary" : "border-border bg-card/70 text-muted-foreground hover:bg-secondary/70 hover:text-foreground")}>{children}</button>
}

function Panel({ children }: { children: ReactNode }) {
  return <section className="rounded-2xl border border-border bg-card/68 p-4 shadow-[0_14px_34px_rgba(15,23,42,0.06)]">{children}</section>
}

function ActionButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button onClick={onClick} className="rounded-xl border border-border bg-secondary/45 px-3 py-2 text-left text-xs font-semibold text-foreground transition hover:border-primary/40 hover:bg-primary/10 hover:text-primary">
      {label}
    </button>
  )
}

function InfoRow({ label, value, badge }: { label: string; value: string; badge?: string }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-3 text-sm last:mb-0">
      <span className="text-muted-foreground">{label}</span>
      {badge ? <span className={cn("rounded-full px-2 py-1 text-xs font-semibold capitalize", badge)}>{value}</span> : <span className="text-right text-foreground">{value}</span>}
    </div>
  )
}

function List({ items, empty }: { items: Array<{ title: string; detail: string; icon: ReactNode }>; empty: string }) {
  if (!items.length) return <p className="rounded-xl border border-border bg-secondary/35 p-4 text-sm text-muted-foreground">{empty}</p>
  return (
    <div className="space-y-2">
      {items.map((item) => (
        <div key={`${item.title}-${item.detail}`} className="flex items-center gap-3 rounded-xl border border-border bg-secondary/35 p-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-violet-500/10 text-violet-300">{item.icon}</span>
          <span className="min-w-0 flex-1">
            <span className="line-clamp-1 text-sm font-medium">{item.title}</span>
            <span className="line-clamp-1 text-xs text-muted-foreground">{item.detail}</span>
          </span>
        </div>
      ))}
    </div>
  )
}

function statusClass(status: string) {
  if (status === "active") return "bg-emerald-500/15 text-emerald-300"
  if (status === "completed") return "bg-primary/15 text-primary"
  if (status === "archived") return "bg-slate-500/15 text-slate-300"
  return "bg-amber-500/15 text-amber-300"
}

function getProjectTime(project: ProjectRecord) {
  const value = project.updated_at || project.created_at
  const date = value ? new Date(value) : new Date(0)
  return Number.isNaN(date.getTime()) ? 0 : date.getTime()
}

function formatDate(value?: string) {
  if (!value) return "Not available"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "Not available"
  return date.toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" })
}

function formatRelative(value?: string) {
  if (!value) return "Updated recently"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "Updated recently"
  const diff = Date.now() - date.getTime()
  const minutes = Math.max(1, Math.floor(diff / 60000))
  if (minutes < 60) return `Updated ${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `Updated ${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `Updated ${days}d ago`
  return formatDate(value)
}

function deriveTags(project: ProjectRecord) {
  const text = `${project.name} ${project.description ?? ""}`.toLowerCase()
  const tags = new Set<string>()
  if (/research|market|competitor|analysis/.test(text)) tags.add("Research")
  if (/ai|automation|agent/.test(text)) tags.add("AI")
  if (/strategy|business|growth|revenue/.test(text)) tags.add("Strategy")
  if (/content|calendar|social|marketing/.test(text)) tags.add("Content")
  if (/software|website|platform|app|code/.test(text)) tags.add("Development")
  if (/college|study|education|exam/.test(text)) tags.add("Education")
  if (!tags.size) tags.add(statusCopy[project.status as ProjectStatus] ?? "Project")
  return Array.from(tags)
}

function agentsForProject(project: ProjectRecord) {
  const text = `${project.name} ${project.description ?? ""}`.toLowerCase()
  const matched = agents.filter((agent) => {
    if (agent.id === "nova") return /research|market|competitor|analysis|ai/.test(text)
    if (agent.id === "zeus") return /business|strategy|growth|revenue|investor|startup/.test(text)
    if (agent.id === "atlas") return /software|website|platform|app|code|technical/.test(text)
    if (agent.id === "friday") return /content|calendar|social|marketing/.test(text)
    if (agent.id === "alex") return /college|study|education|exam|personal/.test(text)
    if (agent.id === "bolt") return /task|workflow|execution|launch|plan/.test(text)
    return false
  })
  return matched.length ? matched.slice(0, 3) : agents.slice(0, 3)
}

function draftsForProject(drafts: DraftRecord[], project: ProjectRecord, projectCount: number, workflowLinks: Record<string, string>) {
  if (projectCount === 1) return drafts
  return drafts.filter((draft) => workflowLinks[draft.id] === project.id || textMatchesProject(`${draft.title} ${draft.source_prompt}`, project))
}

function documentsForProject(documents: GeneratedDocument[], project: ProjectRecord, projectCount: number, workflowLinks: Record<string, string>) {
  if (projectCount === 1) return documents
  return documents.filter((document) => workflowLinks[document.id] === project.id || textMatchesProject(`${document.file_name ?? ""} ${document.source_prompt}`, project))
}

function textMatchesProject(value: string, project: ProjectRecord) {
  const text = value.toLowerCase()
  const projectName = project.name.toLowerCase()
  if (text.includes(projectName)) return true
  const tokens = projectName.split(/\s+/).filter((token) => token.length > 3)
  return tokens.length > 0 && tokens.some((token) => text.includes(token))
}

function getSuggestedNextStep(project: ProjectRecord, filesCount: number, draftsCount: number) {
  if (project.status === "planned") {
    return {
      title: "Start with project context",
      description: "Create the first workflow so CEASER has a concrete direction for this workspace.",
      cta: "Create Workflow",
      action: "workflow" as const,
    }
  }
  if (draftsCount > 0) {
    return {
      title: "Continue the latest workflow",
      description: "There is generated work connected to this project. Review it, refine it, or turn it into the next output.",
      cta: "Continue Project",
      action: "workspace" as const,
    }
  }
  if (filesCount > 0) {
    return {
      title: "Turn project files into output",
      description: "Files are linked. Ask CEASER to summarize them, extract actions, or generate a report.",
      cta: "Create Workflow",
      action: "workflow" as const,
    }
  }
  return {
    title: "Continue research",
    description: "Nova can gather context, sources, and competitor signals before the next project output.",
    cta: "Continue Research",
    action: "research" as const,
  }
}

function getAgentProjectTask(agentId: string) {
  if (agentId === "nova") return "Researching context and sources"
  if (agentId === "zeus") return "Preparing business direction"
  if (agentId === "atlas") return "Mapping technical requirements"
  if (agentId === "friday") return "Ready to create content outputs"
  if (agentId === "alex") return "Organizing learning and personal context"
  if (agentId === "bolt") return "Preparing execution steps"
  return "Ready for project work"
}
