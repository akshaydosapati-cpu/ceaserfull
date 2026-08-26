"use client"

import { GlowCard } from "../glow-card"
import { Brain, FileText, FolderKanban, GitBranch, Target, User } from "lucide-react"

const graphNodes = [
  { id: "user", label: "User", icon: User },
  { id: "goals", label: "Goals", icon: Target },
  { id: "projects", label: "Projects", icon: FolderKanban },
  { id: "files", label: "Files", icon: FileText },
  { id: "decisions", label: "Decisions", icon: GitBranch },
  { id: "memories", label: "Memories", icon: Brain },
]

export function MemoryGraphPage() {
  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mb-6">
        <p className="text-sm uppercase tracking-wider text-muted-foreground">Memory Engine</p>
        <h1 className="text-3xl font-bold">Memory Graph</h1>
        <p className="mt-2 max-w-3xl text-muted-foreground">
          Visual shell for the CEASER knowledge graph: users, goals, projects, files, decisions, and memories.
        </p>
      </div>

      <GlowCard>
        <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-6">
          {graphNodes.map((node) => {
            const Icon = node.icon
            return (
              <div key={node.id} className="rounded-lg border border-border bg-secondary/20 p-4 text-center">
                <Icon className="mx-auto mb-3 h-6 w-6 text-primary" />
                <p className="font-medium">{node.label}</p>
                <p className="mt-1 text-xs text-muted-foreground">Graph node</p>
              </div>
            )
          })}
        </div>
      </GlowCard>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <GlowCard>
          <h2 className="mb-3 text-lg font-semibold">Memory Layers</h2>
          {["Short-term memory", "Long-term memory", "Semantic memory", "Knowledge graph"].map((layer) => (
            <div key={layer} className="mb-2 rounded-lg bg-secondary/20 px-3 py-2 text-sm">
              {layer}
            </div>
          ))}
        </GlowCard>

        <GlowCard>
          <h2 className="mb-3 text-lg font-semibold">Backend Contract</h2>
          <p className="text-sm text-muted-foreground">
            This page is ready for the future `/memory/graph` API. It should render graph nodes, edges, memory links,
            semantic relationships, and decision history when the Memory Engine is connected.
          </p>
        </GlowCard>
      </div>
    </div>
  )
}
