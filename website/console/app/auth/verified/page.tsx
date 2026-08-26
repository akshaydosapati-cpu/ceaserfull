"use client"

import { useEffect, useState } from "react"
import { CircleCheck, ArrowRight } from "lucide-react"
import { authApi } from "@/lib/api/auth"

export default function VerifiedPage() {
  const [returning, setReturning] = useState(false)

  useEffect(() => {
    if (typeof window === "undefined") return
    try {
      const session = authApi.consumeOAuthRedirect()
      if (!session?.access_token) return
      setReturning(true)
      if (authApi.isDesktopLinkRequest() && authApi.completeDesktopLink(session)) return
      window.location.replace(`${window.location.origin}/console/`)
    } catch {
      window.location.replace(`${window.location.origin}/console/?auth_error=oauth_callback`)
    }
  }, [])

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4 text-foreground">
      <div className="w-full max-w-lg rounded-[2rem] border border-border/70 bg-card/90 p-8 text-center shadow-2xl">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-500/15 text-emerald-300">
          <CircleCheck className="h-8 w-8" />
        </div>
        <h1 className="mt-6 text-3xl font-bold">{returning ? "Signing you in" : "You are verified"}</h1>
        <p className="mt-3 text-sm text-muted-foreground">
          {returning
            ? "Your Google account is connected. Returning to CEASER..."
            : "Your email has been verified successfully. Return to CEASER and sign in to continue."}
        </p>
        {!returning && <div className="mt-8 flex justify-center">
          <button
            type="button"
            onClick={() => {
              const origin = window.location.origin
              window.location.assign(`${origin}/console/`)
            }}
            className="inline-flex items-center gap-2 rounded-2xl bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90"
          >
            Go back and sign in
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>}
      </div>
    </main>
  )
}
