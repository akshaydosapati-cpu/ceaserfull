"use client"

import { useEffect, useState } from "react"
import { user } from "@/lib/data"
import { GlowCard } from "../glow-card"
import { CeaserLogo } from "../ceaser-logo"
import { CeaserSelect } from "../ceaser-select"
import { SystemStatusCard } from "../system-status-card"
import { authApi } from "@/lib/api/auth"
import { getAccessToken } from "@/lib/api/client"
import { commercialApi, type CommercialOverview, type CommercialPlan } from "@/lib/api/commercial"
import { filesApi, type FileRecord } from "@/lib/api/files"
import { voiceApi, type VoiceSettingsRecord } from "@/lib/api/voice"
import { cn } from "@/lib/utils"
import { 
  User, 
  Mic, 
  Puzzle, 
  Shield, 
  Sliders,
  Info,
  Bell,
  Key,
  Smartphone,
  Activity,
  Unplug,
  CreditCard,
  GraduationCap,
  RefreshCw,
  Upload
} from "lucide-react"

const settingsSections = [
  { 
    id: "status", 
    label: "System Status", 
    icon: Activity,
    description: "Readiness & setup"
  },
  { 
    id: "profile", 
    label: "Profile", 
    icon: User,
    description: "Manage your profile"
  },
  { 
    id: "voice", 
    label: "Voice", 
    icon: Mic,
    description: "Voice & speech settings"
  },
  { 
    id: "integrations", 
    label: "Integrations", 
    icon: Puzzle,
    description: "Connected apps & services"
  },
  {
    id: "billing",
    label: "Billing & Student Access",
    icon: CreditCard,
    description: "Plans, usage, verification"
  },
  { 
    id: "security", 
    label: "Security", 
    icon: Shield,
    description: "2FA, data settings"
  },
  { 
    id: "preferences", 
    label: "Preferences", 
    icon: Sliders,
    description: "App preferences & defaults"
  },
  { 
    id: "about", 
    label: "About Ceaser", 
    icon: Info,
    description: "Version 1.0.0"
  }
]

const connectableIntegrations = [
  { name: "Google Calendar", live: true },
  { name: "Gmail", live: true },
  { name: "Google Drive", live: true },
  { name: "Google Tasks", live: true },
  { name: "Google Classroom", live: true },
  { name: "Notion", live: false },
]
const PROFILE_KEY = "ceaser_user_profile"
const PREFERENCES_KEY = "ceaser_preferences"
const roleOptions = [
  { value: "Student", label: "Student", description: "Study plans, notes, exam prep" },
  { value: "Founder", label: "Founder", description: "Startups, strategy, fundraising" },
  { value: "Professional", label: "Professional", description: "Workflows, meetings, productivity" },
  { value: "Creator", label: "Creator", description: "Content, campaigns, publishing" },
  { value: "Developer", label: "Developer", description: "Technical planning and documentation" },
  { value: "Personal", label: "Personal", description: "Personal memory and daily assistance" },
]

