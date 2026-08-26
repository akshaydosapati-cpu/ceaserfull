"use client"

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react"
import { authApi, type AuthSession } from "@/lib/api/auth"
import { adminApi } from "@/lib/api/admin"
import { ApiError, clearAuthTokens, getAccessToken, recordStartupMetric } from "@/lib/api/client"
import { CeaserSelect } from "./ceaser-select"
import { CeaserLogo } from "./ceaser-logo"
import { SystemStatusCard } from "./system-status-card"
import { cn } from "@/lib/utils"
import { trackEvent } from "@/lib/analytics"
import { useApp } from "@/lib/app-context"
import { ArrowLeft, ArrowRight, CheckCircle2, Eye, EyeOff, Loader2, Mic, MonitorCog, ShieldCheck, Sparkles, UserRound, Wand2 } from "lucide-react"

const ONBOARDING_KEY = "ceaser_onboarding_complete"
const PROFILE_KEY = "ceaser_user_profile"

type Step = "welcome" | "auth" | "profile" | "permissions" | "hotkey" | "voice" | "ready"
type AuthMode = "login" | "signup"
type AuthStatus = "unknown" | "no_session" | "verifying" | "authenticated" | "unauthenticated" | "temporary_error"

const useCases = ["Student", "Professional", "Founder", "Creator", "Developer"]

