"use client"

import { create } from "zustand"
import { persist } from "zustand/middleware"

export type MemoryType = "goal" | "meeting" | "document" | "research" | "conversation" | "project" | "note" | "file"

export interface Memory {
  id: string
  title: string
  description: string
  date: string
  type: MemoryType
  agentId?: string
  content?: string
  tags?: string[]
}

const defaultMemories: Memory[] = [
  {
    id: "1",
    title: "CliniLocker Funding Goal",
    description: "Goal set on May 24, 2026",
    date: "May 24, 2026",
    type: "goal",
    agentId: "zeus",
    tags: ["funding", "startup"]
  },
  {
    id: "2",
    title: "Meeting with Investor",
    description: "Discussed on May 22, 2026",
    date: "May 22, 2026",
    type: "meeting",
    agentId: "zeus",
    tags: ["investor", "funding"]
  },
  {
    id: "3",
    title: "Product Roadmap v2",
    description: "Updated on May 20, 2026",
    date: "May 20, 2026",
    type: "document",
    agentId: "atlas",
    tags: ["roadmap", "product"]
  },
  {
    id: "4",
    title: "Competitor Analysis",
    description: "Researched on May 19, 2026",
    date: "May 19, 2026",
    type: "research",
    agentId: "nova",
    tags: ["competitors", "research"]
  },
  {
    id: "5",
    title: "Marketing Strategy",
    description: "Focus on content + SEO",
    date: "May 18, 2026",
    type: "document",
    agentId: "friday",
    tags: ["marketing", "strategy"]
  },
  {
    id: "6",
    title: "Personal Fitness Plan",
    description: "Weekly workout schedule",
    date: "May 17, 2026",
    type: "goal",
    agentId: "alex",
    tags: ["fitness", "health"]
  }
]

interface MemoryStore {
  memories: Memory[]
  searchQuery: string
  filterType: MemoryType | "all"
  filterAgentId: string | null

  // Actions
  setSearchQuery: (query: string) => void
  setFilterType: (type: MemoryType | "all") => void
  setFilterAgentId: (agentId: string | null) => void
  addMemory: (memory: Omit<Memory, "id">) => void
  updateMemory: (id: string, updates: Partial<Memory>) => void
  deleteMemory: (id: string) => void
  getFilteredMemories: () => Memory[]
  getMemoriesByAgent: (agentId: string) => Memory[]
  getMemoriesByType: (type: MemoryType) => Memory[]
}

export const useMemoryStore = create<MemoryStore>()(
  persist(
    (set, get) => ({
      memories: defaultMemories,
      searchQuery: "",
      filterType: "all",
      filterAgentId: null,

      setSearchQuery: (query: string) => set({ searchQuery: query }),
      setFilterType: (type: MemoryType | "all") => set({ filterType: type }),
      setFilterAgentId: (agentId: string | null) => set({ filterAgentId: agentId }),

      addMemory: (memory: Omit<Memory, "id">) => {
        const id = Date.now().toString()
        set((state) => ({
          memories: [{ ...memory, id }, ...state.memories]
        }))
      },

      updateMemory: (id: string, updates: Partial<Memory>) => {
        set((state) => ({
          memories: state.memories.map((m) =>
            m.id === id ? { ...m, ...updates } : m
          )
        }))
      },

      deleteMemory: (id: string) => {
        set((state) => ({
          memories: state.memories.filter((m) => m.id !== id)
        }))
      },

      getFilteredMemories: () => {
        const { memories, searchQuery, filterType, filterAgentId } = get()
        return memories.filter((m) => {
          const matchesSearch = searchQuery
            ? m.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
              m.description.toLowerCase().includes(searchQuery.toLowerCase())
            : true
          const matchesType = filterType === "all" || m.type === filterType
          const matchesAgent = filterAgentId ? m.agentId === filterAgentId : true
          return matchesSearch && matchesType && matchesAgent
        })
      },

      getMemoriesByAgent: (agentId: string) => {
        return get().memories.filter((m) => m.agentId === agentId)
      },

      getMemoriesByType: (type: MemoryType) => {
        return get().memories.filter((m) => m.type === type)
      }
    }),
    {
      name: "ceaser-memory-store"
    }
  )
)