export function SettingsPage() {
  const [activeSection, setActiveSection] = useState("status")
  const [profile, setProfile] = useState<{ name?: string; email?: string; useCase?: string } | null>(null)
  const [profileDraft, setProfileDraft] = useState({ name: user.name, email: "", useCase: user.role })
  const [newPassword, setNewPassword] = useState("")
  const [securityMessage, setSecurityMessage] = useState("")
  const [securityBusy, setSecurityBusy] = useState<string | null>(null)
  const [mfaEnrollment, setMfaEnrollment] = useState<Record<string, unknown> | null>(null)
  const [mfaCode, setMfaCode] = useState("")
  const [voiceSettings, setVoiceSettings] = useState<VoiceSettingsRecord | null>(null)
  const [voiceBusy, setVoiceBusy] = useState(false)
  const [voiceMessage, setVoiceMessage] = useState("")
  const [browserVoices, setBrowserVoices] = useState<SpeechSynthesisVoice[]>([])
  const [sessionActive, setSessionActive] = useState(false)
  const [preferences, setPreferences] = useState({ notifications: true })
  const [commercialOverview, setCommercialOverview] = useState<CommercialOverview | null>(null)
  const [commercialPlans, setCommercialPlans] = useState<CommercialPlan[]>([])
  const [commercialBusy, setCommercialBusy] = useState<string | null>(null)
  const [commercialMessage, setCommercialMessage] = useState("")
  const [studentEmail, setStudentEmail] = useState("")
  const [studentOtp, setStudentOtp] = useState("")
  const [studentDocumentFile, setStudentDocumentFile] = useState<File | null>(null)
  const [uploadedStudentDocument, setUploadedStudentDocument] = useState<FileRecord | null>(null)
  const [pendingVerificationId, setPendingVerificationId] = useState("")

  useEffect(() => {
    try {
      const savedProfile = JSON.parse(window.localStorage.getItem(PROFILE_KEY) || "null")
      setProfile(savedProfile)
      setProfileDraft({
        name: savedProfile?.name || user.name,
        email: savedProfile?.email || "",
        useCase: savedProfile?.useCase || user.role,
      })
      setSessionActive(Boolean(getAccessToken()))
      setPreferences({ notifications: true, ...JSON.parse(window.localStorage.getItem(PREFERENCES_KEY) || "{}") })
    } catch {
      setProfile(null)
      setSessionActive(false)
    }
  }, [])

  useEffect(() => {
    let mounted = true
    const loadSettings = async () => {
      try {
        const settings = await voiceApi.getSettings()
        if (mounted) setVoiceSettings(settings)
      } catch {
        if (mounted) setVoiceMessage("Voice settings need an active session.")
      }
    }
    void loadSettings()
    return () => {
      mounted = false
    }
  }, [])

  useEffect(() => {
    void loadCommercialData()
  }, [])

  useEffect(() => {
    if (typeof window === "undefined" || !window.speechSynthesis) return
    const loadVoices = () => setBrowserVoices(window.speechSynthesis.getVoices())
    loadVoices()
    window.speechSynthesis.onvoiceschanged = loadVoices
    return () => {
      window.speechSynthesis.onvoiceschanged = null
    }
  }, [])

  const displayName = profile?.name || user.name
  const displayEmail = profile?.email || "Signed in account"
  const displayRole = profile?.useCase || user.role

  function savePreferences(patch: Partial<typeof preferences>) {
    setPreferences((current) => {
      const next = { ...current, ...patch }
      window.localStorage.setItem(PREFERENCES_KEY, JSON.stringify(next))
      return next
    })
  }

  function saveProfile() {
    const next = {
      name: profileDraft.name.trim() || user.name,
      email: profileDraft.email.trim(),
      useCase: profileDraft.useCase,
    }
    window.localStorage.setItem(PROFILE_KEY, JSON.stringify(next))
    setProfile(next)
  }

  async function loadCommercialData() {
    setCommercialBusy("load")
    setCommercialMessage("")
    try {
      const [overview, plans] = await Promise.all([commercialApi.overview(), commercialApi.plans()])
      setCommercialOverview(overview)
      setCommercialPlans(plans)
      setPendingVerificationId(overview.student_verification?.id || "")
      setStudentEmail(overview.student_verification?.institutional_email || "")
    } catch (error) {
      setCommercialMessage(error instanceof Error ? error.message : "Could not load billing and student access.")
    } finally {
      setCommercialBusy(null)
    }
  }

  async function startStudentVerification() {
    if (!studentEmail.trim()) {
      setCommercialMessage("Enter your institutional email first.")
      return
    }
    setCommercialBusy("student-email")
    setCommercialMessage("")
    try {
      const result = await commercialApi.startStudentEmail(studentEmail.trim())
      setPendingVerificationId(result.verification_id || "")
      setCommercialMessage(result.message)
      await loadCommercialData()
    } catch (error) {
      setCommercialMessage(error instanceof Error ? error.message : "Could not start student verification.")
    } finally {
      setCommercialBusy(null)
    }
  }

  async function confirmStudentVerification() {
    if (!pendingVerificationId || !studentOtp.trim()) {
      setCommercialMessage("Enter the verification id/code first.")
      return
    }
    setCommercialBusy("student-confirm")
    setCommercialMessage("")
    try {
      await commercialApi.confirmStudentEmail(pendingVerificationId, studentOtp.trim())
      setStudentOtp("")
      setCommercialMessage("Student email verified.")
      await loadCommercialData()
    } catch (error) {
      setCommercialMessage(error instanceof Error ? error.message : "Could not confirm the code.")
    } finally {
      setCommercialBusy(null)
    }
  }

  async function submitStudentDocument() {
    if (!studentDocumentFile && !uploadedStudentDocument) {
      setCommercialMessage("Choose your student ID document first.")
      return
    }
    setCommercialBusy("student-document")
    setCommercialMessage("")
    try {
      const uploaded = uploadedStudentDocument ?? await filesApi.upload(studentDocumentFile as File)
      setUploadedStudentDocument(uploaded)
      await commercialApi.submitStudentDocument(uploaded.id)
      setStudentDocumentFile(null)
      setCommercialMessage("Student document submitted for manual review.")
      await loadCommercialData()
    } catch (error) {
      setCommercialMessage(error instanceof Error ? error.message : "Could not submit student document.")
    } finally {
      setCommercialBusy(null)
    }
  }

  async function runTestUpgrade(planCode: string, interval: "monthly" | "annual") {
    setCommercialBusy(`${planCode}-${interval}`)
    setCommercialMessage("")
    try {
      const result = await commercialApi.testCheckout(planCode, interval)
      setCommercialMessage(result.message)
      await loadCommercialData()
    } catch (error) {
      setCommercialMessage(error instanceof Error ? error.message : "Could not activate the test plan.")
    } finally {
      setCommercialBusy(null)
    }
  }

  async function updatePassword() {
    if (newPassword.length < 6) {
      setSecurityMessage("Use at least 6 characters for the new password.")
      return
    }
    setSecurityBusy("password")
    setSecurityMessage("")
    try {
      await authApi.updatePassword(newPassword)
      setNewPassword("")
      setSecurityMessage("Password updated.")
    } catch (error) {
      setSecurityMessage(error instanceof Error ? error.message : "Could not update password.")
    } finally {
      setSecurityBusy(null)
    }
  }

  async function startMfaEnrollment() {
    setSecurityBusy("mfa")
    setSecurityMessage("")
    try {
      const result = await authApi.enrollMfa()
      setMfaEnrollment(result)
      setSecurityMessage("Scan the authenticator QR code, then enter the 6-digit code.")
    } catch (error) {
      setSecurityMessage(error instanceof Error ? error.message : "Could not start two-factor setup.")
    } finally {
      setSecurityBusy(null)
    }
  }

  async function verifyMfaEnrollment() {
    const factorId = String(mfaEnrollment?.id || "")
    if (!factorId || !mfaCode.trim()) {
      setSecurityMessage("Start setup and enter the authenticator code first.")
      return
    }
    setSecurityBusy("mfa-verify")
    setSecurityMessage("")
    try {
      const challenge = await authApi.challengeMfa(factorId)
      const challengeId = String(challenge.id || challenge.challenge_id || "")
      await authApi.verifyMfa(factorId, challengeId, mfaCode.trim())
      setSecurityMessage("Two-factor authentication enabled.")
      setMfaEnrollment(null)
      setMfaCode("")
    } catch (error) {
      setSecurityMessage(error instanceof Error ? error.message : "Could not verify two-factor code.")
    } finally {
      setSecurityBusy(null)
    }
  }

  async function saveVoiceSettings(patch: Partial<VoiceSettingsRecord>) {
    const next = { ...(voiceSettings ?? defaultVoiceSettings()), ...patch }
    setVoiceSettings(next)
    setVoiceBusy(true)
    setVoiceMessage("")
    try {
      const updated = await voiceApi.updateSettings(patch)
      setVoiceSettings(updated)
      setVoiceMessage("Voice settings saved.")
    } catch (error) {
      setVoiceMessage(error instanceof Error ? error.message : "Could not save voice settings.")
    } finally {
      setVoiceBusy(false)
    }
  }

  function testVoice() {
    if (typeof window === "undefined" || !window.speechSynthesis) {
      setVoiceMessage("Browser speech is unavailable on this device.")
      return
    }

    const settings = voiceSettings ?? defaultVoiceSettings()
    const utterance = new SpeechSynthesisUtterance("CEASER voice is ready. Speed and volume are using your saved settings.")
    const selectedVoice = browserVoices.find((voice) => voice.name === settings.preferred_voice)

    utterance.rate = settings.speech_speed ?? 1
    utterance.volume = settings.speech_volume ?? 1
    utterance.lang = settings.language ?? "en"
    if (selectedVoice) utterance.voice = selectedVoice

    window.speechSynthesis.cancel()
    window.speechSynthesis.speak(utterance)
    setVoiceMessage("Playing a test voice with the selected speed and volume.")
  }

  return (
    <div className="flex h-full">
      {/* Settings Navigation */}
      <div className="w-64 border-r border-border bg-card/30 p-4">
        <h1 className="mb-6 px-2 text-xl font-bold">Settings</h1>
        <nav className="space-y-1">
          {settingsSections.map((section) => {
            const Icon = section.icon
            return (
              <button
                key={section.id}
                onClick={() => setActiveSection(section.id)}
                className={cn(
                  "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors",
                  activeSection === section.id
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                )}
              >
                <Icon className="h-5 w-5" />
                <div className="flex-1">
                  <p className="text-sm font-medium">{section.label}</p>
                  <p className="text-xs text-muted-foreground">{section.description}</p>
                </div>
              </button>
            )
          })}
        </nav>
      </div>

      {/* Settings Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {activeSection === "status" && (
          <div className="max-w-3xl space-y-6">
            <h2 className="text-2xl font-bold">System Status</h2>
            <p className="text-muted-foreground">Clean launch readiness without technical noise.</p>
            <SystemStatusCard />
          </div>
        )}

        {activeSection === "profile" && (
          <div className="max-w-2xl space-y-6">
            <h2 className="text-2xl font-bold">Profile</h2>
            
            <GlowCard>
              <div className="flex items-center gap-4">
                <div className="flex h-20 w-20 items-center justify-center rounded-full bg-gradient-to-br from-primary/30 to-primary/10 text-2xl font-bold text-primary">
                  {displayName.charAt(0)}
                </div>
                <div className="flex-1">
                  <h3 className="text-lg font-semibold">{displayName}</h3>
                  <p className="text-muted-foreground">{displayRole}</p>
                </div>
              </div>
            </GlowCard>

            <div className="space-y-4">
              <div>
                <label className="mb-2 block text-sm font-medium">Full Name</label>
                <input
                  type="text"
                  value={profileDraft.name}
                  onChange={(event) => setProfileDraft((current) => ({ ...current, name: event.target.value }))}
                  className="w-full rounded-lg border border-border bg-background px-4 py-2 outline-none focus:border-primary"
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium">Email</label>
                <input
                  type="email"
                  value={profileDraft.email}
                  onChange={(event) => setProfileDraft((current) => ({ ...current, email: event.target.value }))}
                  placeholder={displayEmail}
                  className="w-full rounded-lg border border-border bg-background px-4 py-2 outline-none focus:border-primary"
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium">Role</label>
                <CeaserSelect
                  value={profileDraft.useCase}
                  onValueChange={(value) => setProfileDraft((current) => ({ ...current, useCase: value }))}
                  options={roleOptions}
                />
              </div>
            </div>

            <button onClick={saveProfile} className="rounded-xl bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90">
              Save Profile
            </button>
          </div>
        )}

        {activeSection === "voice" && (
          <div className="max-w-2xl space-y-6">
            <h2 className="text-2xl font-bold">Voice Settings</h2>
            {voiceMessage && <p className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-muted-foreground">{voiceMessage}</p>}
            
            <GlowCard>
              <h3 className="mb-4 font-semibold">Voice Assistant</h3>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Enable Voice Input</p>
                    <p className="text-sm text-muted-foreground">Allow voice commands</p>
                  </div>
                  <SettingSwitch checked={voiceSettings?.voice_enabled ?? true} disabled={voiceBusy} onChange={(checked) => void saveVoiceSettings({ voice_enabled: checked })} />
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Voice Feedback</p>
                    <p className="text-sm text-muted-foreground">Ceaser speaks responses</p>
                  </div>
                  <SettingSwitch checked={voiceSettings?.auto_speak_responses ?? true} disabled={voiceBusy} onChange={(checked) => void saveVoiceSettings({ auto_speak_responses: checked })} />
                </div>
              </div>
            </GlowCard>

            <GlowCard>
              <h3 className="mb-4 font-semibold">Voice Selection</h3>
              <div className="grid gap-4">
                <div>
                  <label className="mb-2 block text-sm font-medium">Preferred Browser Voice</label>
                  <CeaserSelect
                    value={voiceSettings?.preferred_voice || "system"}
                    onValueChange={(value) => void saveVoiceSettings({ preferred_voice: value === "system" ? null : value })}
                    options={[
                      { value: "system", label: "Best available voice" },
                      ...browserVoices.map((voice) => ({ value: voice.name, label: voice.name, description: voice.lang })),
                    ]}
                  />
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <RangeSetting label="Speaking speed" value={voiceSettings?.speech_speed ?? 1} min={0.5} max={2} step={0.1} onChange={(value) => void saveVoiceSettings({ speech_speed: value })} />
                  <RangeSetting label="Volume" value={voiceSettings?.speech_volume ?? 1} min={0} max={1} step={0.05} onChange={(value) => void saveVoiceSettings({ speech_volume: value })} />
                </div>
                <button onClick={testVoice} className="w-fit rounded-xl border border-primary/40 bg-primary/10 px-4 py-2 text-sm font-semibold text-primary transition hover:bg-primary/15">
                  Play Voice Sample
                </button>
                <div>
                  <label className="mb-2 block text-sm font-medium">Language</label>
                  <CeaserSelect
                    value={voiceSettings?.language ?? "en"}
                    onValueChange={(value) => void saveVoiceSettings({ language: value })}
                    options={[
                      { value: "en", label: "English" },
                      { value: "en-IN", label: "English (India)" },
                      { value: "en-US", label: "English (US)" },
                      { value: "hi-IN", label: "Hindi" },
                      { value: "te-IN", label: "Telugu" },
                    ]}
                  />
                </div>
              </div>
            </GlowCard>
          </div>
        )}

        {activeSection === "integrations" && (
          <div className="max-w-2xl space-y-6">
            <h2 className="text-2xl font-bold">Integrations</h2>
            <p className="text-muted-foreground">Connect your favorite apps and services from the Integrations page. Nothing is shown as connected until OAuth is complete.</p>
            
            <div className="space-y-3">
              {connectableIntegrations.map((integration) => (
                <GlowCard key={integration.name}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-secondary">
                        <Unplug className="h-5 w-5 text-muted-foreground" />
                      </div>
                      <span className="font-medium">{integration.name}</span>
                    </div>
                    <span className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-muted-foreground">
                      {integration.live ? "Not connected" : "Future update"}
                    </span>
                  </div>
                </GlowCard>
              ))}
            </div>
          </div>
        )}

        {activeSection === "billing" && (
          <div className="max-w-5xl space-y-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h2 className="text-2xl font-bold">Billing & Student Access</h2>
                <p className="text-muted-foreground">Manage plans, student verification, and usage limits.</p>
              </div>
              <button
                onClick={() => void loadCommercialData()}
                disabled={commercialBusy === "load"}
                className="inline-flex items-center gap-2 rounded-xl border border-border px-4 py-2 text-sm font-semibold transition hover:bg-secondary disabled:opacity-50"
              >
                <RefreshCw className={cn("h-4 w-4", commercialBusy === "load" && "animate-spin")} />
                Refresh
              </button>
            </div>

            {commercialMessage && (
              <p className="rounded-xl border border-primary/20 bg-primary/10 px-4 py-3 text-sm text-muted-foreground">{commercialMessage}</p>
            )}

            <div className="grid gap-4 lg:grid-cols-3">
              <GlowCard className="lg:col-span-2">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="text-sm uppercase tracking-[0.22em] text-primary">Current Plan</p>
                    <h3 className="mt-2 text-3xl font-bold">{commercialOverview?.plan?.name || "Loading..."}</h3>
                    <p className="mt-1 text-sm text-muted-foreground">{commercialOverview?.plan?.description || "Plan details will appear after sign in."}</p>
                  </div>
                  <StatusBadge label={commercialOverview?.subscription?.status || "checking"} />
                </div>
                <div className="mt-6 grid gap-3 sm:grid-cols-3">
                  <MetricCard label="Billing" value={commercialOverview?.subscription?.billing_interval || "Free"} />
                  <MetricCard label="Student Price" value={commercialOverview?.student_pricing_available ? "Available" : "Locked"} />
                  <MetricCard label="Provider" value={commercialOverview?.subscription?.provider || "CEASER"} />
                </div>
              </GlowCard>

              <GlowCard>
                <div className="flex items-start gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/15 text-primary">
                    <GraduationCap className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="font-semibold">Student Verification</p>
                    <p className="text-sm text-muted-foreground">NHCE email or private document fallback.</p>
                  </div>
                </div>
                <div className="mt-4">
                  <StatusBadge label={commercialOverview?.student_verification?.status || "not_started"} />
                  {commercialOverview?.student_verification?.institutional_email && (
                    <p className="mt-2 text-sm text-muted-foreground">{commercialOverview.student_verification.institutional_email}</p>
                  )}
                </div>
              </GlowCard>
            </div>

            <GlowCard>
              <div className="grid gap-4 lg:grid-cols-2">
                <div className="space-y-3">
                  <h3 className="font-semibold">Instant NHCE Email Verification</h3>
                  <p className="text-sm text-muted-foreground">Allowed student domain: newhorizonindia.edu. Enter the verification code to confirm eligibility.</p>
                  <input
                    value={studentEmail}
                    onChange={(event) => setStudentEmail(event.target.value)}
                    placeholder="student@newhorizonindia.edu"
                    className="h-11 w-full rounded-xl border border-border bg-background px-3 text-sm outline-none focus:border-primary"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => void startStudentVerification()}
                      disabled={commercialBusy === "student-email"}
                      className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:opacity-50"
                    >
                      Start Email Check
                    </button>
                    <input
                      value={studentOtp}
                      onChange={(event) => setStudentOtp(event.target.value)}
                      placeholder="000000"
                      className="h-10 w-28 rounded-xl border border-border bg-background px-3 text-sm outline-none focus:border-primary"
                    />
                    <button
                      onClick={() => void confirmStudentVerification()}
                      disabled={commercialBusy === "student-confirm"}
                      className="rounded-xl border border-border px-4 py-2 text-sm font-semibold transition hover:bg-secondary disabled:opacity-50"
                    >
                      Confirm
                    </button>
                  </div>
                </div>

                <div className="space-y-3">
                  <h3 className="font-semibold">Private Document Fallback</h3>
                  <p className="text-sm text-muted-foreground">For students without approved institutional email. Upload your student ID here and submit it for review.</p>
                  <label className="flex min-h-24 cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-background/50 px-4 py-5 text-center transition hover:border-primary/60 hover:bg-primary/5">
                    <Upload className="mb-2 h-5 w-5 text-primary" />
                    <span className="text-sm font-semibold text-foreground">
                      {studentDocumentFile?.name || uploadedStudentDocument?.name || "Choose student ID document"}
                    </span>
                    <span className="mt-1 text-xs text-muted-foreground">PDF, image, or document. It will be uploaded and submitted in one step.</span>
                    <input
                      type="file"
                      accept=".pdf,.png,.jpg,.jpeg,.webp,.doc,.docx"
                      className="hidden"
                      onChange={(event) => {
                        setStudentDocumentFile(event.target.files?.[0] ?? null)
                        setUploadedStudentDocument(null)
                      }}
                    />
                  </label>
                  <button
                    onClick={() => void submitStudentDocument()}
                    disabled={commercialBusy === "student-document"}
                    className="rounded-xl border border-border px-4 py-2 text-sm font-semibold transition hover:bg-secondary disabled:opacity-50"
                  >
                    Submit for Review
                  </button>
                </div>
              </div>
            </GlowCard>

            <div className="grid gap-4 lg:grid-cols-3">
              {commercialPlans.map((plan) => (
                <GlowCard key={plan.code}>
                  <div className="flex h-full flex-col gap-4">
                    <div>
                      <p className="text-sm uppercase tracking-[0.18em] text-primary">{plan.code}</p>
                      <h3 className="mt-2 text-xl font-bold">{plan.name}</h3>
                      <p className="mt-1 text-sm text-muted-foreground">{plan.description}</p>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <MetricCard label="Monthly" value={formatPrice(plan.monthly_price, plan.currency)} />
                      <MetricCard label="Annual" value={formatPrice(plan.annual_price, plan.currency)} />
                    </div>
                    <div className="mt-auto flex gap-2">
                      <button
                        onClick={() => void runTestUpgrade(plan.code, "monthly")}
                        disabled={plan.code === "FREE" || commercialBusy === `${plan.code}-monthly`}
                        className="flex-1 rounded-xl bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-45"
                      >
                        Activate Monthly
                      </button>
                      <button
                        onClick={() => void runTestUpgrade(plan.code, "annual")}
                        disabled={plan.code === "FREE" || commercialBusy === `${plan.code}-annual`}
                        className="flex-1 rounded-xl border border-border px-3 py-2 text-sm font-semibold transition hover:bg-secondary disabled:cursor-not-allowed disabled:opacity-45"
                      >
                        Activate Annual
                      </button>
                    </div>
                  </div>
                </GlowCard>
              ))}
            </div>

            <GlowCard>
              <h3 className="mb-4 font-semibold">Usage Limits</h3>
              {commercialOverview?.usage?.length ? (
                <div className="grid gap-3 md:grid-cols-2">
                  {commercialOverview.usage.map((item) => (
                    <div key={item.entitlement_key} className="rounded-2xl border border-border bg-background/50 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-medium">{humanizeEntitlement(item.entitlement_key)}</p>
                        <span className="text-sm text-muted-foreground">{item.used_quantity}/{item.limit_value}</span>
                      </div>
                      <div className="mt-3 h-2 overflow-hidden rounded-full bg-secondary">
                        <div
                          className="h-full rounded-full bg-primary"
                          style={{ width: `${Math.min(100, Math.round((item.used_quantity / Math.max(1, item.limit_value)) * 100))}%` }}
                        />
                      </div>
                      <p className="mt-2 text-xs text-muted-foreground">{item.remaining} remaining · resets {item.reset_period}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="rounded-2xl border border-dashed border-border p-4 text-sm text-muted-foreground">
                  Usage counters will appear after the first tracked CEASER action.
                </p>
              )}
            </GlowCard>
          </div>
        )}

        {activeSection === "security" && (
          <div className="max-w-2xl space-y-6">
            <h2 className="text-2xl font-bold">Security</h2>
            {securityMessage && <p className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-muted-foreground">{securityMessage}</p>}
            
            <GlowCard>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Model Provider</p>
                    <p className="text-sm text-muted-foreground">AI requests are routed securely through the CEASER backend.</p>
                  </div>
                  <span className="rounded-full bg-primary/10 px-3 py-1 text-sm font-medium text-primary">
                    Active
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Key className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium">Password</p>
                      <p className="text-sm text-muted-foreground">Update your password for this account</p>
                    </div>
                  </div>
                </div>
                <div className="flex gap-2">
                  <input
                    type="password"
                    value={newPassword}
                    onChange={(event) => setNewPassword(event.target.value)}
                    placeholder="New password"
                    className="h-10 min-w-0 flex-1 rounded-lg border border-border bg-background px-3 text-sm outline-none focus:border-primary"
                  />
                  <button onClick={() => void updatePassword()} disabled={securityBusy === "password"} className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50">
                    {securityBusy === "password" ? "Saving" : "Update"}
                  </button>
                </div>
                <div className="border-t border-border pt-4">
                  <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                      <Smartphone className="h-5 w-5 text-muted-foreground" />
                      <div>
                        <p className="font-medium">Two-Factor Authentication</p>
                        <p className="text-sm text-muted-foreground">Use an authenticator app with a 6-digit code</p>
                      </div>
                    </div>
                    <button onClick={() => void startMfaEnrollment()} disabled={securityBusy === "mfa"} className="rounded-lg border border-border px-4 py-2 text-sm transition-colors hover:bg-secondary disabled:opacity-50">
                      {securityBusy === "mfa" ? "Starting" : "Set up"}
                    </button>
                  </div>
                  {mfaEnrollment && (
                    <div className="mt-4 space-y-3 rounded-xl border border-primary/20 bg-primary/10 p-4">
                      {getMfaQr(mfaEnrollment) ? (
                        <img src={getMfaQr(mfaEnrollment)} alt="Authenticator QR code" className="h-40 w-40 rounded-xl bg-white p-2" />
                      ) : (
                        <p className="text-sm text-muted-foreground">Secret: {getMfaSecret(mfaEnrollment) || "Open your authenticator app and use the setup details returned by Supabase."}</p>
                      )}
                      <div className="flex gap-2">
                        <input
                          value={mfaCode}
                          onChange={(event) => setMfaCode(event.target.value)}
                          placeholder="6-digit code"
                          className="h-10 min-w-0 flex-1 rounded-lg border border-border bg-background px-3 text-sm outline-none focus:border-primary"
                        />
                        <button onClick={() => void verifyMfaEnrollment()} disabled={securityBusy === "mfa-verify"} className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50">
                          {securityBusy === "mfa-verify" ? "Verifying" : "Verify"}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Smartphone className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium">Active Sessions</p>
                      <p className="text-sm text-muted-foreground">Current device session is managed by sign in/out</p>
                    </div>
                  </div>
                </div>
                <div className="rounded-xl border border-border bg-background/50 p-4">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <p className="text-sm font-medium">Current browser session</p>
                      <p className="text-xs text-muted-foreground">This is the session CEASER is using for API requests on this device.</p>
                    </div>
                    <span className={cn("rounded-full px-3 py-1 text-xs font-semibold", sessionActive ? "bg-emerald-500/15 text-emerald-300" : "bg-amber-500/15 text-amber-300")}>
                      {sessionActive ? "Active" : "Not signed in"}
                    </span>
                  </div>
                </div>
              </div>
            </GlowCard>
          </div>
        )}

        {activeSection === "preferences" && (
          <div className="max-w-2xl space-y-6">
            <h2 className="text-2xl font-bold">Preferences</h2>
            
            <GlowCard>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Bell className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium">Notifications</p>
                      <p className="text-sm text-muted-foreground">Push & email notifications</p>
                    </div>
                  </div>
                  <SettingSwitch checked={preferences.notifications} onChange={(checked) => savePreferences({ notifications: checked })} />
                </div>
              </div>
            </GlowCard>
          </div>
        )}

        {activeSection === "about" && (
          <div className="max-w-2xl space-y-6">
            <h2 className="text-2xl font-bold">About Ceaser</h2>
            
            <GlowCard>
              <div className="flex items-center gap-4">
                <CeaserLogo size="lg" showText={false} />
                <div>
                  <h3 className="text-lg font-semibold">CEASER OS</h3>
                  <p className="text-muted-foreground">Personal Intelligence Operating System</p>
                  <p className="text-sm text-muted-foreground">Version 1.0.0</p>
                </div>
              </div>
            </GlowCard>

            <GlowCard>
              <div className="space-y-3">
                <InfoRow label="Release Notes" value="Coming with packaged release" />
                <InfoRow label="Terms of Service" value="Prepared for launch assets" />
                <InfoRow label="Privacy Policy" value="Prepared for launch assets" />
                <InfoRow label="Support" value="Founder-led support for launch users" />
              </div>
            </GlowCard>
          </div>
        )}
      </div>
    </div>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 py-2">
      <span className="font-medium">{label}</span>
      <span className="text-right text-sm text-muted-foreground">{value}</span>
    </div>
  )
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border bg-background/50 p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 font-semibold">{value}</p>
    </div>
  )
}

function StatusBadge({ label }: { label: string }) {
  const normalized = label.replaceAll("_", " ")
  const positive = ["active", "approved", "connected"].includes(label)
  const pending = ["email_pending", "manual_review", "checking"].includes(label)
  return (
    <span
      className={cn(
        "inline-flex w-fit rounded-full px-3 py-1 text-xs font-semibold capitalize",
        positive && "bg-emerald-500/15 text-emerald-300",
        pending && "bg-amber-500/15 text-amber-300",
        !positive && !pending && "bg-secondary text-muted-foreground",
      )}
    >
      {normalized}
    </span>
  )
}

function formatPrice(amount: number, currency: string) {
  if (!amount) return "Free"
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: currency || "INR",
    maximumFractionDigits: 0,
  }).format(amount / 100)
}

function humanizeEntitlement(key: string) {
  return key
    .replaceAll("_", " ")
    .replace(/\b\w/g, (match) => match.toUpperCase())
}

function SettingSwitch({ checked, disabled, onChange }: { checked: boolean; disabled?: boolean; onChange: (checked: boolean) => void }) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        "h-6 w-11 rounded-full p-0.5 transition disabled:opacity-50",
        checked ? "bg-primary/25" : "bg-secondary",
      )}
      aria-pressed={checked}
    >
      <span className={cn("block h-5 w-5 rounded-full transition-transform", checked ? "translate-x-5 bg-primary" : "bg-muted-foreground")} />
    </button>
  )
}

function RangeSetting({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string
  value: number
  min: number
  max: number
  step: number
  onChange: (value: number) => void
}) {
  const [draft, setDraft] = useState(value)

  useEffect(() => {
    setDraft(value)
  }, [value])

  return (
    <label className="block rounded-xl border border-border bg-background/50 p-3">
      <span className="flex items-center justify-between gap-3 text-sm font-medium">
        {label}
        <span className="text-xs text-muted-foreground">{draft.toFixed(step < 0.1 ? 2 : 1)}</span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={draft}
        onChange={(event) => setDraft(Number(event.target.value))}
        onMouseUp={() => onChange(draft)}
        onTouchEnd={() => onChange(draft)}
        className="mt-3 w-full accent-primary"
      />
    </label>
  )
}

function defaultVoiceSettings(): VoiceSettingsRecord {
  return {
    id: "local",
    user_id: "local",
    voice_enabled: true,
    auto_speak_responses: true,
    voice_provider: "auto",
    preferred_voice: null,
    speech_speed: 1,
    speech_volume: 1,
    language: "en",
  }
}

function getMfaQr(enrollment: Record<string, unknown>) {
  const totp = enrollment.totp as Record<string, unknown> | undefined
  return String(totp?.qr_code || totp?.qrCode || "")
}

function getMfaSecret(enrollment: Record<string, unknown>) {
  const totp = enrollment.totp as Record<string, unknown> | undefined
  return String(totp?.secret || "")
}
