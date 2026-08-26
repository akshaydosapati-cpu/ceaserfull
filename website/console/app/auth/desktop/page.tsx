"use client"

import { useEffect, useMemo, useState } from "react"
import { MonitorCheck, ShieldCheck } from "lucide-react"
import { desktopApi } from "@/lib/api/desktop"
import { getAccessToken } from "@/lib/api/client"
import { authApi } from "@/lib/api/auth"

function param(name: string) {
  if (typeof window === "undefined") return ""
  return new URLSearchParams(window.location.search).get(name) || ""
}

export default function DesktopAuthPage() {
  const [status, setStatus] = useState<"idle" | "working" | "connected" | "timeout" | "error">("idle")
  const [message, setMessage] = useState("")
  const request = useMemo(() => ({
    state: param("state"),
    code_challenge: param("code_challenge"),
    code_challenge_method: (param("code_challenge_method") || "S256") as "S256",
    redirect_uri: param("redirect_uri") || "ceaser://auth/callback",
    device_id: param("device_id"),
    device_name: param("device_name") || "CEASER Desktop",
    platform: param("platform") || "windows",
    app_version: param("app_version") || "",
  }), [])

  const signedIn = Boolean(getAccessToken())
  const validRequest = Boolean(request.state && request.code_challenge && request.device_id)

  useEffect(() => {
    authApi.rememberDesktopAuthReturn()
  }, [])

  async function approve() {
    if (!validRequest) {
      setStatus("error")
      setMessage("Desktop connection request is missing required security parameters.")
      return
    }
    setStatus("working")
    setMessage("Creating a one-time desktop authorization code...")
    try {
      const response = await desktopApi.authorize(request)
      const params = new URLSearchParams({ code: response.code, state: response.state })
      const callbackUrl = `ceaser://auth/callback?${params.toString()}`
      console.info("[CEASER desktop auth] authorization_code_created", { state: response.state, callback_has_code: true })
      setMessage("Opening CEASER Desktop with a secure one-time code...")
      window.setTimeout(() => {
        setStatus((current) => current === "working" ? "connected" : current)
        setMessage("Desktop connection request sent. If CEASER Desktop is open, you may close this page.")
      }, 1400)
      window.setTimeout(() => {
        setStatus((current) => current === "working" ? "timeout" : current)
        setMessage("CEASER Desktop did not confirm from the browser. Open the desktop app and try Connect again if it did not update.")
      }, 18000)
      window.location.href = callbackUrl
    } catch (error) {
      setStatus("error")
      setMessage(error instanceof Error ? error.message : "Could not authorize CEASER Desktop.")
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#050915] p-6 text-white">
      <section className="w-full max-w-xl rounded-[28px] border border-cyan-400/20 bg-white/[0.04] p-8 shadow-2xl shadow-cyan-950/40">
        <div className="mb-7 flex items-center gap-4">
          <div className="grid h-14 w-14 place-items-center rounded-2xl bg-cyan-400/10 text-cyan-300">
            <MonitorCheck className="h-7 w-7" />
          </div>
          <div>
            <p className="text-sm uppercase tracking-[0.24em] text-cyan-200/70">CEASER Desktop</p>
            <h1 className="text-3xl font-semibold">Connect CEASER Desktop</h1>
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-black/20 p-5">
          <p className="text-sm text-slate-300">Device</p>
          <p className="mt-1 text-lg font-semibold">{request.device_name}</p>
          <p className="mt-1 text-sm text-slate-400">{request.platform || "desktop"} {request.app_version ? `- v${request.app_version}` : ""}</p>
        </div>

        <div className="mt-5 flex gap-3 rounded-2xl border border-emerald-400/20 bg-emerald-400/10 p-4 text-sm text-emerald-100">
          <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0" />
          <p>CEASER will send only a single-use authorization code back to the app. Access and refresh tokens are never placed in the redirect URL.</p>
        </div>

        {!signedIn ? (
          <div className="mt-6 rounded-2xl border border-amber-400/20 bg-amber-400/10 p-4">
            <p className="font-semibold text-amber-100">Sign in required</p>
            <p className="mt-1 text-sm text-amber-100/80">Sign in once. CEASER will return here with the same secure desktop request.</p>
            <a href="/console/?desktop_link=1" className="mt-4 inline-flex rounded-xl bg-white px-4 py-2 text-sm font-semibold text-slate-950">Sign in to continue</a>
          </div>
        ) : (
          <button
            onClick={() => void approve()}
            disabled={status === "working" || status === "connected" || !validRequest}
            className="mt-6 w-full rounded-2xl bg-cyan-300 px-5 py-4 text-sm font-bold text-slate-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {status === "working" ? "Connecting..." : status === "connected" ? "Desktop connection sent" : "Approve and return to desktop"}
          </button>
        )}

        {message && (
          <p className={`mt-4 text-sm ${status === "error" ? "text-red-300" : status === "timeout" ? "text-amber-200" : status === "connected" ? "text-emerald-200" : "text-slate-300"}`}>
            {message}
          </p>
        )}
      </section>
    </main>
  )
}
