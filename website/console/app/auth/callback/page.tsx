"use client"

import { useEffect } from "react"
import { authApi } from "@/lib/api/auth"
import { creditsApi } from "@/lib/api/credits"

export default function AuthCallbackPage() {
  useEffect(() => {
    const finish = async () => {
    const isLocalhost = ["localhost", "127.0.0.1"].includes(window.location.hostname)
    const consoleUrl = (
      isLocalhost
        ? `${window.location.origin}/console`
        : process.env.NEXT_PUBLIC_APP_URL || `${window.location.origin}/console`
    ).replace(/\/$/, "")
    try {
      const session = authApi.consumeOAuthRedirect()
      if (authApi.isDesktopLinkRequest() && authApi.completeDesktopLink(session)) return
      const referral = window.localStorage.getItem("ceaser_referral_code")
      if (referral && session?.access_token) {
        try {
          await creditsApi.applyReferral(referral)
          window.localStorage.removeItem("ceaser_referral_code")
        } catch {
          // Invalid, duplicate, or ineligible referrals must not block sign-in.
        }
      }
      window.location.replace(`${consoleUrl}/`)
    } catch {
      window.location.replace(`${consoleUrl}/?auth_error=oauth_callback`)
    }
    }
    void finish()
  }, [])

  return (
    <main className="flex min-h-screen items-center justify-center bg-background text-foreground">
      <div className="rounded-2xl border border-border/70 bg-card/80 px-6 py-5 text-center shadow-2xl">
        <p className="text-sm font-semibold">Signing you in...</p>
        <p className="mt-1 text-xs text-muted-foreground">Returning to CEASER.</p>
      </div>
    </main>
  )
}
