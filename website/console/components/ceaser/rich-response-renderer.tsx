"use client"

import { useEffect, useRef, useState } from "react"
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import { AlertTriangle, CheckCircle2, Code2, Download, ExternalLink, FileText, FolderKanban, Loader2, ShieldCheck } from "lucide-react"
import { getAccessToken, getApiBaseUrl } from "@/lib/api/client"
import type { RichResponse } from "@/lib/api/chat"

type Block = RichResponse["blocks"][number]
const palette = ["#4f8cff", "#20c7b7", "#a855f7", "#ff7a1a", "#f2b01e", "#38bdf8"]

export function RichResponseRenderer({ response, onAction }: { response: RichResponse; onAction: (command: string) => void }) {
  return <div className="space-y-4">
    {response.activity?.length ? <Activity events={response.activity} /> : null}
    {response.blocks.map((block, index) => <BlockView key={String(block.block_id ?? index)} block={block} />)}
    {response.sources?.length ? <Sources sources={response.sources} /> : null}
    {response.actions?.length ? <div className="flex flex-wrap gap-2">{response.actions.filter(action => action.enabled !== false).slice(0, 4).map((action, index) => <button key={String(action.action_id ?? index)} onClick={() => onAction(actionCommand(action))} className="inline-flex items-center gap-2 rounded-lg border border-cyan-300/20 bg-cyan-300/[0.07] px-3 py-2 text-sm text-cyan-100 hover:bg-cyan-300/[0.12]">{action.requires_confirmation ? <ShieldCheck className="h-4 w-4" /> : null}{String(action.label ?? "Continue")}</button>)}</div> : null}
  </div>
}

function actionCommand(action: RichResponse["actions"][number]) {
  const argumentsRecord = action.arguments as Record<string, unknown> | undefined
  return String(argumentsRecord?.command ?? action.label ?? "")
}

function blockItems(block: Block): Array<Record<string, unknown>> {
  return Array.isArray(block.items) ? block.items.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object") : []
}

function BlockView({ block }: { block: Block }) {
  const type = String(block.type ?? "text")
  if (type === "text" || type === "markdown") return <div className="whitespace-pre-wrap text-sm leading-7 text-white/82">{String(block.content ?? "")}</div>
  if (type === "code") return <Code block={block} />
  if (type === "table") return <Table block={block} />
  if (type === "chart") return <Chart block={block} />
  if (type === "image" || type === "generated_image") return <ImageBlock block={block} generated={type === "generated_image"} />
  if (type === "image_group") return <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{blockItems(block).slice(0, 6).map((item, index) => <ImageBlock key={index} block={{ ...item, type: "image" }} />)}</div>
  if (type === "file") return <File block={block} />
  if (type === "source_group") return <Sources sources={blockItems(block) as RichResponse["sources"]} />
  if (type === "project") return <Project block={block} />
  if (type === "status") return <div className="flex items-center gap-3 rounded-lg border border-emerald-400/15 bg-emerald-400/[0.05] px-4 py-3 text-sm"><CheckCircle2 className="h-4 w-4 text-emerald-300" />{String(block.content ?? block.title ?? "Completed")}</div>
  if (type === "error") return <div className="flex items-start gap-3 rounded-lg border border-rose-400/20 bg-rose-400/[0.06] p-4"><AlertTriangle className="mt-0.5 h-4 w-4 text-rose-300" /><div><p className="text-sm font-medium">{String(block.title ?? "CEASER could not finish this")}</p><p className="mt-1 text-sm text-white/55">{String(block.content ?? (block.error as Record<string, unknown> | undefined)?.message ?? "Try again safely.")}</p></div></div>
  return block.content ? <p className="text-sm leading-7 text-white/75">{String(block.content)}</p> : null
}

