"use client"

import { useEffect, useMemo, useState } from "react"
import { Download, Eye, FilePlus2, Search, Trash2, Upload } from "lucide-react"
import { adminApi, type InternshipInput, type InternshipRecord } from "@/lib/api/admin"

const emptyForm: InternshipInput = { intern_name: "", role: "", start_date: "", end_date: "", issue_date: "", certificate_id: "" }

export function InternshipsAdmin() {
  const [records, setRecords] = useState<InternshipRecord[]>([])
  const [form, setForm] = useState(emptyForm)
  const [query, setQuery] = useState("")
  const [status, setStatus] = useState("")
  const [selected, setSelected] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState("")
  const active = useMemo(() => records.find((item) => item.id === selected) || records[0] || null, [records, selected])

  async function load() {
    try { setRecords(await adminApi.internships(query, status)) } catch (error) { setMessage(error instanceof Error ? error.message : "Internship records could not be loaded.") }
  }
  useEffect(() => { void load() }, [status])

  async function create() {
    setBusy(true); setMessage("")
    try { const created = await adminApi.createInternship({ ...form, certificate_id: form.certificate_id || undefined }); setRecords((items) => [created, ...items]); setSelected(created.id); setForm(emptyForm); setMessage("Internship record created as draft.") }
    catch (error) { setMessage(error instanceof Error ? error.message : "Record could not be created.") }
    finally { setBusy(false) }
  }

  async function upload(documentType: string, file?: File) {
    if (!active || !file) return
    setBusy(true); setMessage("")
    try { await adminApi.uploadInternshipDocument(active.id, documentType, file); await load(); setMessage("PDF uploaded successfully.") }
    catch (error) { setMessage(error instanceof Error ? error.message : "Upload failed. Please try again.") }
    finally { setBusy(false) }
  }

  async function action(kind: "publish" | "revoke" | "restore") {
    if (!active) return
    setBusy(true)
    try { const handler = kind === "publish" ? adminApi.publishInternship : kind === "revoke" ? adminApi.revokeInternship : adminApi.restoreInternship; const updated = await handler(active.id); setRecords((items) => items.map((item) => item.id === updated.id ? updated : item)); setMessage(`Record ${kind === "publish" ? "published" : kind === "revoke" ? "revoked" : "restored"}.`) }
    catch (error) { setMessage(error instanceof Error ? error.message : "Action failed.") }
    finally { setBusy(false) }
  }

  async function openDocument(documentId: string, filename: string, download: boolean) {
    if (!active) return
    try { const blob = await adminApi.internshipDocument(active.id, documentId, download); const url = URL.createObjectURL(blob); if (download) { const anchor = document.createElement("a"); anchor.href = url; anchor.download = filename; anchor.click() } else window.open(url, "_blank", "noopener,noreferrer"); window.setTimeout(() => URL.revokeObjectURL(url), 60_000) }
    catch (error) { setMessage(error instanceof Error ? error.message : "Document could not be opened.") }
  }

  return <div className="grid gap-5 xl:grid-cols-[minmax(320px,0.8fr)_minmax(420px,1.2fr)]">
    <section className="rounded-lg border border-white/10 bg-white/[0.04] p-5">
      <div className="mb-4 flex items-center gap-2"><FilePlus2 className="h-5 w-5 text-primary"/><h2 className="text-lg font-semibold">Create Internship Record</h2></div>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Intern name" value={form.intern_name} onChange={(value) => setForm({ ...form, intern_name: value })}/>
        <Field label="Role" value={form.role} onChange={(value) => setForm({ ...form, role: value })}/>
        <Field type="date" label="Start date" value={form.start_date} onChange={(value) => setForm({ ...form, start_date: value })}/>
        <Field type="date" label="End date" value={form.end_date} onChange={(value) => setForm({ ...form, end_date: value })}/>
        <Field type="date" label="Issue date" value={form.issue_date} onChange={(value) => setForm({ ...form, issue_date: value })}/>
        <Field label="Certificate ID (optional)" value={form.certificate_id || ""} onChange={(value) => setForm({ ...form, certificate_id: value.toUpperCase() })}/>
      </div>
      <button disabled={busy || !form.intern_name || !form.role || !form.start_date || !form.end_date || !form.issue_date} onClick={() => void create()} className="mt-4 h-10 w-full rounded-md bg-primary px-4 text-sm font-semibold text-primary-foreground disabled:opacity-45">Create draft</button>
      {message && <p className="mt-3 text-sm text-muted-foreground">{message}</p>}
    </section>

    <section className="min-w-0 rounded-lg border border-white/10 bg-white/[0.04] p-5">
      <div className="mb-4 flex flex-wrap gap-2">
        <label className="flex h-10 min-w-[220px] flex-1 items-center gap-2 rounded-md border border-white/10 px-3"><Search className="h-4 w-4 text-muted-foreground"/><input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void load() }} placeholder="Search name, ID, or role" className="min-w-0 flex-1 bg-transparent text-sm outline-none"/></label>
        <select value={status} onChange={(event) => setStatus(event.target.value)} className="h-10 rounded-md border border-white/10 bg-background px-3 text-sm"><option value="">All statuses</option><option value="draft">Draft</option><option value="published">Published</option><option value="revoked">Revoked</option></select>
        <button onClick={() => void load()} className="h-10 rounded-md border border-white/10 px-4 text-sm">Search</button>
      </div>
      {!records.length ? <p className="rounded-md border border-dashed border-white/10 p-5 text-sm text-muted-foreground">No internship records yet.</p> : <div className="grid gap-4 lg:grid-cols-[220px_1fr]">
        <div className="max-h-[520px] space-y-2 overflow-y-auto">{records.map((item) => <button key={item.id} onClick={() => setSelected(item.id)} className={`w-full rounded-md border p-3 text-left ${active?.id === item.id ? "border-primary/60 bg-primary/10" : "border-white/10 bg-black/10"}`}><span className="block truncate text-sm font-semibold">{item.intern_name}</span><span className="mt-1 block text-[11px] text-muted-foreground">{item.certificate_id}</span><span className="mt-2 inline-block rounded-sm border border-white/10 px-1.5 py-0.5 text-[10px] uppercase">{item.status}</span></button>)}</div>
        {active && <div className="min-w-0"><div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-lg font-semibold">{active.intern_name}</h3><p className="text-sm text-muted-foreground">{active.role} · {active.certificate_id}</p></div><div className="flex gap-2">{active.status === "draft" && <button disabled={busy} onClick={() => void action("publish")} className="rounded-md bg-emerald-500/15 px-3 py-2 text-xs text-emerald-200">Publish</button>}{active.status === "published" && <button disabled={busy} onClick={() => void action("revoke")} className="rounded-md bg-rose-500/15 px-3 py-2 text-xs text-rose-200">Revoke</button>}{active.status === "revoked" && <button disabled={busy} onClick={() => void action("restore")} className="rounded-md bg-emerald-500/15 px-3 py-2 text-xs text-emerald-200">Restore</button>}</div></div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2"><UploadBox label="Offer letter" onFile={(file) => void upload("offer_letter", file)}/><UploadBox label="Internship certificate" onFile={(file) => void upload("internship_certificate", file)}/></div>
          <div className="mt-4 space-y-2">{active.documents.length ? active.documents.map((doc) => <div key={doc.id} className="flex items-center gap-3 rounded-md border border-white/10 p-3"><div className="min-w-0 flex-1"><p className="truncate text-sm">{doc.original_filename}</p><p className="text-[11px] text-muted-foreground">{doc.document_type.replaceAll("_", " ")} · v{doc.version} · {doc.status}</p></div>{doc.status !== "deleted" && <><IconButton label="Preview" onClick={() => void openDocument(doc.id, doc.original_filename, false)} icon={Eye}/><IconButton label="Download" onClick={() => void openDocument(doc.id, doc.original_filename, true)} icon={Download}/><IconButton label="Delete" onClick={async () => { await adminApi.deleteInternshipDocument(active.id, doc.id); await load() }} icon={Trash2}/></>}</div>) : <p className="rounded-md border border-dashed border-white/10 p-4 text-sm text-muted-foreground">No documents uploaded.</p>}</div>
        </div>}
      </div>}
    </section>
  </div>
}

function Field({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (value: string) => void; type?: string }) { return <label className="text-xs text-muted-foreground">{label}<input type={type} value={value} onChange={(event) => onChange(event.target.value)} className="mt-1.5 h-10 w-full rounded-md border border-white/10 bg-black/15 px-3 text-sm text-foreground outline-none focus:border-primary/60"/></label> }
function UploadBox({ label, onFile }: { label: string; onFile: (file?: File) => void }) { return <label className="flex min-h-24 cursor-pointer flex-col items-center justify-center rounded-md border border-dashed border-primary/35 bg-primary/5 p-3 text-center text-xs"><Upload className="mb-2 h-5 w-5 text-primary"/><span>{label}</span><span className="mt-1 text-[10px] text-muted-foreground">PDF, maximum 12 MB</span><input type="file" accept="application/pdf,.pdf" className="sr-only" onChange={(event) => onFile(event.target.files?.[0])}/></label> }
function IconButton({ label, onClick, icon: Icon }: { label: string; onClick: () => void; icon: typeof Eye }) { return <button title={label} aria-label={label} onClick={onClick} className="grid h-8 w-8 shrink-0 place-items-center rounded-md border border-white/10 hover:bg-white/10"><Icon className="h-3.5 w-3.5"/></button> }
