"use client"

import { create } from "zustand"
import { persist } from "zustand/middleware"

export type FileType = "document" | "spreadsheet" | "presentation" | "image" | "folder" | "pdf"

export interface FileItem {
  id: string
  name: string
  type: FileType
  size?: string
  modifiedAt: string
  agentId?: string
  parentId?: string | null
}

export interface Automation {
  id: string
  name: string
  description?: string
  enabled: boolean
  trigger: string
  agentId?: string
  lastRun?: string
  runCount: number
}

const defaultFiles: FileItem[] = [
  { id: "1", name: "CliniLocker Growth Plan", type: "document", size: "2.4 MB", modifiedAt: "May 24, 2026", agentId: "zeus" },
  { id: "2", name: "Competitor Analysis", type: "spreadsheet", size: "1.2 MB", modifiedAt: "May 22, 2026", agentId: "nova" },
  { id: "3", name: "Pitch Deck v3", type: "presentation", size: "5.8 MB", modifiedAt: "May 20, 2026", agentId: "zeus" },
  { id: "4", name: "Brand Assets", type: "folder", modifiedAt: "May 18, 2026", agentId: "friday" },
  { id: "5", name: "Product Screenshots", type: "image", size: "12.3 MB", modifiedAt: "May 15, 2026", agentId: "atlas" },
  { id: "6", name: "Revenue Model", type: "spreadsheet", size: "856 KB", modifiedAt: "May 14, 2026", agentId: "zeus" },
  { id: "7", name: "Marketing Strategy", type: "document", size: "1.1 MB", modifiedAt: "May 12, 2026", agentId: "friday" },
  { id: "8", name: "Research Notes", type: "folder", modifiedAt: "May 10, 2026", agentId: "nova" }
]

const defaultAutomations: Automation[] = [
  {
    id: "1",
    name: "Daily Briefing",
    description: "Generate morning briefing with key metrics and tasks",
    enabled: true,
    trigger: "Every day at 8:00 AM",
    agentId: "bolt",
    lastRun: "Today, 8:00 AM",
    runCount: 45
  },
  {
    id: "2",
    name: "Weekly Report",
    description: "Compile and send weekly progress report",
    enabled: true,
    trigger: "Every Friday at 5:00 PM",
    agentId: "zeus",
    lastRun: "May 24, 2026",
    runCount: 12
  },
  {
    id: "3",
    name: "Social Media Scheduler",
    description: "Auto-schedule approved social posts",
    enabled: true,
    trigger: "When content is approved",
    agentId: "friday",
    lastRun: "Yesterday, 3:45 PM",
    runCount: 89
  },
  {
    id: "4",
    name: "Competitor Monitor",
    description: "Track competitor updates and news",
    enabled: false,
    trigger: "Every 6 hours",
    agentId: "nova",
    lastRun: "May 20, 2026",
    runCount: 156
  },
  {
    id: "5",
    name: "Task Reminders",
    description: "Send reminders for upcoming tasks",
    enabled: true,
    trigger: "30 minutes before due time",
    agentId: "bolt",
    lastRun: "Today, 9:30 AM",
    runCount: 234
  },
  {
    id: "6",
    name: "Code Deployment",
    description: "Auto-deploy to staging on PR merge",
    enabled: true,
    trigger: "On PR merge to main",
    agentId: "atlas",
    lastRun: "May 23, 2026",
    runCount: 28
  }
]

interface FileAutomationStore {
  files: FileItem[]
  automations: Automation[]
  fileViewMode: "grid" | "list"
  fileSearchQuery: string

  // File actions
  setFileViewMode: (mode: "grid" | "list") => void
  setFileSearchQuery: (query: string) => void
  addFile: (file: Omit<FileItem, "id" | "modifiedAt"> & Partial<Pick<FileItem, "modifiedAt">>) => void
  updateFile: (id: string, updates: Partial<FileItem>) => void
  deleteFile: (id: string) => void
  getFilteredFiles: () => FileItem[]
  getFilesByAgent: (agentId: string) => FileItem[]

  // Automation actions
  toggleAutomation: (id: string) => void
  addAutomation: (automation: Omit<Automation, "id" | "runCount">) => void
  deleteAutomation: (id: string) => void
  runAutomation: (id: string) => void
  getAutomationsByAgent: (agentId: string) => Automation[]
}

export const useFileAutomationStore = create<FileAutomationStore>()(
  persist(
    (set, get) => ({
      files: defaultFiles,
      automations: defaultAutomations,
      fileViewMode: "grid",
      fileSearchQuery: "",

      // File actions
      setFileViewMode: (mode: "grid" | "list") => set({ fileViewMode: mode }),
      setFileSearchQuery: (query: string) => set({ fileSearchQuery: query }),

      addFile: (file: Omit<FileItem, "id" | "modifiedAt"> & Partial<Pick<FileItem, "modifiedAt">>) => {
        const id = Date.now().toString()
        const modifiedAt = file.modifiedAt ?? "Today"
        set((state) => ({
          files: [{ ...file, id, modifiedAt }, ...state.files]
        }))
      },

      updateFile: (id: string, updates: Partial<FileItem>) => {
        set((state) => ({
          files: state.files.map((file) =>
            file.id === id ? { ...file, ...updates, modifiedAt: updates.modifiedAt ?? "Today" } : file
          )
        }))
      },

      deleteFile: (id: string) => {
        set((state) => ({
          files: state.files.filter((f) => f.id !== id)
        }))
      },

      getFilteredFiles: () => {
        const { files, fileSearchQuery } = get()
        if (!fileSearchQuery) return files
        return files.filter((f) =>
          f.name.toLowerCase().includes(fileSearchQuery.toLowerCase())
        )
      },

      getFilesByAgent: (agentId: string) => {
        return get().files.filter((f) => f.agentId === agentId)
      },

      // Automation actions
      toggleAutomation: (id: string) => {
        set((state) => ({
          automations: state.automations.map((a) =>
            a.id === id ? { ...a, enabled: !a.enabled } : a
          )
        }))
      },

      addAutomation: (automation: Omit<Automation, "id" | "runCount">) => {
        const id = Date.now().toString()
        set((state) => ({
          automations: [{ ...automation, id, runCount: 0 }, ...state.automations]
        }))
      },

      deleteAutomation: (id: string) => {
        set((state) => ({
          automations: state.automations.filter((a) => a.id !== id)
        }))
      },

      runAutomation: (id: string) => {
        const now = new Date()
        const timeStr = `Today, ${now.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}`
        set((state) => ({
          automations: state.automations.map((a) =>
            a.id === id ? { ...a, lastRun: timeStr, runCount: a.runCount + 1 } : a
          )
        }))
      },

      getAutomationsByAgent: (agentId: string) => {
        return get().automations.filter((a) => a.agentId === agentId)
      }
    }),
    {
      name: "ceaser-file-automation-store"
    }
  )
)