export function WelcomeGate({ children }: { children: ReactNode }) {
  const { setCurrentPage } = useApp()
  const [isChecking, setIsChecking] = useState(true)
  const [authStatus, setAuthStatus] = useState<AuthStatus>("unknown")
  const [session, setSession] = useState<AuthSession | null>(null)
  const [onboardingComplete, setOnboardingComplete] = useState(false)
  const [step, setStep] = useState<Step>("welcome")
  const [authMode, setAuthMode] = useState<AuthMode>("login")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [passwordVisible, setPasswordVisible] = useState(false)
  const [name, setName] = useState("")
  const [useCase, setUseCase] = useState("Founder")
  const [studentProfile, setStudentProfile] = useState({
    college: "",
    course: "",
    department: "",
    semester: "",
    graduationYear: "",
  })
  const [authBusy, setAuthBusy] = useState(false)
  const [googleBusy, setGoogleBusy] = useState(false)
  const [hotkeyContinueBusy, setHotkeyContinueBusy] = useState(false)
  const googleBusyRef = useRef(false)
  const [recoveryBusy, setRecoveryBusy] = useState(false)
  const [verificationBusy, setVerificationBusy] = useState(false)
  const [message, setMessage] = useState("")
  const [micStatus, setMicStatus] = useState<"pending" | "ready" | "blocked">("pending")
  const [hotkeyStatus, setHotkeyStatus] = useState<"pending" | "detected">("pending")
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([])
  const [selectedVoice, setSelectedVoice] = useState("")

  useEffect(() => {
    let mounted = true
    const safetyTimer = window.setTimeout(() => {
      if (!mounted) return
      if (getAccessToken()) {
        setAuthStatus("temporary_error")
        setMessage("CEASER is reconnecting. Cached workspace data remains available.")
      } else {
        setAuthStatus("unauthenticated")
        setStep("auth")
      }
      setIsChecking(false)
    }, 30000)
    async function checkSession() {
      try {
        authApi.consumeOAuthRedirect()
      } catch (error) {
        if (mounted) setMessage(error instanceof Error ? cleanAuthMessage(error.message) : "Google sign-in could not continue.")
      }
      const token = getAccessToken()
      if (!token) {
        if (mounted) {
          setAuthStatus("no_session")
          setIsChecking(false)
        }
        return
      }
      setAuthStatus("verifying")
      recordStartupMetric("auth_verify_start")
      try {
        const current = await authApi.getCurrentUser()
        if (!mounted) return
        const storedProfile = readProfile()
        const serverName = sessionDisplayName(current)
        if (serverName) {
          window.localStorage.setItem(PROFILE_KEY, JSON.stringify({ ...storedProfile, name: serverName, email: sessionEmail(current) }))
        } else if (storedProfile?.name?.trim()) {
          const updated = await authApi.updateProfile(storedProfile.name.trim())
          current.display_name = updated.display_name
        }
        setSession(current)
        setEmail(sessionEmail(current))
        const localCompleted = hasCompletedOnboarding(sessionEmail(current))
        let completed = Boolean(current.onboarding_completed)
        if (!completed && localCompleted && storedProfile?.name?.trim()) {
          const restored = await authApi.updateProfile(storedProfile.name.trim(), profilePayload(storedProfile, true))
          completed = Boolean(restored.onboarding_completed)
        }
        if (completed) window.localStorage.setItem(ONBOARDING_KEY, "true")
        setOnboardingComplete(completed)
        setStep(completed ? "ready" : "profile")
        setAuthStatus("authenticated")
        recordStartupMetric("auth_ready")
      } catch (error) {
        if (!mounted) return
        const definitiveAuthFailure = error instanceof ApiError && error.status === 401
        if (definitiveAuthFailure || !getAccessToken()) {
          setSession(null)
          setOnboardingComplete(false)
          setAuthStatus("unauthenticated")
          setStep("auth")
          setMessage("Your session expired. Please sign in again.")
        } else {
          setAuthStatus("temporary_error")
          setMessage("CEASER is reconnecting. Your saved workspace remains available.")
        }
      } finally {
        window.clearTimeout(safetyTimer)
        if (mounted) setIsChecking(false)
      }
    }
    void checkSession()
    return () => {
      mounted = false
      window.clearTimeout(safetyTimer)
    }
  }, [])

  useEffect(() => {
    const onSessionExpired = () => {
      clearAuthTokens()
      setSession(null)
      setOnboardingComplete(false)
      setStep("auth")
      setMessage("Your session expired. Please sign in again.")
    }
    window.addEventListener("ceaser:session-expired", onSessionExpired)
    return () => window.removeEventListener("ceaser:session-expired", onSessionExpired)
  }, [])

  useEffect(() => {
    if (typeof window === "undefined" || !window.speechSynthesis) return
    const load = () => {
      const available = window.speechSynthesis.getVoices()
      setVoices(available)
      setSelectedVoice((current) => current || preferredVoice(available)?.name || "")
    }
    load()
    window.speechSynthesis.onvoiceschanged = load
    return () => {
      window.speechSynthesis.onvoiceschanged = null
    }
  }, [])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.code === "ControlRight") {
        event.preventDefault()
        setHotkeyStatus("detected")
      }
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [])

  const stepIndex = ["welcome", "auth", "profile", "permissions", "hotkey", "voice", "ready"].indexOf(step)
  const isComplete = Boolean(session && onboardingComplete)
  const canOptimisticallyRender = Boolean(
    typeof window !== "undefined"
    && getAccessToken()
    && window.localStorage.getItem(ONBOARDING_KEY) === "true"
    && (isChecking || authStatus === "verifying" || authStatus === "temporary_error"),
  )

  const firstName = useMemo(() => {
    const stored = readProfile()
    return stored?.name || name || sessionEmail(session)?.split("@")[0] || "there"
  }, [name, session])

  if (canOptimisticallyRender) return <>{children}</>

  if (isChecking) {
    return (
      <WelcomeShell>
        <div className="flex min-h-[420px] items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      </WelcomeShell>
    )
  }

  if (isComplete) return <>{children}</>

  async function submitAuth() {
    setMessage("")
    setAuthBusy(true)
    if (authMode === "signup") trackEvent("sign_up_started")
    try {
      const next = authMode === "login" ? await authApi.login(email.trim(), password) : await authApi.signup(email.trim(), password)
      if (authMode === "signup" && !next.access_token) {
        setMessage("Account created. Check your email to verify your account, then sign in.")
        setAuthMode("login")
        return
      }
      setSession(next)
      trackEvent(authMode === "signup" ? "sign_up" : "login")
      const signedInEmail = sessionEmail(next) || email.trim()
      if (authApi.isDesktopLinkRequest() && authApi.completeDesktopLink(next)) {
        setMessage("Account connected. Returning to CEASER Desktop...")
        return
      }
      setEmail(signedInEmail)
      if (authMode === "login") {
        try {
          const admin = await adminApi.me()
          setCurrentPage(admin.is_admin ? "admin" : "chat")
        } catch {
          setCurrentPage("chat")
        }
        const completed = Boolean(next.onboarding_completed)
        setOnboardingComplete(completed)
        setStep(completed ? "ready" : "profile")
        if (!completed) return
        window.localStorage.setItem(ONBOARDING_KEY, "true")
        return
      }
      const completed = hasCompletedOnboarding(signedInEmail)
      if (completed) window.localStorage.setItem(ONBOARDING_KEY, "true")
      setOnboardingComplete(completed)
      setStep(completed ? "ready" : "profile")
    } catch (error) {
      setMessage(error instanceof Error ? cleanAuthMessage(error.message) : "Could not sign in. Check your details and try again.")
    } finally {
      setAuthBusy(false)
    }
  }

  async function requestMicrophone() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      stream.getTracks().forEach((track) => track.stop())
      setMicStatus("ready")
    } catch {
      setMicStatus("blocked")
    }
  }

  async function sendRecoveryEmail() {
    if (!email.trim()) {
      setMessage("Enter your email first, then request a reset link.")
      return
    }
    setRecoveryBusy(true)
    setMessage("")
    try {
      await authApi.recoverPassword(email.trim(), typeof window !== "undefined" ? window.location.origin : undefined)
      setMessage("Password reset email sent if the account exists.")
    } catch (error) {
      setMessage(error instanceof Error ? cleanAuthMessage(error.message) : "Could not send reset email.")
    } finally {
      setRecoveryBusy(false)
    }
  }

  async function resendVerification() {
    if (!email.trim()) {
      setMessage("Enter your email first, then resend verification.")
      return
    }
    setVerificationBusy(true)
    setMessage("")
    try {
      await authApi.resendVerification(email.trim())
      setMessage("Verification email sent if the account exists.")
    } catch (error) {
      setMessage(error instanceof Error ? cleanAuthMessage(error.message) : "Could not resend verification email.")
    } finally {
      setVerificationBusy(false)
    }
  }

  async function handleGoogleSignIn() {
    if (googleBusyRef.current) return
    googleBusyRef.current = true
    setGoogleBusy(true)
    setMessage("")

    try {
      await new Promise<void>((resolve) => window.requestAnimationFrame(() => resolve()))
      await Promise.resolve(authApi.signInWithGoogle())
    } catch (error) {
      googleBusyRef.current = false
      setGoogleBusy(false)
      setMessage(error instanceof Error ? cleanAuthMessage(error.message) : "Google sign-in is not configured.")
    }
  }

  async function saveProfile() {
    const displayName = name.trim() || firstName
    try {
      await authApi.updateProfile(displayName, {
        use_case: useCase,
        onboarding_data: onboardingData(studentProfile, selectedVoice, useCase),
        onboarding_completed: false,
      })
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not save your name.")
      return
    }
    window.localStorage.setItem(PROFILE_KEY, JSON.stringify({
      name: displayName,
      email: sessionEmail(session) || email,
      useCase,
      ...(useCase === "Student" ? { studentProfile: cleanStudentProfile(studentProfile) } : {}),
    }))
    setStep("permissions")
  }

  async function finishOnboarding() {
    const stored = {
      name: name.trim() || firstName,
      email: sessionEmail(session) || email,
      useCase,
      voice: selectedVoice,
      hotkey: "Hold Right Ctrl",
      ...(useCase === "Student" ? { studentProfile: cleanStudentProfile(studentProfile) } : {}),
    }
    try {
      await authApi.updateProfile(stored.name, profilePayload(stored, true))
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not finish your profile setup.")
      return
    }
    window.localStorage.setItem(PROFILE_KEY, JSON.stringify(stored))
    window.localStorage.setItem(ONBOARDING_KEY, "true")
    setStep("ready")
  }

  function openCeaser() {
    window.localStorage.setItem(ONBOARDING_KEY, "true")
    setOnboardingComplete(true)
  }

  return (
    <WelcomeShell>
      <div className="mx-auto flex min-h-[calc(100vh-2rem)] w-full max-w-6xl flex-col justify-center p-4 lg:p-8">
        <div className="mb-6 flex items-center justify-between gap-4">
          <CeaserLogo size="md" iconSrc="/logo.png" />
          <div className="hidden rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs text-muted-foreground md:block">
            Welcome flow {Math.max(stepIndex + 1, 1)} / 7
          </div>
        </div>

        <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
          <section className="rounded-[1.75rem] border border-white/10 bg-[#081120]/84 p-6 shadow-[0_30px_100px_rgba(0,0,0,0.36)] backdrop-blur-xl">
            <Progress current={stepIndex} />
            {step === "welcome" && (
              <StepPanel eyebrow="Welcome" title="Welcome to CEASER" text="Your voice-first personal AI operating system for desktop actions, research, memory, documents, and agent workflows.">
                <div className="grid gap-3 md:grid-cols-3">
                  <MiniFeature icon={Mic} title="Voice First" text="Talk to CEASER from your desktop." />
                  <MiniFeature icon={Wand2} title="AI Workforce" text="Nova, Zeus, Atlas, Friday, Alex, and Bolt." />
                  <MiniFeature icon={MonitorCog} title="Desktop Ready" text="Open apps, search, and act quickly." />
                </div>
                <PrimaryButton onClick={() => setStep("auth")}>Get started</PrimaryButton>
              </StepPanel>
            )}

            {step === "auth" && (
              <StepPanel eyebrow="Account" title={authMode === "login" ? "Sign in to CEASER" : "Create your CEASER account"} text="Use the same account across the web app and desktop companion.">
                <div className="grid gap-3">
                  <input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Email" type="email" className="h-12 rounded-2xl border border-white/10 bg-white/5 px-4 outline-none ring-primary/30 focus:ring-2" />
                  <div className="relative"><input value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Password" type={passwordVisible ? "text" : "password"} className="h-12 w-full rounded-2xl border border-white/10 bg-white/5 px-4 pr-12 outline-none ring-primary/30 focus:ring-2" /><button type="button" onClick={() => setPasswordVisible((visible) => !visible)} aria-label={passwordVisible ? "Hide password" : "Show password"} className="absolute inset-y-0 right-0 px-4 text-muted-foreground hover:text-foreground">{passwordVisible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button></div>
                  {message && <p className="rounded-xl border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-sm text-amber-200">{message}</p>}
                  <PrimaryButton onClick={() => void submitAuth()} disabled={!email || !password || authBusy}>
                    {authBusy ? "Checking..." : authMode === "login" ? "Sign in" : "Create account"}
                  </PrimaryButton>
                  <button
                    type="button"
                    disabled={googleBusy}
                    onClick={() => void handleGoogleSignIn()}
                    aria-busy={googleBusy}
                    className="group inline-flex h-12 items-center justify-center gap-3 rounded-2xl border border-white/14 bg-white/[0.08] px-5 text-sm font-semibold text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.08),0_18px_50px_rgba(0,0,0,0.18)] transition hover:border-white/25 hover:bg-white/[0.12] hover:shadow-[inset_0_1px_0_rgba(255,255,255,0.12),0_22px_70px_rgba(59,130,246,0.16)] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <span className="flex h-7 w-7 items-center justify-center rounded-full bg-white text-[15px] font-black text-[#4285f4] shadow-sm transition group-hover:scale-105">G</span>
                    {googleBusy ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <span>Redirecting...</span>
                      </>
                    ) : (
                      <span>Continue with Google</span>
                    )}
                  </button>
                  <div className="flex items-center justify-between"><BackButton onClick={() => setStep("welcome")} /><button type="button" onClick={() => setAuthMode(authMode === "login" ? "signup" : "login")} className="text-sm text-muted-foreground transition hover:text-primary">{authMode === "login" ? "Need an account? Create one" : "Already have an account? Sign in"}</button></div>
                  <div className="flex flex-wrap justify-center gap-3 text-xs">
                    <button type="button" onClick={() => void sendRecoveryEmail()} disabled={recoveryBusy} className="text-muted-foreground transition hover:text-primary disabled:opacity-50">
                      {recoveryBusy ? "Sending reset..." : "Forgot password?"}
                    </button>
                    <button type="button" onClick={() => void resendVerification()} disabled={verificationBusy} className="text-muted-foreground transition hover:text-primary disabled:opacity-50">
                      {verificationBusy ? "Sending verification..." : "Resend verification"}
                    </button>
                  </div>
                </div>
              </StepPanel>
            )}

            {step === "profile" && (
              <StepPanel eyebrow="Profile" title="Tell CEASER who you are" text="Keep it simple. This helps CEASER personalize the first experience without heavy setup.">
                <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Your name" className="h-12 rounded-2xl border border-white/10 bg-white/5 px-4 outline-none ring-primary/30 focus:ring-2" />
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {useCases.map((item) => (
                    <button key={item} type="button" onClick={() => setUseCase(item)} className={cn("rounded-2xl border px-4 py-3 text-left text-sm transition", useCase === item ? "border-primary bg-primary/10 text-primary" : "border-white/10 bg-white/5 text-muted-foreground hover:text-foreground")}>
                      {item}
                    </button>
                  ))}
                </div>
                {useCase === "Student" && (
                  <div className="grid gap-3 rounded-3xl border border-primary/20 bg-primary/10 p-4 md:grid-cols-2">
                    <StudentInput label="College" value={studentProfile.college} onChange={(value) => setStudentProfile((current) => ({ ...current, college: value }))} />
                    <StudentInput label="Course" value={studentProfile.course} onChange={(value) => setStudentProfile((current) => ({ ...current, course: value }))} />
                    <StudentInput label="Department" value={studentProfile.department} onChange={(value) => setStudentProfile((current) => ({ ...current, department: value }))} />
                    <StudentInput label="Semester" value={studentProfile.semester} onChange={(value) => setStudentProfile((current) => ({ ...current, semester: value }))} />
                    <StudentInput label="Graduation year" value={studentProfile.graduationYear} onChange={(value) => setStudentProfile((current) => ({ ...current, graduationYear: value }))} />
                  </div>
                )}
                <div className="flex items-center gap-3"><BackButton onClick={() => setStep("auth")} /><PrimaryButton onClick={saveProfile}>Continue</PrimaryButton></div>
              </StepPanel>
            )}

            {step === "permissions" && (
              <StepPanel eyebrow="Permissions" title="Enable the basics" text="CEASER needs microphone access for voice. Desktop actions stay under your control.">
                <div className="grid gap-3 md:grid-cols-2">
                  <PermissionCard icon={Mic} title="Microphone" status={micStatus === "ready" ? "Ready" : micStatus === "blocked" ? "Needs browser permission" : "Not checked"} action={requestMicrophone} />
                  <PermissionCard icon={ShieldCheck} title="Desktop control" status="Safe actions only in V1" />
                </div>
                <div className="flex items-center gap-3"><BackButton onClick={() => setStep("profile")} /><PrimaryButton onClick={() => setStep("hotkey")}>Continue</PrimaryButton></div>
              </StepPanel>
            )}

            {step === "hotkey" && (
              <StepPanel eyebrow="Desktop" title="Your CEASER hotkey" text="The global overlay shortcut works when the CEASER desktop companion is running. You can test the key combination here before continuing.">
                <div className="rounded-3xl border border-primary/20 bg-primary/10 p-6 text-center">
                  <p className="text-sm text-muted-foreground">Hotkey</p>
                  <p className="mt-2 text-3xl font-bold tracking-wide text-primary">CTRL + SHIFT + SPACEBAR</p>
                  <p className={cn("mt-3 text-sm", hotkeyStatus === "detected" ? "text-emerald-300" : "text-muted-foreground")}>
                    {hotkeyStatus === "detected" ? "Hotkey detected. Hold it, speak, then release to run the command." : "Click CTRL + SHIFT + SPACEBAR while speaking. Release it when you are done."}
                  </p>
                </div>
                <div className="flex items-center gap-3"><BackButton onClick={() => setStep("permissions")} /><PrimaryButton onClick={async () => { if (hotkeyContinueBusy) return; setHotkeyContinueBusy(true); await new Promise((resolve) => window.setTimeout(resolve, 450)); setStep("voice"); setHotkeyContinueBusy(false) }} disabled={hotkeyContinueBusy}>{hotkeyContinueBusy ? "Continuing..." : "Continue"}</PrimaryButton></div>
              </StepPanel>
            )}

            {step === "voice" && (
              <StepPanel eyebrow="Voice" title="Choose a voice" text="CEASER will use the best available browser/system voice. You can adjust this later.">
                <CeaserSelect
                  value={selectedVoice || "system"}
                  onValueChange={(value) => setSelectedVoice(value === "system" ? "" : value)}
                  options={
                    voices.length
                      ? [{ value: "system", label: "System voice" }, ...voices.map((voice) => ({ value: voice.name, label: voice.name, description: voice.lang }))]
                      : [{ value: "system", label: "System voice" }]
                  }
                  triggerClassName="h-12 rounded-2xl"
                />
                <div className="flex items-center gap-3"><BackButton onClick={() => setStep("hotkey")} /><PrimaryButton onClick={finishOnboarding}>Finish setup</PrimaryButton></div>
              </StepPanel>
            )}

            {step === "ready" && (
              <StepPanel eyebrow="Ready" title={`Welcome, ${firstName}`} text="CEASER web is ready. Start the desktop companion to use the global hotkey and voice overlay, then try one of these commands.">
                <div className="grid gap-2">
                  {["Hey CEASER, open Chrome", "Research AI healthcare startups in India", "Summarize this PDF", "Create a study plan for tomorrow"].map((item) => (
                    <div key={item} className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-muted-foreground">{item}</div>
                  ))}
                </div>
                <div className="flex items-center gap-3"><BackButton onClick={() => setStep("voice")} /><PrimaryButton onClick={openCeaser}>Open CEASER</PrimaryButton></div>
              </StepPanel>
            )}
          </section>

          <aside className="space-y-4">
            <SystemStatusCard />
            <section className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
              <p className="text-xs font-medium uppercase tracking-[0.24em] text-primary">Launch Standard</p>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                No technical errors, no broken claims, and no confusing first step. CEASER should be useful within five minutes.
              </p>
            </section>
          </aside>
        </div>
      </div>
    </WelcomeShell>
  )
}

