"use client"

import { create } from "zustand"
import { persist } from "zustand/middleware"

export type ProjectStatus = "ongoing" | "planning" | "completed" | "paused"

export interface Project {
  id: string
  name: string
  status: ProjectStatus
  progress: number
  agentId?: string
  description?: string
  createdAt: string
  updatedAt: string
}

const defaultProjects: Project[] = [
  {
    id: "1",
    name: "CliniLocker",
    status: "ongoing",
    progress: 70,
    agentId: "zeus",
    description: "Healthcare SaaS platform",
    createdAt: "2026-04-01",
    updatedAt: "2026-05-24"
  },
  {
    id: "2",
    name: "AI Research",
    status: "ongoing",
    progress: 45,
    agentId: "nova",
    description: "AI and ML research initiative",
    createdAt: "2026-04-15",
    updatedAt: "2026-05-20"
  },
  {
    id: "3",
    name: "Content Hub",
    status: "planning",
    progress: 30,
    agentId: "friday",
    description: "Content management and distribution",
    createdAt: "2026-05-01",
    updatedAt: "2026-05-18"
  },
  {
    id: "4",
    name: "Personal Fitness Plan",
    status: "ongoing",
    progress: 60,
    agentId: "alex",
    description: "Health and fitness tracking",
    createdAt: "2026-03-01",
    updatedAt: "2026-05-22"
  },
  {
    id: "5",
    name: "Marketing Strategy",
    status: "ongoing",
    progress: 55,
    agentId: "friday",
    description: "Brand marketing and growth",
    createdAt: "2026-04-20",
    updatedAt: "2026-05-19"
  },
  {
    id: "6",
    name: "SaaS Idea Validation",
    status: "planning",
    progress: 20,
    agentId: "nova",
    description: "Market validation for new SaaS idea",
    createdAt: "2026-05-10",
    updatedAt: "2026-05-15"
  }
]

interface ProjectStore {
  projects: Project[]
  filterStatus: ProjectStatus | "all"
  searchQuery: string

  // Actions
  setFilterStatus: (status: ProjectStatus | "all") => void
  setSearchQuery: (query: string) => void
  addProject: (project: Omit<Project, "id" | "createdAt" | "updatedAt">) => void
  updateProject: (id: string, updates: Partial<Project>) => void
  deleteProject: (id: string) => void
  getFilteredProjects: () => Project[]
  getProjectsByAgent: (agentId: string) => Project[]
  getProjectsByStatus: (status: ProjectStatus) => Project[]
}

export const useProjectStore = create<ProjectStore>()(
  persist(
    (set, get) => ({
      projects: defaultProjects,
      filterStatus: "all",
      searchQuery: "",

      setFilterStatus: (status: ProjectStatus | "all") => set({ filterStatus: status }),
      setSearchQuery: (query: string) => set({ searchQuery: query }),

      addProject: (project: Omit<Project, "id" | "createdAt" | "updatedAt">) => {
        const now = new Date().toISOString().split("T")[0]
        const id = Date.now().toString()
        set((state) => ({
          projects: [
            { ...project, id, createdAt: now, updatedAt: now },
            ...state.projects
          ]
        }))
      },

      updateProject: (id: string, updates: Partial<Project>) => {
        const now = new Date().toISOString().split("T")[0]
        set((state) => ({
          projects: state.projects.map((p) =>
            p.id === id ? { ...p, ...updates, updatedAt: now } : p
          )
        }))
      },

      deleteProject: (id: string) => {
        set((state) => ({
          projects: state.projects.filter((p) => p.id !== id)
        }))
      },

      getFilteredProjects: () => {
        const { projects, filterStatus, searchQuery } = get()
        return projects.filter((p) => {
          const matchesStatus = filterStatus === "all" || p.status === filterStatus
          const matchesSearch = searchQuery
            ? p.name.toLowerCase().includes(searchQuery.toLowerCase())
            : true
          return matchesStatus && matchesSearch
        })
      },

      getProjectsByAgent: (agentId: string) => {
        return get().projects.filter((p) => p.agentId === agentId)
      },

      getProjectsByStatus: (status: ProjectStatus) => {
        return get().projects.filter((p) => p.status === status)
      }
    }),
    {
      name: "ceaser-project-store"
    }
  )
)
