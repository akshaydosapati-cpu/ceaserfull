"use client"

import { useEffect } from "react"

export default function ReferralPage() {
  useEffect(() => {
    const code = String(new URLSearchParams(window.location.search).get("code") || "").trim().toUpperCase()
    if (/^[A-Z0-9]{4,40}$/.test(code)) window.localStorage.setItem("ceaser_referral_code", code)
    const base = (process.env.NEXT_PUBLIC_APP_URL || `${window.location.origin}/console`).replace(/\/$/, "")
    window.location.replace(`${base}/?referral=1`)
  }, [])
  return <main className="flex min-h-screen items-center justify-center bg-background text-foreground"><p>Preparing your CEASER invitation...</p></main>
}