function WelcomeShell({ children }: { children: ReactNode }) {
  return <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(0,212,255,0.18),transparent_34%),#030712] text-foreground">{children}</div>
}

function StepPanel({ eyebrow, title, text, children }: { eyebrow: string; title: string; text: string; children: ReactNode }) {
  return (
    <div className="space-y-5">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.26em] text-primary">{eyebrow}</p>
        <h1 className="mt-3 text-3xl font-bold md:text-5xl">{title}</h1>
        <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted-foreground md:text-base">{text}</p>
      </div>
      {children}
    </div>
  )
}

function Progress({ current }: { current: number }) {
  return (
    <div className="mb-8 grid grid-cols-7 gap-2">
      {Array.from({ length: 7 }).map((_, index) => (
        <div key={index} className={cn("h-1.5 rounded-full", index <= current ? "bg-primary" : "bg-white/10")} />
      ))}
    </div>
  )
}

function PrimaryButton({ children, onClick, disabled }: { children: ReactNode; onClick: () => void; disabled?: boolean }) {
  return (
    <button type="button" disabled={disabled} onClick={onClick} className="inline-flex h-12 items-center justify-center gap-2 rounded-2xl bg-primary px-5 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50">
      {children}
      <ArrowRight className="h-4 w-4" />
    </button>
  )
}

