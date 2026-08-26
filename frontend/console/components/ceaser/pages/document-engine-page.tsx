"use client"

import { ceaserEngines } from "@/lib/ceaser"
import { GlowCard } from "../glow-card"
import { BarChart3, FileText, Presentation, Sheet } from "lucide-react"

const documentTypes = [
  { kind: "PPTX", label: "PowerPoint", icon: Presentation, flow: "Research -> Content -> Charts -> Images -> Review -> Export" },
  { kind: "DOCX", label: "Word", icon: FileText, flow: "Research -> Writing -> Formatting -> Review -> Export" },
  { kind: "XLSX", label: "Excel", icon: Sheet, flow: "Requirements -> Structure -> Formulas -> Charts -> Export" },
  { kind: "PDF", label: "PDF", icon: FileText, flow: "Source document -> Formatting -> Export" },
]

export function DocumentEnginePage() {
  const engine = ceaserEngines.find((item) => item.id === "document")

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mb-6">
        <p className="text-sm uppercase tracking-wider text-muted-foreground">Execution Engine</p>
        <h1 className="text-3xl font-bold">Document Engine</h1>
        <p className="mt-2 max-w-3xl text-muted-foreground">{engine?.purpose}</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {documentTypes.map((type) => {
          const Icon = type.icon
          return (
            <GlowCard key={type.kind} hover>
              <div className="flex items-start gap-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
                  <Icon className="h-6 w-6 text-primary" />
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wider text-muted-foreground">{type.kind}</p>
                  <h2 className="text-lg font-semibold">{type.label} generation</h2>
                  <p className="mt-2 text-sm text-muted-foreground">{type.flow}</p>
                </div>
              </div>
            </GlowCard>
          )
        })}

        <GlowCard className="lg:col-span-2">
          <div className="mb-4 flex items-center gap-3">
            <BarChart3 className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-semibold">Library Contracts</h2>
          </div>
          <div className="grid gap-3 md:grid-cols-4">
            {["pptxgenjs", "docx", "exceljs", "pdf-lib"].map((library) => (
              <div key={library} className="rounded-lg border border-border bg-secondary/20 p-4">
                <p className="font-medium">{library}</p>
                <p className="mt-1 text-xs text-muted-foreground">Frontend request model ready, backend generation pending.</p>
              </div>
            ))}
          </div>
        </GlowCard>
      </div>
    </div>
  )
}