function Code({ block }: { block: Block }) { const content = String(block.content ?? ""); return <section className="overflow-hidden rounded-lg border border-white/10 bg-[#050914]"><header className="flex items-center justify-between border-b border-white/10 px-4 py-2 text-xs text-white/48"><span className="flex items-center gap-2"><Code2 className="h-3.5 w-3.5" />{String(block.filename ?? block.language ?? "Code")}</span><button onClick={() => navigator.clipboard.writeText(content)} className="text-cyan-300">Copy</button></header><pre className="max-h-[30rem] overflow-auto p-4 text-xs leading-6 text-slate-200"><code>{content}</code></pre></section> }
function Table({ block }: { block: Block }) { const columns = Array.isArray(block.columns) ? block.columns.map(String) : []; const rows = Array.isArray(block.rows) ? block.rows : []; return <section className="overflow-hidden rounded-lg border border-white/10 bg-white/[0.025]">{block.title ? <h3 className="border-b border-white/10 px-4 py-3 text-sm font-semibold">{String(block.title)}</h3> : null}<div className="overflow-x-auto"><table className="w-full min-w-[34rem] text-left text-sm"><thead className="bg-white/[0.04] text-white/55"><tr>{columns.map(column => <th key={column} className="px-4 py-3 font-medium">{column}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index} className="border-t border-white/[0.07]">{columns.map((_, cell) => <td key={cell} className="px-4 py-3 text-white/78">{String((row as unknown[])[cell] ?? "")}</td>)}</tr>)}</tbody></table></div></section> }

function Chart({ block }: { block: Block }) {
  const labels = Array.isArray(block.labels) ? block.labels.map(String) : []; const series = Array.isArray(block.series) ? block.series : []
  const data = labels.map((label, index) => ({ name: label, ...Object.fromEntries(series.map((item, i) => [String(item.name ?? `Series ${i + 1}`), Number((item.data as unknown[])?.[index] ?? 0)])) }))
  const axes = <><CartesianGrid stroke="rgba(148,163,184,.12)" vertical={false} /><XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={false} tickLine={false} /><YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={false} tickLine={false} /></>
  return <section className="rounded-lg border border-white/10 bg-white/[0.025] p-4"><h3 className="mb-4 text-sm font-semibold">{String(block.title ?? "CEASER analysis")}</h3><div className="h-64"><ResponsiveContainer width="100%" height="100%">{block.chart_type === "pie" ? <PieChart><Pie data={data} dataKey={String(series[0]?.name ?? "Series 1")} nameKey="name" innerRadius={54} outerRadius={88}>{data.map((_, i) => <Cell key={i} fill={palette[i % palette.length]} />)}</Pie><Tooltip /></PieChart> : block.chart_type === "line" ? <LineChart data={data}>{axes}{series.map((item, i) => <Line key={i} type="monotone" dataKey={String(item.name ?? `Series ${i + 1}`)} stroke={palette[i % palette.length]} strokeWidth={2} dot={false} />)}<Tooltip /></LineChart> : block.chart_type === "area" ? <AreaChart data={data}>{axes}{series.map((item, i) => <Area key={i} type="monotone" dataKey={String(item.name ?? `Series ${i + 1}`)} stroke={palette[i % palette.length]} fill={palette[i % palette.length]} fillOpacity={0.16} />)}<Tooltip /></AreaChart> : <BarChart data={data}>{axes}{series.map((item, i) => <Bar key={i} dataKey={String(item.name ?? `Series ${i + 1}`)} fill={palette[i % palette.length]} radius={[5, 5, 0, 0]} />)}<Tooltip /></BarChart>}</ResponsiveContainer></div></section>
}