function BackButton({ onClick }: { onClick: () => void }) {
  return <button type="button" onClick={onClick} className="inline-flex h-12 items-center justify-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-4 text-sm font-medium text-muted-foreground transition hover:bg-white/10 hover:text-foreground"><ArrowLeft className="h-4 w-4" />Previous</button>
}

function MiniFeature({ icon: Icon, title, text }: { icon: typeof Mic; title: string; text: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
      <Icon className="h-5 w-5 text-primary" />
      <p className="mt-3 font-semibold">{title}</p>
      <p className="mt-1 text-sm text-muted-foreground">{text}</p>
    </div>
  )
}

function PermissionCard({ icon: Icon, title, status, action }: { icon: typeof Mic; title: string; status: string; action?: () => void }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
      <div className="flex items-center gap-3">
        <Icon className="h-5 w-5 text-primary" />
        <div className="flex-1">
          <p className="font-semibold">{title}</p>
          <p className="text-sm text-muted-foreground">{status}</p>
        </div>
        {status === "Ready" && <CheckCircle2 className="h-5 w-5 text-emerald-300" />}
      </div>
      {action && (
        <button type="button" onClick={() => void action()} className="mt-4 rounded-xl border border-white/10 px-3 py-2 text-xs font-medium text-muted-foreground transition hover:bg-white/10 hover:text-foreground">
          Check permission
        </button>
      )}
    </div>
  )
}

function StudentInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="space-y-1 text-sm">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-11 w-full rounded-2xl border border-white/10 bg-white/5 px-3 text-sm outline-none ring-primary/30 focus:ring-2"
      />
    </label>
  )
}

function cleanStudentProfile(profile: { college: string; course: string; department: string; semester: string; graduationYear: string }) {
  return {
    college: profile.college.trim(),
    course: profile.course.trim(),
    department: profile.department.trim(),
    semester: profile.semester.trim(),
    graduationYear: profile.graduationYear.trim(),
  }
}

function preferredVoice(voices: SpeechSynthesisVoice[]) {
  const ranked = ["Microsoft Aria", "Microsoft Jenny", "Microsoft Guy"]
  return ranked.map((name) => voices.find((voice) => voice.name.includes(name))).find(Boolean) || voices.find((voice) => voice.lang?.startsWith("en")) || voices[0]
}

function readProfile(): { name?: string } | null {
  if (typeof window === "undefined") return null
  try {
    return JSON.parse(window.localStorage.getItem(PROFILE_KEY) || "null")
  } catch {
    return null
  }
}

function hasCompletedOnboarding(email?: string) {
  if (typeof window === "undefined") return false
  const completed = window.localStorage.getItem(ONBOARDING_KEY) === "true"
  const profile = readProfile() as { email?: string; name?: string } | null
  if (completed && profile?.name) return true
  if (email && profile?.email) return profile.email.toLowerCase() === email.toLowerCase()
  return completed
}

