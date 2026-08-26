"use client"

import { create } from "zustand"
import { persist } from "zustand/middleware"
import { ceaserAgents } from "@/lib/ceaser"

export interface AgentModule {
  id: string
  name: string
  description: string
  enabled: boolean
}

export interface AgentState {
  id: string
  enabled: boolean
  modules: AgentModule[]
  customName?: string
  customDescription?: string
  personality: "Professional" | "Friendly" | "Concise" | "Detailed"
  autonomyLevel: "Ask before acting" | "Act then inform" | "Full autonomy"
}

// Agent-specific module registries
export const agentModuleRegistry: Record<string, Omit<AgentModule, "enabled">[]> =
  Object.fromEntries(
    ceaserAgents.map((agent) => [
      agent.id,
      agent.modules.map((module) => ({
        id: module.id,
        name: module.name,
        description: module.description,
      })),
    ]),
  )

interface AgentStore {
  agents: Record<string, AgentState>
  initializeAgent: (agentId: string) => void
  setAgentEnabled: (agentId: string, enabled: boolean) => void
  toggleAgentEnabled: (agentId: string) => void
  toggleModuleEnabled: (agentId: string, moduleId: string) => void
  updateAgentSettings: (agentId: string, settings: Partial<Pick<AgentState, "customName" | "customDescription" | "personality" | "autonomyLevel">>) => void
  getAgentState: (agentId: string) => AgentState | undefined
  getAgentModules: (agentId: string) => AgentModule[]
  isAgentEnabled: (agentId: string) => boolean
  isModuleEnabled: (agentId: string, moduleId: string) => boolean
}

export const useAgentStore = create<AgentStore>()(
  persist(
    (set, get) => ({
      agents: {},

      initializeAgent: (agentId: string) => {
        const state = get()
        if (state.agents[agentId]) return

        const moduleRegistry = agentModuleRegistry[agentId] || []
        const modules: AgentModule[] = moduleRegistry.map((mod) => ({
          ...mod,
          enabled: true // All modules enabled by default
        }))

        set((state) => ({
          agents: {
            ...state.agents,
            [agentId]: {
              id: agentId,
              enabled: true,
              modules,
              personality: "Professional",
              autonomyLevel: "Ask before acting",
            }
          }
        }))
      },

      setAgentEnabled: (agentId: string, enabled: boolean) => {
        const state = get()
        if (!state.agents[agentId]) {
          state.initializeAgent(agentId)
        }

        set((state) => {
          const agent = state.agents[agentId]
          if (!agent) return state

          return {
            agents: {
              ...state.agents,
              [agentId]: {
                ...agent,
                enabled,
              },
            },
          }
        })
      },

      toggleAgentEnabled: (agentId: string) => {
        set((state) => {
          const agent = state.agents[agentId]
          if (!agent) return state

          return {
            agents: {
              ...state.agents,
              [agentId]: {
                ...agent,
                enabled: !agent.enabled
              }
            }
          }
        })
      },

      toggleModuleEnabled: (agentId: string, moduleId: string) => {
        set((state) => {
          const agent = state.agents[agentId]
          if (!agent) return state

          return {
            agents: {
              ...state.agents,
              [agentId]: {
                ...agent,
                modules: agent.modules.map((mod) =>
                  mod.id === moduleId ? { ...mod, enabled: !mod.enabled } : mod
                )
              }
            }
          }
        })
      },

      updateAgentSettings: (agentId, settings) => {
        set((state) => {
          const agent = state.agents[agentId]
          if (!agent) return state
          return {
            agents: {
              ...state.agents,
              [agentId]: {
                ...agent,
                ...settings,
              },
            },
          }
        })
      },

      getAgentState: (agentId: string) => {
        return get().agents[agentId]
      },

      getAgentModules: (agentId: string) => {
        const agent = get().agents[agentId]
        if (!agent) {
          // Return default modules if agent not initialized
          const registry = agentModuleRegistry[agentId] || []
          return registry.map((mod) => ({ ...mod, enabled: true }))
        }
        return agent.modules
      },

      isAgentEnabled: (agentId: string) => {
        const agent = get().agents[agentId]
        return agent?.enabled ?? true
      },

      isModuleEnabled: (agentId: string, moduleId: string) => {
        const agent = get().agents[agentId]
        if (!agent) return true
        const selectedModule = agent.modules.find((m) => m.id === moduleId)
        return selectedModule?.enabled ?? true
      }
    }),
    {
      name: "ceaser-agent-store"
    }
  )
)