function ImageBlock({ block, generated = false }: { block: Block; generated?: boolean }) {
  const [resolvedUrl, setResolvedUrl] = useState<string | null>(null)
  const objectUrlRef = useRef<string | null>(null)

  useEffect(() => {
    const assetId = String(block.asset_id ?? "").trim()
    if (!assetId) {
      setResolvedUrl(null)
      return () => {}
    }
    let cancelled = false
    const controller = new AbortController()
    async function loadPreview() {
      try {
        const token = getAccessToken()
        const response = await fetch(`${getApiBaseUrl()}/files/${assetId}/preview`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          signal: controller.signal,
        })
        if (!response.ok) return
        const blob = await response.blob()
        if (cancelled) return
        if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current)
        objectUrlRef.current = URL.createObjectURL(blob)
        setResolvedUrl(objectUrlRef.current)
      } catch {
        if (!cancelled) setResolvedUrl(null)
      }
    }
    void loadPreview()
    return () => {
      cancelled = true
      controller.abort()
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current)
        objectUrlRef.current = null
      }
    }
  }, [block.asset_id])

  const url = String(block.url ?? block.thumbnail_url ?? resolvedUrl ?? "")
  if (!url) {
    return <figure className="overflow-hidden rounded-lg border border-white/10 bg-white/[0.025] p-4"><div className="flex items-center gap-2 text-sm text-white/55"><Loader2 className="h-4 w-4 animate-spin" /> Preparing generated image...</div></figure>
  }
  return <figure className="overflow-hidden rounded-lg border border-white/10 bg-white/[0.025]"><img src={url} alt={String(block.alt_text ?? block.caption ?? "CEASER visual")} className="max-h-[34rem] w-full object-contain" loading="lazy" /><figcaption className="flex items-center justify-between gap-3 px-4 py-3 text-xs text-white/52"><span>{String(block.caption ?? (generated ? "Generated by CEASER" : block.source_name ?? "Visual source"))}</span>{generated ? <a href={url} download className="flex items-center gap-1.5 text-cyan-300"><Download className="h-3.5 w-3.5" />Download</a> : block.source_url ? <a href={String(block.source_url)} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 text-cyan-300">Source<ExternalLink className="h-3.5 w-3.5" /></a> : null}</figcaption></figure> }
function File({ block }: { block: Block }) { return <article className="flex items-center gap-3 rounded-lg border border-white/10 bg-white/[0.035] p-4"><div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-500/12 text-blue-300"><FileText className="h-5 w-5" /></div><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{String(block.filename ?? block.title ?? "CEASER file")}</p><p className="mt-1 text-xs text-white/45">{String(block.caption ?? "Ready in CEASER Files")}</p></div>{block.url ? <a href={String(block.url)} download className="text-cyan-300"><Download className="h-4 w-4" /></a> : null}</article> }
function Project({ block }: { block: Block }) { const project = (block.project ?? {}) as Record<string, unknown>; return <article className="rounded-lg border border-violet-400/20 bg-violet-500/[0.05] p-4"><p className="flex items-center gap-2 text-xs font-semibold uppercase text-violet-300"><FolderKanban className="h-4 w-4" />Project</p><h3 className="mt-2 text-lg font-semibold">{String(project.name ?? block.title ?? "CEASER project")}</h3><p className="mt-2 text-sm leading-6 text-white/62">{String(project.summary ?? block.content ?? "Project context is ready.")}</p></article> }
function Sources({ sources }: { sources: RichResponse["sources"] }) { return <section><h3 className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-white/45">Sources</h3><div className="grid gap-2 sm:grid-cols-2">{sources.slice(0, 8).map((source, index) => <a key={String(source.source_id ?? index)} href={String(source.url)} target="_blank" rel="noreferrer" className="rounded-lg border border-white/10 bg-white/[0.025] p-3 hover:border-cyan-300/30"><p className="line-clamp-1 text-sm font-medium">{String(source.title ?? source.domain ?? "Source")}</p><p className="mt-1 line-clamp-2 text-xs leading-5 text-white/45">{String(source.snippet ?? source.domain ?? "")}</p></a>)}</div></section> }
function Activity({ events }: { events: RichResponse["activity"] }) { const active = events[events.length - 1]; return <div className="flex items-center gap-3 rounded-lg border border-blue-400/15 bg-blue-400/[0.05] px-4 py-3"><Loader2 className={`h-4 w-4 text-blue-300 ${active?.status === "running" ? "animate-spin" : ""}`} /><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{String(active?.title ?? "CEASER activity")}</p><p className="truncate text-xs text-white/45">{String(active?.detail ?? active?.stage ?? "")}</p></div>{typeof active?.progress === "number" ? <span className="text-xs text-blue-200">{active.progress}%</span> : null}</div> }