function cleanAuthMessage(value: string) {
  if (/failed to fetch/i.test(value)) return "CEASER backend is not reachable. Start the backend, then try again."
  if (/invalid login credentials|unauthorized|invalid/i.test(value)) {
    return "Email/password sign-in failed. If you created this account with Google, use Continue with Google or select Forgot password to create a password."
  }
  return value || "Could not continue. Please try again."
}

function sessionEmail(session?: AuthSession | null) {
  return session?.email || session?.user?.email || ""
}

function onboardingData(studentProfile: Parameters<typeof cleanStudentProfile>[0], voice: string, useCase: string) {
  return {
    voice,
    hotkey: "Hold Right Ctrl",
    ...(useCase === "Student" ? { student_profile: cleanStudentProfile(studentProfile) } : {}),
  }
}

function profilePayload(profile: any, completed: boolean) {
  return {
    use_case: profile.useCase || null,
    onboarding_data: {
      voice: profile.voice || "",
      hotkey: profile.hotkey || "Hold Right Ctrl",
      ...(profile.studentProfile ? { student_profile: profile.studentProfile } : {}),
    },
    onboarding_completed: completed,
  }
}

function sessionDisplayName(session?: AuthSession | null) {
  return session?.display_name?.trim() || session?.user?.display_name?.trim() || session?.user?.name?.trim() || ""
}

