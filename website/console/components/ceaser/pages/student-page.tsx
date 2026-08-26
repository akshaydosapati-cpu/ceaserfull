"use client"

import { useMemo, type ReactNode } from "react"
import { useApp } from "@/lib/app-context"
import { cn } from "@/lib/utils"
import {
  Bell,
  BookOpen,
  BriefcaseBusiness,
  CalendarDays,
  CheckCircle2,
  ClipboardList,
  FileText,
  GraduationCap,
  Mic2,
  PenLine,
  Search,
  Sparkles,
  Target,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"

type StudentProfile = {
  college?: string
  course?: string
  department?: string
  semester?: string
  graduationYear?: string
}

const PROFILE_KEY = "ceaser_user_profile"

const quickActions = [
  { title: "Study", detail: "Notes, explainers, flashcards", icon: BookOpen, prompt: "Help me study from my notes and create a revision plan." },
  { title: "Assignments", detail: "Outline, draft, references", icon: PenLine, prompt: "Help me plan an assignment with outline, references, and final draft structure." },
  { title: "Exams", detail: "Timetable, MCQs, revision", icon: CalendarDays, prompt: "Create an exam study plan with daily timetable, revision schedule, MCQs, and flashcards." },
  { title: "Projects", detail: "Research, PPT, files, tasks", icon: ClipboardList, prompt: "Create a student project workspace with research, tasks, files, and timeline." },
  { title: "Career", detail: "Resume, jobs, interview prep", icon: BriefcaseBusiness, prompt: "Help me improve my resume and prepare for internships." },
  { title: "Research", detail: "Papers, summaries, sources", icon: Search, prompt: "Research this academic topic and give sources, summary, and key points." },
]

const studyTools = [
  "Explain in simple English",
  "Generate study notes",
  "Create flashcards",
  "Create MCQs",
  "Make a revision sheet",
  "Summarize chapter",
]

const assignmentFlow = ["Understand question", "Research safely", "Create outline", "Draft sections", "Add references", "Export / save"]
const careerFlow = ["Resume builder", "Cover letter", "LinkedIn improvement", "Interview practice", "Skill roadmap", "Job tracker"]

export function StudentPage() {
  const { setCurrentPage } = useApp()
  const profile = useMemo(readProfile, [])
  const student = profile?.studentProfile || {}
  const firstName = profile?.name?.split(" ")[0] || "Student"

  function openChat(prompt: string) {
    window.localStorage.setItem("ceaser_chat_seed", prompt)
    setCurrentPage("chat")
  }

  return (
    <div className="space-y-6 p-6">
      <section className="overflow-hidden rounded-[2rem] border border-border bg-card/80 p-6 shadow-[0_30px_120px_rgba(0,0,0,0.28)]">
        <div className="grid gap-6 lg:grid-cols-[1.3fr_0.7fr]">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-primary">Student OS</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight">Welcome back, {firstName}</h1>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
              CEASER brings study material, assignments, exams, projects, career prep, and desktop voice into one academic operating layer.
            </p>
            <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <ProfilePill label="College" value={student.college || "Add in onboarding"} />
              <ProfilePill label="Course" value={student.course || "Student Mode"} />
              <ProfilePill label="Department" value={student.department || "Not set"} />
              <ProfilePill label="Semester" value={student.semester || "Not set"} />
            </div>
          </div>
          <div className="rounded-3xl border border-primary/20 bg-primary/10 p-5">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary text-primary-foreground">
                <GraduationCap className="h-6 w-6" />
              </div>
              <div>
                <p className="font-semibold">Today’s Study Plan</p>
                <p className="text-xs text-muted-foreground">Generated from tasks, files, and exam goals.</p>
              </div>
            </div>
            <div className="mt-4 space-y-2 text-sm">
              {["Review priority topic", "Generate notes from uploaded PDF", "Practice 10 MCQs", "Update project progress"].map((item) => (
                <div key={item} className="flex items-center gap-2 rounded-2xl bg-background/40 px-3 py-2">
                  <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {quickActions.map((action) => {
          const Icon = action.icon
          return (
            <button
              key={action.title}
              onClick={() => openChat(action.prompt)}
              className="group rounded-3xl border border-border bg-card/70 p-5 text-left transition hover:-translate-y-0.5 hover:border-primary/60 hover:bg-primary/10"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-secondary text-primary">
                  <Icon className="h-5 w-5" />
                </div>
                <span className="rounded-full bg-background/60 px-3 py-1 text-xs text-muted-foreground group-hover:text-primary">Ask CEASER</span>
              </div>
              <h3 className="mt-4 font-semibold">{action.title}</h3>
              <p className="mt-1 text-sm text-muted-foreground">{action.detail}</p>
            </button>
          )
        })}
      </section>

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <Panel title="Study Workspace" icon={BookOpen} subtitle="Turn PDFs, notes, slides, books, and papers into learning assets.">
          <div className="grid gap-2 sm:grid-cols-2">
            {studyTools.map((tool) => <ActionChip key={tool} label={tool} onClick={() => setCurrentPage("files")} />)}
          </div>
        </Panel>

        <Panel title="Exam Mode" icon={Target} subtitle="Subject + exam date + hours/day becomes a practical revision system.">
          <Flow items={["Study plan", "Revision schedule", "Weak topics", "MCQs", "Flashcards", "One-day sheet"]} />
          <button onClick={() => openChat("Create an exam mode plan for my next exam with timetable, topics, MCQs, flashcards, and revision sheet.")} className="mt-4 rounded-2xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground">
            Create Exam Plan
          </button>
        </Panel>

        <Panel title="Assignment Mode" icon={PenLine} subtitle="Academic help with planning, research, outlines, citations, and drafts. No cheating automation.">
          <Flow items={assignmentFlow} />
          <button onClick={() => openChat("Help me complete an assignment ethically: understand the question, create outline, research references, and draft sections.")} className="mt-4 rounded-2xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground">
            Start Assignment
          </button>
        </Panel>

        <Panel title="Project Workspace" icon={FileText} subtitle="Each college project keeps research, docs, PPTs, files, chat, notes, tasks, timeline, and references together.">
          <div className="grid gap-3 sm:grid-cols-3">
            <Metric label="Files" value="Live" />
            <Metric label="Tasks" value="Linked" />
            <Metric label="Agents" value="Ready" />
          </div>
          <button onClick={() => setCurrentPage("projects")} className="mt-4 rounded-2xl border border-border px-4 py-2 text-sm font-semibold hover:bg-secondary">
            Open Projects
          </button>
        </Panel>
      </div>

      <section className="grid gap-6 xl:grid-cols-3">
        <Panel title="Career Hub" icon={BriefcaseBusiness} subtitle="Resume, internships, portfolio, LinkedIn help, interviews, and skill roadmap.">
          <Flow items={careerFlow} />
        </Panel>
        <Panel title="Career Watch" icon={Bell} subtitle="Future job discovery layer. Providers can be plugged in without redesigning the UI.">
          <div className="space-y-2">
            {["Role watch", "Location watch", "Salary range", "Experience level", "Skill keywords"].map((item) => <StatusRow key={item} label={item} status="Ready" />)}
          </div>
        </Panel>
        <Panel title="Desktop Voice" icon={Mic2} subtitle="Hold Right Ctrl, speak the command, release. CEASER routes study, career, files, or desktop work.">
          <div className="rounded-3xl border border-primary/20 bg-primary/10 p-4">
            <p className="text-sm font-semibold">Example</p>
            <p className="mt-2 text-sm text-muted-foreground">“Create a 7 day study plan for my DBMS exam.”</p>
          </div>
        </Panel>
      </section>
    </div>
  )
}

function readProfile(): { name?: string; useCase?: string; studentProfile?: StudentProfile } | null {
  if (typeof window === "undefined") return null
  try {
    return JSON.parse(window.localStorage.getItem(PROFILE_KEY) || "null")
  } catch {
    return null
  }
}

function ProfilePill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border bg-background/40 px-4 py-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 line-clamp-1 text-sm font-semibold">{value}</p>
    </div>
  )
}

function Panel({ title, subtitle, icon: Icon, children }: { title: string; subtitle: string; icon: LucideIcon; children: ReactNode }) {
  return (
    <section className="rounded-[1.75rem] border border-border bg-card/70 p-5">
      <div className="flex items-start gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-secondary text-primary">
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <h2 className="font-semibold">{title}</h2>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{subtitle}</p>
        </div>
      </div>
      <div className="mt-5">{children}</div>
    </section>
  )
}

function ActionChip({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button onClick={onClick} className="rounded-2xl border border-border bg-background/50 px-3 py-2 text-left text-sm transition hover:border-primary/60 hover:bg-primary/10">
      {label}
    </button>
  )
}

function Flow({ items }: { items: string[] }) {
  return (
    <div className="space-y-2">
      {items.map((item, index) => (
        <div key={item} className="flex items-center gap-3 rounded-2xl bg-background/40 px-3 py-2 text-sm">
          <span className={cn("flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold", index === 0 ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground")}>{index + 1}</span>
          <span>{item}</span>
        </div>
      ))}
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-background/40 p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 font-semibold">{value}</p>
    </div>
  )
}

function StatusRow({ label, status }: { label: string; status: string }) {
  return (
    <div className="flex items-center justify-between rounded-2xl bg-background/40 px-3 py-2 text-sm">
      <span>{label}</span>
      <span className="rounded-full bg-emerald-500/10 px-2 py-1 text-xs text-emerald-300">{status}</span>
    </div>
  )
}
