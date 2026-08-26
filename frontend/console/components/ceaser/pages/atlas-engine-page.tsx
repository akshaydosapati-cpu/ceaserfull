"use client"

import { ceaserEngines, ceaserIntegrations, getAgent } from "@/lib/ceaser"
import { GlowCard } from "../glow-card"
import { AgentAvatar } from "../agent-avatar"
import { Code2, GitBranch, Rocket, Terminal } from "lucide-react"

export function AtlasEnginePage() {
  const atlas = getAgent("atlas")
  const engine = ceaserEngines.find((item) => item.id === "atlas")
  const integrations = ceaserIntegrations.filter((item) => engine?.integrations?.includes(item.id))

  if (!atlas || !engine) return null

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <p className="text-sm uppercase tracking-wider text-muted-foreground">Execution Engine</p>
          <h1 className="text-3xl font-bold">{engine.name}</h1>
          <p className="mt-2 max-w-3xl text-muted-foreground">{engine.purpose}</p>
        </div>
        <AgentAvatar agent={atlas} size="xl" showStatus showGlow />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <GlowCard>
          <div className="mb-4 flex items-center gap-3">
            <Code2 className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-semibold">Software Creation Workflow</h2>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {engine.workflow.map((step, index) => (
              <div key={step} className="rounded-lg border border-border bg-secondary/20 p-4">
                <p className="text-xs text-muted-foreground">Step {index + 1}</p>
                <p className="mt-1 font-medium">{step}</p>
              </div>
            ))}
          </div>
        </GlowCard>

        <GlowCard>
          <div className="mb-4 flex items-center gap-3">
            <Terminal className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-semibold">Backend Readiness</h2>
          </div>
          <div className="space-y-3">
            {engine.capabilities.map((capability) => (
              <div key={capability} className="flex items-center justify-between rounded-lg bg-secondary/20 px-3 py-2">
                <span className="text-sm">{capability}</span>
                <span className="text-xs text-muted-foreground">API pending</span>
              </div>
            ))}
          </div>
        </GlowCard>

        <GlowCard className="xl:col-span-2">
          <div className="mb-4 flex items-center gap-3">
            <GitBranch className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-semibold">Required Integrations</h2>
          </div>
          <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-5">
            {integrations.map((integration) => (
              <div key={integration.id} className="rounded-lg border border-border bg-background/40 p-4">
                <p className="font-medium">{integration.name}</p>
                <p className="mt-1 text-xs text-muted-foreground">{integration.description}</p>
                <div className="mt-3 flex items-center gap-2 text-xs text-primary">
                  <Rocket className="h-3 w-3" />
                  {integration.status}
                </div>
              </div>
            ))}
          </div>
        </GlowCard>
      </div>
    </div>
  )
}
