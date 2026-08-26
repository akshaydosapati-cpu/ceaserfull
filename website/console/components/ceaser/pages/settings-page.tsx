"use client"

import { useEffect, useRef, useState } from "react"
import { user } from "@/lib/data"
import { getUserDisplayName, readUserProfile } from "@/lib/user-profile"
import { GlowCard } from "../glow-card"
import { CeaserLogo } from "../ceaser-logo"
import { CeaserSelect } from "../ceaser-select"
import { authApi } from "@/lib/api/auth"
import { getAccessToken } from "@/lib/api/client"
import { ENABLE_BILLING_SECTION } from "@/lib/ceaser/config"
import {
  commercialApi,
  type BillingCreateSubscriptionResponse,
  type BillingInvoice,
  type BillingSubscriptionOverview,
  type CommercialPlan,
  type CommercialSubscription,
  type StudentVerification,
} from "@/lib/api/commercial"
import { filesApi, type FileRecord } from "@/lib/api/files"
import { voiceApi, type VoiceSettingsRecord } from "@/lib/api/voice"
import { desktopApi, type DesktopDevice } from "@/lib/api/desktop"
import { cn } from "@/lib/utils"
import { 
  User, 
  Mic, Shield, 
  Sliders,
  Info,
  Moon,
  Bell,
  Key,
  Smartphone,
  Activity,
  Sparkles,
  Crown,
  CircleCheck,
  Download,
  ArrowRight,
  Landmark,
  CreditCard,
  GraduationCap,
  Upload,
  Loader2
  ,Eye, EyeOff
} from "lucide-react"

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => {
      open: () => void
      on: (event: string, callback: (response: unknown) => void) => void
    }
  }
}


const settingsSections = [
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


  ...(ENABLE_BILLING_SECTION
    ? [{
      id: "billing",
      label: "Billing & Student Access",
      icon: CreditCard,
      description: "Plans, usage, verification",
    }]
    : []),
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


const PROFILE_KEY = "ceaser_user_profile"
const PREFERENCES_KEY = "ceaser_preferences"
const COMMERCIAL_CACHE_KEY = "ceaser_commercial_cache_v1"
type CompanionPreferences = {
  notifications: boolean
  conversation_style: "balanced" | "casual" | "professional"
  humor: "off" | "low" | "medium" | "high"
  roasting: "off" | "light" | "medium"
  proactive_mode: "off" | "important_only" | "balanced" | "companion"
  language: "auto" | "English" | "Telugu" | "Kannada" | "Hindi" | "Tamil" | "Malayalam"
  code_switching: boolean
}
const defaultCompanionPreferences: CompanionPreferences = {
  notifications: true,
  conversation_style: "balanced",
  humor: "medium",
  roasting: "light",
  proactive_mode: "balanced",
  language: "auto",
  code_switching: true,
}
const roleOptions = [
  { value: "Student", label: "Student", description: "Study plans, notes, exam prep" },
  { value: "Founder", label: "Founder", description: "Startups, strategy, fundraising" },
  { value: "Professional", label: "Professional", description: "Workflows, meetings, productivity" },
  { value: "Creator", label: "Creator", description: "Content, campaigns, publishing" },
  { value: "Developer", label: "Developer", description: "Technical planning and documentation" },
  { value: "Personal", label: "Personal", description: "Personal memory and daily assistance" },
]

let razorpayLoader: Promise<void> | null = null
const RAZORPAY_PUBLIC_KEY = process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID || ""

function ensureRazorpayLoaded() {
  if (typeof window === "undefined") return Promise.resolve()
  if (window.Razorpay) return Promise.resolve()
  if (razorpayLoader) return razorpayLoader
  razorpayLoader = new Promise<void>((resolve, reject) => {
    const script = document.createElement("script")
    script.src = "https://checkout.razorpay.com/v1/checkout.js"
    script.async = true
    script.onload = () => resolve()
    script.onerror = () => reject(new Error("Razorpay checkout could not be loaded."))
    document.body.appendChild(script)
  })
  return razorpayLoader
}

export function SettingsPage() {
  const [activeSection, setActiveSection] = useState("profile")
  const [profile, setProfile] = useState<{ name?: string; email?: string; useCase?: string } | null>(null)
  const [profileDraft, setProfileDraft] = useState({ name: getUserDisplayName(readUserProfile(), user.name), email: "", useCase: user.role })
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmNewPassword, setConfirmNewPassword] = useState("")
  const [passwordModalOpen, setPasswordModalOpen] = useState(false)
  const [mfaModalOpen, setMfaModalOpen] = useState(false)
  const [mfaSetupPassword, setMfaSetupPassword] = useState("")
  const [mfaEnabled, setMfaEnabled] = useState(false)
  const [securityMessage, setSecurityMessage] = useState("")
  const [securityBusy, setSecurityBusy] = useState<string | null>(null)
  const [mfaEnrollment, setMfaEnrollment] = useState<Record<string, unknown> | null>(null)
  const [mfaCode, setMfaCode] = useState("")
  const [voiceSettings, setVoiceSettings] = useState<VoiceSettingsRecord | null>(null)
  const [voiceBusy, setVoiceBusy] = useState(false)
  const [voiceMessage, setVoiceMessage] = useState("")
  const [browserVoices, setBrowserVoices] = useState<SpeechSynthesisVoice[]>([])
  const [sessionActive, setSessionActive] = useState(false)
  const [desktopDevices, setDesktopDevices] = useState<DesktopDevice[]>([])
  const [desktopDevicesBusy, setDesktopDevicesBusy] = useState(false)
  const [desktopDevicesMessage, setDesktopDevicesMessage] = useState("")
  const [preferences, setPreferences] = useState<CompanionPreferences>(defaultCompanionPreferences)
  const [billingOverview, setBillingOverview] = useState<BillingSubscriptionOverview | null>(null)
  const [commercialPlans, setCommercialPlans] = useState<CommercialPlan[]>([])
  const [commercialBusy, setCommercialBusy] = useState<string | null>(null)
  const [commercialMessage, setCommercialMessage] = useState("")
  const [studentVerification, setStudentVerification] = useState<StudentVerification | null>(null)
  const [billingIntervalView, setBillingIntervalView] = useState<"monthly" | "annual">("monthly")
  const [studentEmail, setStudentEmail] = useState("")
  const [studentOtp, setStudentOtp] = useState("")
  const [studentDocumentFile, setStudentDocumentFile] = useState<File | null>(null)
  const [uploadedStudentDocument, setUploadedStudentDocument] = useState<FileRecord | null>(null)
  const [pendingVerificationId, setPendingVerificationId] = useState("")
  const [studentModalOpen, setStudentModalOpen] = useState(false)
  const [studentCheckoutPlan, setStudentCheckoutPlan] = useState<CommercialPlan | null>(null)
  const [checkoutModalOpen, setCheckoutModalOpen] = useState(false)
  const commercialLoadedRef = useRef(false)
  const commercialPrefetchRef = useRef(false)
  const plansSectionRef = useRef<HTMLDivElement | null>(null)
  const invoicesSectionRef = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    if (!ENABLE_BILLING_SECTION && activeSection === "billing") {
      setActiveSection("status")
    }
  }, [activeSection])
  useEffect(() => {
    try {
      const savedProfile = JSON.parse(window.localStorage.getItem(PROFILE_KEY) || "null")
      setProfile(savedProfile)
      setProfileDraft({
        name: getUserDisplayName(savedProfile, user.name),
        email: savedProfile?.email || "",
        useCase: savedProfile?.useCase || user.role,
      })
      setSessionActive(Boolean(getAccessToken()))
      setPreferences({ ...defaultCompanionPreferences, ...JSON.parse(window.localStorage.getItem(PREFERENCES_KEY) || "{}") })
    } catch {
      setProfile(null)
      setSessionActive(false)
    }
  }, [])

  useEffect(() => {
    if (activeSection !== "security" || !getAccessToken()) return
    void loadDesktopDevices()
  }, [activeSection])

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
    hydrateCommercialCache()
    if (getAccessToken() && !commercialPrefetchRef.current) {
      commercialPrefetchRef.current = true
      void loadCommercialData({ silent: true })
    }
  }, [])

  useEffect(() => {
    if (activeSection !== "billing") return
    hydrateCommercialCache()
    void ensureRazorpayLoaded().catch(() => undefined)
    if (commercialLoadedRef.current) return
    commercialLoadedRef.current = true
    void loadCommercialData()
  }, [activeSection])

  useEffect(() => {
    if (typeof document === "undefined") return
    const urls = ["https://checkout.razorpay.com", "https://api.razorpay.com"]
    const links = urls.map((href) => {
      const link = document.createElement("link")
      link.rel = "preconnect"
      link.href = href
      document.head.appendChild(link)
      return link
    })
    return () => {
      links.forEach((link) => link.remove())
    }
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

  useEffect(() => {
    if (billingOverview?.subscription?.billing_interval === "annual") {
      setBillingIntervalView("annual")
      return
    }
    setBillingIntervalView("monthly")
  }, [billingOverview?.subscription?.billing_interval, activeSection])

  const displayName = getUserDisplayName(profile, user.name)
  const displayEmail = profile?.email || "Signed in account"
  const displayRole = profile?.useCase || user.role

  function isCommercialTimeoutMessage(message: string) {
    const normalized = message.trim().toLowerCase()
    return normalized.includes("taking longer than expected") || normalized.includes("signal timed out")
  }

  function savePreferences(patch: Partial<typeof preferences>) {
    setPreferences((current) => {
      const next = { ...current, ...patch }
      window.localStorage.setItem(PREFERENCES_KEY, JSON.stringify(next))
      return next
    })
  }

  async function saveProfile() {
    const next = {
      name: profileDraft.name.trim() || getUserDisplayName(profile, user.name),
      email: profileDraft.email.trim(),
      useCase: profileDraft.useCase,
    }
    await authApi.updateProfile(next.name)
    window.localStorage.setItem(PROFILE_KEY, JSON.stringify(next))
    setProfile(next)
  }

  async function loadDesktopDevices() {
    setDesktopDevicesBusy(true)
    setDesktopDevicesMessage("")
    try {
      setDesktopDevices(await desktopApi.listDevices())
    } catch (error) {
      setDesktopDevicesMessage(error instanceof Error ? error.message : "Could not load connected desktop devices.")
    } finally {
      setDesktopDevicesBusy(false)
    }
  }

  async function revokeDesktopDevice(deviceId: string) {
    setDesktopDevicesBusy(true)
    setDesktopDevicesMessage("")
    try {
      await desktopApi.revokeDevice(deviceId)
      setDesktopDevices((current) => current.map((device) => device.device_id === deviceId ? { ...device, status: "revoked", revoked_at: new Date().toISOString() } : device))
      setDesktopDevicesMessage("Desktop device disconnected.")
    } catch (error) {
      setDesktopDevicesMessage(error instanceof Error ? error.message : "Could not disconnect the desktop device.")
    } finally {
      setDesktopDevicesBusy(false)
    }
  }

  function hydrateCommercialCache() {
    if (typeof window === "undefined") return
    try {
      const raw = window.localStorage.getItem(COMMERCIAL_CACHE_KEY)
      if (!raw) return
      const cached = JSON.parse(raw) as {
        timestamp?: number
        billingOverview?: BillingSubscriptionOverview | null
        studentVerification?: StudentVerification | null
        plans?: CommercialPlan[]
      }
      if (!cached?.timestamp || Date.now() - cached.timestamp > 10 * 60_000) return
      if (cached.billingOverview) {
        setBillingOverview(cached.billingOverview)
      }
      if (cached.studentVerification) {
        setStudentVerification(cached.studentVerification)
        setPendingVerificationId(cached.studentVerification.id || "")
        setStudentEmail(cached.studentVerification.institutional_email || "")
      }
      if (cached.plans?.length) {
        setCommercialPlans(cached.plans)
      }
    } catch {
      // Ignore cache errors.
    }
  }

  function persistCommercialCache(next: {
    billingOverview?: BillingSubscriptionOverview | null
    studentVerification?: StudentVerification | null
    plans?: CommercialPlan[]
  }) {
    if (typeof window === "undefined") return
    try {
      const currentRaw = window.localStorage.getItem(COMMERCIAL_CACHE_KEY)
      const current = currentRaw
        ? (JSON.parse(currentRaw) as {
            billingOverview?: BillingSubscriptionOverview | null
            studentVerification?: StudentVerification | null
            plans?: CommercialPlan[]
          })
        : {}
      window.localStorage.setItem(
        COMMERCIAL_CACHE_KEY,
        JSON.stringify({
          timestamp: Date.now(),
          billingOverview: next.billingOverview ?? current.billingOverview ?? null,
          studentVerification: next.studentVerification ?? current.studentVerification ?? null,
          plans: next.plans ?? current.plans ?? [],
        }),
      )
    } catch {
      // Ignore cache errors.
    }
  }

  async function loadCommercialData(options?: { silent?: boolean }) {
    const silent = Boolean(options?.silent)
    const hadBillingOverview = Boolean(billingOverview)
    const hadPlans = commercialPlans.length > 0
    if (!silent) {
      setCommercialBusy("load")
    }
    if (!silent && activeSection === "billing") {
      setCommercialMessage("")
    }
    try {
      const [billingResult, plansResult] = await Promise.allSettled([commercialApi.billingOverview(), commercialApi.plans()])

      if (billingResult.status === "fulfilled") {
        setBillingOverview(billingResult.value)
        persistCommercialCache({ billingOverview: billingResult.value })
      }

      if (plansResult.status === "fulfilled") {
        setCommercialPlans(plansResult.value)
        persistCommercialCache({ plans: plansResult.value })
      }

      const errors: string[] = []
      if (billingResult.status === "rejected") {
        errors.push(billingResult.reason instanceof Error ? billingResult.reason.message : "Billing overview is unavailable.")
      }
      if (plansResult.status === "rejected") {
        errors.push(plansResult.reason instanceof Error ? plansResult.reason.message : "Plans are unavailable.")
      }

      if (errors.length && activeSection === "billing" && !silent) {
        const hasRenderableState =
          billingResult.status === "fulfilled" ||
          plansResult.status === "fulfilled" ||
          hadBillingOverview ||
          hadPlans

        if (!hasRenderableState) {
          const firstError = errors[0] || "Could not load billing and student access."
          setCommercialMessage(
            isCommercialTimeoutMessage(firstError)
              ? "Billing details are syncing. Please wait a moment."
              : firstError,
          )
        } else if (billingResult.status === "fulfilled" || plansResult.status === "fulfilled") {
          setCommercialMessage("")
        }
      }
    } finally {
      if (!silent) {
        setCommercialBusy(null)
      }
    }
  }

  async function loadStudentVerificationStatus() {
    try {
      const status = await commercialApi.studentStatus()
      setStudentVerification(status)
      setPendingVerificationId(status?.id || "")
      setStudentEmail(status?.institutional_email || "")
      persistCommercialCache({ studentVerification: status })
      return status
    } catch {
      return null
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
      await loadStudentVerificationStatus()
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
      const verification = await commercialApi.confirmStudentEmail(pendingVerificationId, studentOtp.trim())
      setStudentVerification(verification)
      persistCommercialCache({ studentVerification: verification })
      setStudentOtp("")
      setCommercialMessage("Student email verified.")
      await loadCommercialData()
      if (studentCheckoutPlan) {
        setStudentModalOpen(false)
        await runTestUpgrade(studentCheckoutPlan.code, "monthly")
      }
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
      const verification = await commercialApi.submitStudentDocument(uploaded.id)
      setStudentVerification(verification)
      persistCommercialCache({ studentVerification: verification })
      setStudentDocumentFile(null)
      setCommercialMessage("Student document verified. Student Pro is now unlocked.")
      await loadCommercialData()
      if (studentCheckoutPlan) {
        setStudentModalOpen(false)
        await runTestUpgrade(studentCheckoutPlan.code, "monthly")
      }
    } catch (error) {
      setCommercialMessage(error instanceof Error ? error.message : "Could not submit student document.")
    } finally {
      setCommercialBusy(null)
    }
  }

  async function openStudentCheckout(plan: CommercialPlan) {
    setStudentCheckoutPlan(plan)
    setStudentModalOpen(true)
    setCommercialMessage("")
    await loadStudentVerificationStatus()
  }

  async function handleManagePlan() {
    if (!billingOverview?.subscription?.provider_subscription_id) {
      plansSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })
      setCommercialMessage("Choose a paid subscription plan to start recurring billing.")
      return
    }
    invoicesSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })
    setCommercialMessage("Your recurring subscription is active. You can cancel it below if needed.")
  }

  async function handleCancelOrResumeSubscription() {
    if (!billingOverview?.subscription?.provider_subscription_id || billingOverview.plan.code === "FREE") {
      setCommercialMessage("This account does not have an active recurring Razorpay subscription to manage.")
      plansSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })
      return
    }
    setCommercialBusy("subscription-manage")
    setCommercialMessage("")
    try {
      const result = billingOverview.subscription.cancel_at_period_end
        ? await commercialApi.resumeSubscription()
        : await commercialApi.cancelSubscription()
      setCommercialMessage(result.message)
      await loadCommercialData()
    } catch (error) {
      setCommercialMessage(error instanceof Error ? error.message : "Could not update the subscription.")
    } finally {
      setCommercialBusy(null)
    }
  }

  function handleInvoiceOpen(invoice: BillingInvoice) {
    if (typeof window === "undefined") return
    if (invoice.hosted_url) {
      window.open(invoice.hosted_url, "_blank", "noopener,noreferrer")
      return
    }
    setCommercialMessage("Invoice download will appear here once Razorpay issues the hosted invoice.")
  }

  async function runTestUpgrade(planCode: string, interval: "monthly" | "annual") {
    setCommercialBusy(`${planCode}-${interval}`)
    setCommercialMessage("Opening secure checkout...")
    setCheckoutModalOpen(true)
    try {
      const [, checkoutConfig] = await Promise.all([
        ensureRazorpayLoaded(),
        commercialApi.createSubscription(planCode, interval),
      ])
      const RazorpayCheckout = window.Razorpay
      if (!RazorpayCheckout) {
        throw new Error("Razorpay checkout is unavailable on this device.")
      }
      await new Promise<void>((resolve, reject) => {
        const subscriptionConfig = checkoutConfig as BillingCreateSubscriptionResponse
        const checkoutKey = subscriptionConfig.key_id || RAZORPAY_PUBLIC_KEY
        if (!checkoutKey) {
          reject(new Error("Razorpay public key is not configured for this environment."))
          return
        }
        const checkout = new RazorpayCheckout({
          key: checkoutKey,
          subscription_id: subscriptionConfig.subscription_id,
          amount: subscriptionConfig.amount,
          currency: subscriptionConfig.currency,
          name: subscriptionConfig.name || "CEASER",
          description: subscriptionConfig.description || `${planCode} plan`,
          prefill: {
            name: subscriptionConfig.prefill_name || profileDraft.name || displayName,
            email: subscriptionConfig.prefill_email || profileDraft.email || displayEmail,
          },
          theme: {
            color: subscriptionConfig.theme_color || "#6d4cff",
          },
          modal: {
            ondismiss: () => {
              reject(new Error("Payment was cancelled."))
            },
          },
          handler: async (response: Record<string, string>) => {
            try {
              const verified = await commercialApi.verifyPayment({
                razorpay_payment_id: response.razorpay_payment_id,
                razorpay_order_id: response.razorpay_order_id,
                razorpay_subscription_id: response.razorpay_subscription_id,
                razorpay_signature: response.razorpay_signature,
              })
              setCommercialMessage(verified.message || "Payment verified successfully.")
              resolve()
            } catch (error) {
              reject(error)
            }
          },
        })
        checkout.on("payment.failed", () => {
          reject(new Error("Payment failed. Please try again."))
        })
        setCheckoutModalOpen(false)
        checkout.open()
      })
      await loadCommercialData()
    } catch (error) {
      setCheckoutModalOpen(false)
      setCommercialMessage(error instanceof Error ? error.message : "Could not start checkout.")
    } finally {
      setCheckoutModalOpen(false)
      setCommercialBusy(null)
    }
  }

  function handleSelectFreePlan() {
    setCommercialMessage("Free access is already available. You can continue using CEASER on the Free plan anytime.")
    plansSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })
  }

  async function updatePassword() {
    const passwordIsValid = newPassword.length >= 8 && /[A-Z]/.test(newPassword) && /[a-z]/.test(newPassword) && /\d/.test(newPassword) && /[^A-Za-z0-9]/.test(newPassword)
    if (!currentPassword) {
      setSecurityMessage("Enter your current password.")
      return
    }
    if (!passwordIsValid) {
      setSecurityMessage("Your new password does not meet the requirements.")
      return
    }
    if (newPassword !== confirmNewPassword) {
      setSecurityMessage("New passwords do not match.")
      return
    }
    setSecurityBusy("password")
    setSecurityMessage("")
    try {
      await authApi.updatePassword(currentPassword, newPassword)
      setCurrentPassword("")
      setNewPassword("")
      setConfirmNewPassword("")
      setSecurityMessage("Password updated.")
      setPasswordModalOpen(false)
    } catch (error) {
      setSecurityMessage(error instanceof Error ? error.message : "Could not update password.")
    } finally {
      setSecurityBusy(null)
    }
  }

  async function startMfaEnrollment() {
    if (!mfaSetupPassword) {
      setSecurityMessage("Enter your password to continue.")
      return
    }
    setSecurityBusy("mfa")
    setSecurityMessage("")
    try {
      await authApi.verifyPassword(mfaSetupPassword)
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
      setMfaEnabled(true)
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
        {activeSection === "profile" && (
          <div className="max-w-5xl space-y-6">
            <h2 className="text-2xl font-bold">Profile</h2>

            <div className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
              <GlowCard>
                <div className="flex h-full flex-col justify-between gap-6">
                  <div className="space-y-5">
                    <div className="flex items-center gap-4">
                      <div className="flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-to-br from-primary/35 via-primary/20 to-cyan-400/10 text-2xl font-bold text-primary shadow-[0_16px_40px_rgba(79,140,255,0.18)]">
                        {displayName.charAt(0).toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm uppercase tracking-[0.22em] text-primary/80">Account Identity</p>
                        <h3 className="truncate text-2xl font-semibold">{displayName}</h3>
                        <p className="mt-1 text-sm text-muted-foreground">{displayRole}</p>
                      </div>
                    </div>

                    <div className="space-y-3 rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-sm text-muted-foreground">Display name</span>
                        <span className="max-w-[55%] truncate text-sm font-medium">{profileDraft.name || displayName}</span>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-sm text-muted-foreground">Email</span>
                        <span className="max-w-[55%] truncate text-sm font-medium">{profileDraft.email || displayEmail}</span>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-sm text-muted-foreground">Role</span>
                        <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">{profileDraft.useCase}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </GlowCard>

              <GlowCard>
                <div className="space-y-6">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h3 className="text-xl font-semibold">Edit Profile</h3>
                      <p className="mt-1 text-sm text-muted-foreground">Update your identity, contact details, and working style in one place.</p>
                    </div>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="md:col-span-2">
                      <label className="mb-2 block text-sm font-medium">Full Name</label>
                      <input
                        type="text"
                        value={profileDraft.name}
                        onChange={(event) => setProfileDraft((current) => ({ ...current, name: event.target.value }))}
                        className="w-full rounded-2xl border border-border bg-background px-4 py-3 outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="mb-2 block text-sm font-medium">Email</label>
                      <input
                        type="email"
                        value={profileDraft.email}
                        onChange={(event) => setProfileDraft((current) => ({ ...current, email: event.target.value }))}
                        placeholder={displayEmail}
                        className="w-full rounded-2xl border border-border bg-background px-4 py-3 outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="mb-2 block text-sm font-medium">Role</label>
                      <CeaserSelect
                        value={profileDraft.useCase}
                        onValueChange={(value) => setProfileDraft((current) => ({ ...current, useCase: value }))}
                        options={roleOptions}
                      />
                    </div>
                  </div>

                  <div className="flex flex-col gap-3 border-t border-white/10 pt-5 sm:flex-row sm:items-center sm:justify-between">
                    <p className="text-sm text-muted-foreground">Your profile updates are saved locally and reflected across the app instantly.</p>
                    <button onClick={saveProfile} className="rounded-xl bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90">
                      Save Profile
                    </button>
                  </div>
                </div>
              </GlowCard>
            </div>
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
        {ENABLE_BILLING_SECTION && activeSection === "billing" && (() => {
          const fallbackPlan =
            commercialPlans.find((plan) => plan.code === "FREE") ||
            commercialPlans[0] ||
            null
          const hasPaidHistory = Boolean((billingOverview?.payments?.length || 0) > 0)
          const hasRecurringSubscription = Boolean(billingOverview?.subscription)
          const currentPlan =
            billingOverview?.plan && (hasRecurringSubscription || hasPaidHistory || billingOverview.plan.code === "FREE")
              ? billingOverview.plan
              : fallbackPlan
          const subscription = billingOverview?.subscription
          const displayedPlans = commercialPlans.length
            ? commercialPlans
            : currentPlan
              ? [currentPlan]
              : []
          const billingInterval = subscription?.billing_interval || billingIntervalView
          const billingPrice = currentPlan
            ? billingInterval === "annual"
              ? formatPrice(currentPlan.annual_price, currentPlan.currency)
              : formatPrice(currentPlan.monthly_price, currentPlan.currency)
            : formatPrice(0, "INR")
          const renewalDate = subscription?.current_period_end ? formatLongDate(subscription.current_period_end) : null
          const usageItems = billingOverview?.usage ?? []
          const planTone = getPlanTone(currentPlan?.code || "FREE")
          const studentVerified = Boolean(billingOverview?.student_pricing_available)
          const planReady = Boolean(currentPlan)
          const friendlyCommercialMessage =
            commercialMessage === "No Razorpay subscription found for this account." && currentPlan?.code && currentPlan.code !== "FREE"
              ? ""
              : commercialMessage
          const paymentRows =
            billingOverview?.payments?.map((payment) => ({
              id: payment.id,
              date: formatLongDate(payment.captured_at || new Date().toISOString()),
              reference: payment.provider_invoice_id || payment.provider_payment_id,
              amount: formatPrice(payment.amount, payment.currency),
              plan: currentPlan?.name || "CEASER Plan",
              status: payment.status || "paid",
            })) || []

          return (
            <div className="max-w-6xl space-y-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h2 className="text-2xl font-bold">Billing & Subscription</h2>
                  <p className="text-muted-foreground">Manage your plan, payment history, and usage limits.</p>
                </div>
                {commercialBusy === "load" ? <StatusBadge label="loading" /> : null}
              </div>

              {friendlyCommercialMessage && (
                <p className="rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">{friendlyCommercialMessage}</p>
              )}

              <GlowCard className="overflow-hidden">
                <div className="grid gap-8 lg:grid-cols-[1.4fr_0.9fr]">
                  <div className="space-y-6">
                    <div className="inline-flex rounded-full bg-primary/15 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-primary">
                      Current Plan
                    </div>
                    <div>
                      <div className="flex flex-wrap items-center gap-3">
                        <h3 className="text-4xl font-bold">{currentPlan?.name || "CEASER Free"}</h3>
                        <Sparkles className="h-7 w-7 text-violet-400" />
                      </div>
                      <div className="mt-2 flex flex-wrap items-end gap-3">
                        <p className="text-3xl font-bold">{billingPrice}</p>
                        {currentPlan ? (
                          <p className="pb-1 text-lg text-muted-foreground">/ {billingInterval === "annual" ? "year" : "month"}</p>
                        ) : null}
                      </div>
                      <p className="mt-3 max-w-2xl text-sm text-muted-foreground">
                        {currentPlan?.description || "Choose the right CEASER plan for your workflow and upgrade when you're ready."}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-3">
                      <StatusBadge label={subscription?.status || (planReady ? "ready" : "not_started")} />
                      {renewalDate ? <span className="text-sm text-muted-foreground">Renews on {renewalDate}</span> : null}
                      {studentVerified ? <span className="text-sm text-emerald-300">Student pricing unlocked</span> : null}
                      {!subscription && currentPlan?.code !== "FREE" && hasPaidHistory ? (
                        <span className="text-sm text-cyan-300">Plan access is active from your latest payment</span>
                      ) : null}
                    </div>
                    <div className="flex flex-wrap gap-3">
                      <button
                        onClick={() => void handleManagePlan()}
                        className="inline-flex items-center gap-2 rounded-2xl bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90"
                      >
                        <CreditCard className="h-4 w-4" />
                        Manage Plan
                      </button>
                      <button
                        onClick={() => void handleCancelOrResumeSubscription()}
                        disabled={commercialBusy === "subscription-manage" || !subscription?.provider_subscription_id}
                        className="inline-flex items-center gap-2 rounded-2xl border border-border px-5 py-3 text-sm font-semibold transition hover:bg-secondary disabled:opacity-50"
                      >
                        <ArrowRight className="h-4 w-4" />
                        {commercialBusy === "subscription-manage"
                          ? "Updating..."
                          : subscription?.cancel_at_period_end
                            ? "Resume Subscription"
                            : "Cancel Subscription"}
                      </button>
                    </div>
                  </div>

                  <div className="relative min-h-[320px] overflow-hidden rounded-[2rem] border border-white/10 bg-gradient-to-br from-violet-500/20 via-primary/10 to-cyan-500/10 p-6">
                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(124,58,237,0.35),transparent_35%),radial-gradient(circle_at_72%_28%,rgba(59,130,246,0.3),transparent_28%),radial-gradient(circle_at_50%_72%,rgba(16,185,129,0.18),transparent_30%)]" />
                    <div className="relative flex h-full items-center justify-center">
                      <div className="absolute bottom-10 left-10 h-24 w-24 rounded-full border border-violet-400/30 bg-violet-500/10 blur-[1px]" />
                      <div className="absolute right-14 top-14 h-10 w-10 rounded-full bg-cyan-400/70 blur-[1px]" />
                      <div className="absolute right-16 bottom-20 h-20 w-20 rounded-full border border-primary/40 bg-primary/10" />
                      <div className="relative">
                        <div className="absolute inset-x-[-35px] bottom-[-26px] h-10 rounded-full bg-violet-500/20 blur-xl" />
                        <div className="relative flex h-36 w-36 items-end justify-center rounded-[2.5rem] border border-white/10 bg-gradient-to-br from-violet-500/25 via-indigo-500/15 to-cyan-500/10 shadow-[0_0_60px_rgba(124,58,237,0.25)]">
                          <Crown className="mb-8 h-20 w-20 text-violet-300 drop-shadow-[0_0_12px_rgba(168,85,247,0.85)]" />
                        </div>
                      </div>
                    </div>
                    <div className="absolute bottom-6 left-6 right-6 flex items-center justify-between text-xs text-muted-foreground">
                      <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-black/20 px-3 py-1">
                        <CircleCheck className="h-3.5 w-3.5 text-emerald-400" />
                        {planTone.label}
                      </span>
                      <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-black/20 px-3 py-1">
                        <Landmark className="h-3.5 w-3.5 text-cyan-400" />
                        CEASER Subscription
                      </span>
                    </div>
                  </div>
                </div>
              </GlowCard>

              <div className="grid gap-4 lg:grid-cols-2">
                <GlowCard>
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <h3 className="text-lg font-semibold">Your Usage</h3>
                      <p className="text-sm text-muted-foreground">Resets with your billing cycle.</p>
                    </div>
                    <span className="text-sm text-muted-foreground">
                      {usageItems.length ? `Renews on ${renewalDate}` : "Usage will appear after the first tracked action."}
                    </span>
                  </div>
                  {usageItems.length ? (
                    <div className="mt-5 grid gap-3 md:grid-cols-2">
                      {usageItems.slice(0, 4).map((item, index) => (
                        <UsageTile key={item.entitlement_key} item={item} tone={planTone.colors[index % planTone.colors.length]} />
                      ))}
                    </div>
                  ) : (
                    <p className="mt-5 rounded-2xl border border-dashed border-border p-4 text-sm text-muted-foreground">
                      Usage counters will appear after the first tracked CEASER action.
                    </p>
                  )}
                  <div className="mt-5 flex justify-center">
                    <button className="inline-flex items-center gap-2 rounded-2xl border border-border px-4 py-2 text-sm font-semibold transition hover:bg-secondary">
                      <Activity className="h-4 w-4" />
                      View all usage details
                    </button>
                  </div>
                </GlowCard>

                <GlowCard>
                  <div className="flex h-full flex-col justify-between gap-5">
                    <div>
                      <h3 className="text-lg font-semibold">Student Pro Access</h3>
                      <p className="mt-1 text-sm text-muted-foreground">
                        Student verification now appears only when someone selects Student Pro, so the main billing page stays focused.
                      </p>
                    </div>
                    <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 p-4">
                      <div className="flex items-start gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-emerald-500/15 text-emerald-300">
                          <GraduationCap className="h-5 w-5" />
                        </div>
                        <div>
                          <p className="font-semibold">{studentVerified ? "Student access approved" : "Student access available at checkout"}</p>
                          <p className="text-sm text-muted-foreground">
                            {studentVerified
                              ? "Your student verification is active. Student Pro can go straight to Razorpay."
                              : "Choose Student Pro and we’ll collect your institutional email or document in a popup before payment."}
                          </p>
                        </div>
                      </div>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <MetricCard label="Status" value={studentVerification?.status ? humanizeEntitlement(studentVerification.status) : studentVerified ? "Approved" : "Not started"} />
                      <MetricCard label="Institution" value={studentVerification?.institutional_email || "Verify during checkout"} />
                    </div>
                  </div>
                </GlowCard>
              </div>

              <div ref={plansSectionRef}>
              <GlowCard>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h3 className="text-lg font-semibold">Choose the plan that&apos;s right for you</h3>
                    <p className="text-sm text-muted-foreground">Compare CEASER plans and switch when your workflow changes.</p>
                  </div>
                  <div className="inline-flex rounded-full border border-border bg-secondary/40 p-1 text-sm">
                    <button
                      onClick={() => setBillingIntervalView("monthly")}
                      className={cn(
                        "rounded-full px-4 py-1.5 font-semibold transition",
                        billingIntervalView === "monthly" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground",
                      )}
                    >
                      Monthly
                    </button>
                    <button
                      onClick={() => setBillingIntervalView("annual")}
                      className={cn(
                        "rounded-full px-4 py-1.5 font-semibold transition",
                        billingIntervalView === "annual" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground",
                      )}
                    >
                      Yearly
                    </button>
                    <span className="px-4 py-1.5 text-emerald-400">Save 20%</span>
                  </div>
                </div>

                <div className="mt-6 grid gap-4 xl:grid-cols-3">
                  {displayedPlans.map((plan, index) => {
                    const active = plan.code === currentPlan?.code
                    const colors = planToneByIndex(index)
                    const price = formatPrice(billingIntervalView === "annual" ? plan.annual_price : plan.monthly_price, plan.currency)
                    const lockedForStudentVerification = plan.code === "STUDENT_PRO" && !studentVerified
                    const disabled =
                      (plan.code === "FREE" && active) ||
                      commercialBusy === `${plan.code}-${billingIntervalView}`
                    const ctaLabel = active
                      ? "Current Plan"
                      : lockedForStudentVerification
                        ? "Verify Student Access"
                        : plan.code === "FREE"
                          ? "Select Free"
                          : "Upgrade Now"
                    return (
                      <div
                        key={plan.code}
                        className={cn(
                          "relative overflow-hidden rounded-[1.75rem] border p-5 transition",
                          active ? "border-primary/70 bg-primary/10 shadow-[0_0_0_1px_rgba(99,102,241,0.2)]" : "border-border bg-background/40 hover:border-primary/40",
                        )}
                      >
                        <div className={cn("absolute inset-x-0 top-0 h-1.5", colors.bar)} />
                        {active && (
                          <div className="absolute right-4 top-4 rounded-full bg-primary/20 px-3 py-1 text-xs font-semibold text-primary">
                            Most Popular
                          </div>
                        )}
                        <div className="flex h-full flex-col">
                          <div>
                            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-primary">{plan.code}</p>
                            <h3 className="mt-2 text-2xl font-bold">{plan.name}</h3>
                            <p className="mt-1 text-sm text-muted-foreground">{plan.description}</p>
                            <div className="mt-4 flex items-end gap-2">
                              <p className="text-3xl font-bold">{price}</p>
                              <span className="pb-1 text-sm text-muted-foreground">/ {billingIntervalView === "annual" ? "year" : "month"}</span>
                            </div>
                          </div>
                          <ul className="mt-5 space-y-2 text-sm text-muted-foreground">
                            {getPlanPerks(plan.code).map((perk) => (
                              <li key={perk} className="flex items-center gap-2">
                                <CircleCheck className={cn("h-4 w-4", colors.text)} />
                                <span>{perk}</span>
                              </li>
                            ))}
                          </ul>
                          <button
                            onClick={() =>
                              void (
                                plan.code === "FREE"
                                  ? handleSelectFreePlan()
                                  : lockedForStudentVerification
                                    ? openStudentCheckout(plan)
                                    : runTestUpgrade(plan.code, billingIntervalView)
                              )
                            }
                            disabled={disabled}
                            className={cn(
                              "mt-6 inline-flex items-center justify-center gap-2 rounded-2xl border px-4 py-3 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-45",
                              active
                                ? "border-border bg-background/60 text-foreground hover:bg-background/80"
                                : "border-transparent bg-primary text-primary-foreground hover:bg-primary/90",
                            )}
                          >
                            {ctaLabel}
                          </button>
                          {lockedForStudentVerification ? (
                            <p className="mt-2 text-xs text-amber-300">Student verification is required before checkout.</p>
                          ) : null}
                        </div>
                      </div>
                    )
                  })}
                </div>
                {!displayedPlans.length ? (
                  <div className="mt-6 rounded-2xl border border-dashed border-border p-5 text-sm text-muted-foreground">
                    Plans are being prepared. Refresh once if they do not appear.
                  </div>
                ) : null}
              </GlowCard>
              </div>

              <div ref={invoicesSectionRef}>
              <GlowCard>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h3 className="text-lg font-semibold">Payment History</h3>
                    <p className="text-sm text-muted-foreground">Recent billing activity for your CEASER account.</p>
                  </div>
                  <button
                    onClick={() => invoicesSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })}
                    className="inline-flex items-center gap-2 text-sm font-semibold text-primary hover:underline"
                  >
                    View all invoices
                    <ArrowRight className="h-4 w-4" />
                  </button>
                </div>
                <div className="mt-5 space-y-3">
                  {paymentRows.length ? (
                    paymentRows.map((row, index) => {
                      const invoice = billingOverview?.invoices?.[index]
                      const invoiceActionLabel = invoice?.hosted_url
                        ? "Open Invoice"
                        : row.status === "captured" || row.status === "paid"
                          ? "Payment Recorded"
                          : "Invoice Pending"
                      return (
                      <div key={row.id} className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-border bg-background/50 px-4 py-4">
                        <div className="flex items-center gap-3">
                          <div className="flex h-11 w-11 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-300">
                            <CircleCheck className="h-5 w-5" />
                          </div>
                          <div>
                            <p className="font-semibold">{row.date}</p>
                            <p className="text-sm text-muted-foreground">{row.reference}</p>
                          </div>
                        </div>
                        <div className="min-w-[180px] text-left sm:text-right">
                          <p className="font-semibold">{row.amount}</p>
                          <p className="text-sm text-muted-foreground">{row.plan}</p>
                        </div>
                        <div className="flex items-center gap-3">
                          <StatusBadge label={row.status} />
                          <button
                            onClick={() => invoice && handleInvoiceOpen(invoice)}
                            disabled={!invoice?.hosted_url}
                            className="inline-flex items-center gap-2 rounded-2xl border border-border px-4 py-2 text-sm font-semibold transition hover:bg-secondary disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            <Download className="h-4 w-4" />
                            {invoiceActionLabel}
                          </button>
                        </div>
                      </div>
                    )})
                  ) : (
                    <div className="rounded-2xl border border-dashed border-border p-5 text-sm text-muted-foreground">
                      Payment history will appear after your first verified subscription payment.
                    </div>
                  )}
                </div>
              </GlowCard>
              </div>

              {studentModalOpen ? (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4 backdrop-blur-sm" onClick={() => setStudentModalOpen(false)}>
                  <div className="w-full max-w-2xl rounded-[2rem] border border-border bg-card p-6 shadow-2xl" onClick={(event) => event.stopPropagation()}>
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <h3 className="text-2xl font-bold">Unlock Student Pro</h3>
                        <p className="mt-1 text-sm text-muted-foreground">
                          Verify your student access once, then we&apos;ll continue directly into Razorpay for {studentCheckoutPlan?.name || "Student Pro"}.
                        </p>
                      </div>
                      <button onClick={() => setStudentModalOpen(false)} className="rounded-xl border border-border px-3 py-2 text-sm transition hover:bg-secondary">
                        Close
                      </button>
                    </div>

                    <div className="mt-6 grid gap-6 lg:grid-cols-2">
                      <div className="space-y-4 rounded-3xl border border-border bg-background/40 p-5">
                        <div>
                          <h4 className="text-lg font-semibold">Verify with institutional email</h4>
                          <p className="text-sm text-muted-foreground">Fastest path for approved NHCE student accounts.</p>
                        </div>
                        <input
                          type="email"
                          value={studentEmail}
                          onChange={(event) => setStudentEmail(event.target.value)}
                          placeholder="student@newhorizonindia.edu"
                          className="w-full rounded-2xl border border-border bg-background px-4 py-3 outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
                        />
                        <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
                          <input
                            type="text"
                            value={studentOtp}
                            onChange={(event) => setStudentOtp(event.target.value)}
                            placeholder="Enter 6-digit code"
                            className="w-full rounded-2xl border border-border bg-background px-4 py-3 outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
                          />
                          <button
                            onClick={() => void confirmStudentVerification()}
                            disabled={commercialBusy === "student-confirm"}
                            className="rounded-2xl border border-border px-4 py-3 text-sm font-semibold transition hover:bg-secondary disabled:opacity-50"
                          >
                            Confirm
                          </button>
                        </div>
                        <button
                          onClick={() => void startStudentVerification()}
                          disabled={commercialBusy === "student-email"}
                          className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:opacity-50"
                        >
                          <Sparkles className="h-4 w-4" />
                          Send Verification Code
                        </button>
                      </div>

                      <div className="space-y-4 rounded-3xl border border-border bg-background/40 p-5">
                        <div>
                          <h4 className="text-lg font-semibold">Upload student document</h4>
                          <p className="text-sm text-muted-foreground">Upload your ID card or proof document to unlock Student Pro immediately.</p>
                        </div>
                        <input
                          type="file"
                          accept=".pdf,.png,.jpg,.jpeg,.webp"
                          onChange={(event) => setStudentDocumentFile(event.target.files?.[0] || null)}
                          className="block w-full text-sm text-muted-foreground file:mr-4 file:rounded-xl file:border-0 file:bg-primary/15 file:px-4 file:py-2 file:font-semibold file:text-primary"
                        />
                        <button
                          onClick={() => void submitStudentDocument()}
                          disabled={commercialBusy === "student-document"}
                          className="inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-border px-4 py-3 text-sm font-semibold transition hover:bg-secondary disabled:opacity-50"
                        >
                          <Upload className="h-4 w-4" />
                          Upload and Continue
                        </button>
                        <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 p-4 text-sm text-muted-foreground">
                          Current status: <span className="font-semibold text-foreground">{studentVerification?.status ? humanizeEntitlement(studentVerification.status) : "Not started"}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ) : null}

              {checkoutModalOpen ? (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/85 p-4 backdrop-blur-sm">
                  <div className="w-full max-w-md rounded-[2rem] border border-primary/20 bg-card p-6 shadow-2xl">
                    <div className="flex items-start gap-4">
                      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/15 text-primary">
                        <CreditCard className="h-6 w-6" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <h3 className="text-xl font-bold">Opening secure checkout</h3>
                        <p className="mt-2 text-sm text-muted-foreground">
                          We&apos;re preparing Razorpay for your CEASER upgrade. This usually takes a moment.
                        </p>
                      </div>
                    </div>
                    <div className="mt-6 flex items-center gap-3 rounded-2xl border border-border bg-background/50 px-4 py-3">
                      <Loader2 className="h-5 w-5 animate-spin text-primary" />
                      <div className="text-sm text-muted-foreground">
                        Connecting to the payment gateway securely...
                      </div>
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          )
        })()}

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
                <button onClick={() => setPasswordModalOpen(true)} className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90">Update Password</button>
                <div className="border-t border-border pt-4">
                  <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                      <Smartphone className="h-5 w-5 text-muted-foreground" />
                      <div>
                        <p className="font-medium">Two-Factor Authentication</p>
                        <p className="text-sm text-muted-foreground">Use an authenticator app with a 6-digit code</p>
                      </div>
                    </div>
                    <button onClick={() => setMfaModalOpen(true)} className="rounded-lg border border-border px-4 py-2 text-sm transition-colors hover:bg-secondary">
                      {mfaEnabled ? "Manage 2FA" : "Enable 2FA"}
                    </button>
                  </div>
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
                <div className="rounded-xl border border-border bg-background/50 p-4">
                  <div className="mb-4 flex items-center justify-between gap-4">
                    <div>
                      <p className="text-sm font-medium">Connected desktop devices</p>
                      <p className="text-xs text-muted-foreground">Revoke a desktop companion if a device is lost, shared, or no longer trusted.</p>
                    </div>
                    <button onClick={() => void loadDesktopDevices()} disabled={desktopDevicesBusy} className="rounded-lg border border-border px-3 py-2 text-xs font-medium hover:bg-secondary disabled:opacity-50">
                      {desktopDevicesBusy ? "Loading..." : "Refresh"}
                    </button>
                  </div>
                  <div className="space-y-3">
                    {desktopDevices.length ? desktopDevices.map((device) => (
                      <div key={device.device_id} className="flex items-center justify-between gap-3 rounded-lg border border-border/70 bg-card/60 p-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold">{device.device_name}</p>
                          <p className="text-xs text-muted-foreground">
                            {device.platform || "desktop"} {device.app_version ? `- v${device.app_version}` : ""} · Last active {formatDeviceDate(device.last_seen_at)}
                          </p>
                          <p className={cn("mt-1 text-xs font-medium", device.revoked_at ? "text-red-400" : "text-emerald-400")}>{device.revoked_at ? "Revoked" : "Connected"}</p>
                        </div>
                        {!device.revoked_at && (
                          <button onClick={() => void revokeDesktopDevice(device.device_id)} disabled={desktopDevicesBusy} className="shrink-0 rounded-lg border border-red-500/30 px-3 py-2 text-xs font-semibold text-red-300 hover:bg-red-500/10 disabled:opacity-50">
                            Revoke
                          </button>
                        )}
                      </div>
                    )) : (
                      <p className="rounded-lg border border-dashed border-border px-3 py-4 text-sm text-muted-foreground">
                        {desktopDevicesBusy ? "Loading desktop devices..." : "No connected desktop companion devices yet."}
                      </p>
                    )}
                  </div>
                  {desktopDevicesMessage && <p className="mt-3 text-xs text-muted-foreground">{desktopDevicesMessage}</p>}
                </div>
              </div>
            </GlowCard>
          </div>
        )}

        {passwordModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4 backdrop-blur-sm" onClick={() => setPasswordModalOpen(false)}>
            <div className="w-full max-w-lg rounded-2xl border border-border bg-card p-6 shadow-2xl" onClick={(event) => event.stopPropagation()}>
              <div className="mb-5 flex items-start justify-between gap-4"><div><h3 className="text-xl font-semibold">Change Password</h3><p className="mt-1 text-sm text-muted-foreground">Confirm your current password, then choose a strong new one.</p></div><button onClick={() => setPasswordModalOpen(false)} className="text-muted-foreground hover:text-foreground">Close</button></div>
              <div className="space-y-4">
                <PasswordField id="modal-current-password" label="Current Password" value={currentPassword} onChange={setCurrentPassword} placeholder="Enter your current password" autoComplete="current-password" />
                <div><PasswordField id="modal-new-password" label="New Password" value={newPassword} onChange={setNewPassword} placeholder="Enter your new password" autoComplete="new-password" /><PasswordRequirements password={newPassword} /></div>
                <PasswordField id="modal-confirm-password" label="Confirm New Password" value={confirmNewPassword} onChange={setConfirmNewPassword} placeholder="Re-enter your new password" autoComplete="new-password" />
                {securityMessage && <p className="text-sm text-muted-foreground">{securityMessage}</p>}
                <button onClick={() => void updatePassword()} disabled={securityBusy === "password"} className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50">{securityBusy === "password" ? "Updating..." : "Update Password"}</button>
              </div>
            </div>
          </div>
        )}

        {mfaModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4 backdrop-blur-sm" onClick={() => setMfaModalOpen(false)}>
            <div className="w-full max-w-lg rounded-2xl border border-border bg-card p-6 shadow-2xl" onClick={(event) => event.stopPropagation()}>
              <div className="mb-5 flex items-start justify-between"><div><h3 className="text-xl font-semibold">Two-Factor Authentication</h3><p className="mt-1 text-sm text-muted-foreground">Add an extra layer of security to your CEASER account.</p></div><button onClick={() => setMfaModalOpen(false)} className="text-muted-foreground hover:text-foreground">Close</button></div>
              {mfaEnabled ? <div className="space-y-4"><p className="rounded-xl bg-emerald-500/10 px-4 py-3 text-sm text-emerald-400">2FA Enabled ✓ Your CEASER account is protected with two-factor authentication.</p><button className="rounded-lg border border-border px-4 py-2 text-sm">Manage 2FA</button><button className="ml-2 rounded-lg border border-red-500/30 px-4 py-2 text-sm text-red-400">Disable 2FA</button></div> : !mfaEnrollment ? <div className="space-y-4"><p className="text-sm">Status: <span className="text-muted-foreground">○ Not enabled</span></p><div><label className="mb-2 block text-sm font-medium">Step 1 — Verify password</label><input type="password" value={mfaSetupPassword} onChange={(event) => setMfaSetupPassword(event.target.value)} placeholder="Enter your CEASER password" className="h-10 w-full rounded-lg border border-border bg-background px-3 text-sm" /></div><button onClick={() => void startMfaEnrollment()} disabled={securityBusy === "mfa"} className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50">{securityBusy === "mfa" ? "Verifying..." : "Enable 2FA"}</button></div> : <div className="space-y-4"><div><p className="font-medium">Step 2 — Choose authenticator</p><p className="text-sm text-muted-foreground">Scan the QR code using your authenticator app.</p></div>{getMfaQr(mfaEnrollment) ? <img src={getMfaQr(mfaEnrollment)} alt="Authenticator QR code" className="h-44 w-44 rounded-xl bg-white p-2" /> : null}<p className="text-sm text-muted-foreground">Can&apos;t scan? Use setup key: <span className="font-mono text-foreground">{getMfaSecret(mfaEnrollment)}</span></p><div><label className="mb-2 block text-sm font-medium">Step 3 — Verify</label><input value={mfaCode} onChange={(event) => setMfaCode(event.target.value.replace(/\D/g, "").slice(0, 6))} inputMode="numeric" placeholder="_ _ _ _ _ _" className="h-12 w-full rounded-lg border border-border bg-background px-3 text-center font-mono text-lg tracking-[0.45em]" /></div><button onClick={() => void verifyMfaEnrollment()} disabled={securityBusy === "mfa-verify" || mfaCode.length !== 6} className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50">{securityBusy === "mfa-verify" ? "Verifying..." : "Verify & Enable"}</button></div>}
            </div>
          </div>
        )}

        {activeSection === "preferences" && (
          <div className="max-w-2xl space-y-6">
            <h2 className="text-2xl font-bold">Preferences</h2>
            
            <GlowCard>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Moon className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium">Appearance</p>
                      <p className="text-sm text-muted-foreground">CEASER runs in dark mode</p>
                    </div>
                  </div>
                </div>
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
            <GlowCard>
              <div className="space-y-4">
                <div>
                  <p className="font-medium">Companion conversation</p>
                  <p className="text-sm text-muted-foreground">Control CEASER&apos;s tone, initiative, and language without changing execution behavior.</p>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <PreferenceSelect label="Conversation style" value={preferences.conversation_style} options={["balanced", "casual", "professional"]} onChange={(value) => savePreferences({ conversation_style: value as CompanionPreferences["conversation_style"] })} />
                  <PreferenceSelect label="Humor" value={preferences.humor} options={["off", "low", "medium", "high"]} onChange={(value) => savePreferences({ humor: value as CompanionPreferences["humor"] })} />
                  <PreferenceSelect label="Light roasting" value={preferences.roasting} options={["off", "light", "medium"]} onChange={(value) => savePreferences({ roasting: value as CompanionPreferences["roasting"] })} />
                  <PreferenceSelect label="Proactive CEASER" value={preferences.proactive_mode} options={["off", "important_only", "balanced", "companion"]} onChange={(value) => savePreferences({ proactive_mode: value as CompanionPreferences["proactive_mode"] })} />
                  <PreferenceSelect label="Language" value={preferences.language} options={["auto", "English", "Telugu", "Kannada", "Hindi", "Tamil", "Malayalam"]} onChange={(value) => savePreferences({ language: value as CompanionPreferences["language"] })} />
                  <div className="flex items-center justify-between rounded-xl border border-border bg-background/50 p-3">
                    <div><p className="text-sm font-medium">Code switching</p><p className="text-xs text-muted-foreground">Mix English technical terms naturally</p></div>
                    <SettingSwitch checked={preferences.code_switching} onChange={(checked) => savePreferences({ code_switching: checked })} />
                  </div>
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

function UsageTile({ item, tone }: { item: { entitlement_key: string; limit_value: number; used_quantity: number; remaining: number; reset_period: string }, tone: { bar: string; text: string } }) {
  const percentage = Math.min(100, Math.round((item.used_quantity / Math.max(1, item.limit_value)) * 100))
  const isCapacityMetric = item.reset_period === "never" && item.used_quantity === 0
  const usageLabel = isCapacityMetric ? `${item.limit_value} available` : `${item.used_quantity}/${item.limit_value}`
  const helperLabel = isCapacityMetric ? "Included with your current plan" : `${item.remaining} remaining - resets ${item.reset_period}`
  return (
    <div className="rounded-2xl border border-border bg-background/50 p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="font-medium">{humanizeEntitlement(item.entitlement_key)}</p>
        <span className="text-sm text-muted-foreground">{usageLabel}</span>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-secondary">
        <div className={cn("h-full rounded-full", tone.bar)} style={{ width: `${percentage}%` }} />
      </div>
      <p className="mt-2 text-xs text-muted-foreground">{helperLabel}</p>
    </div>
  )
}

function getPlanTone(code: string) {
  if (code === "FREE") return { label: "Starter access", colors: [{ bar: "bg-slate-500", text: "text-slate-300" }] }
  if (code === "STUDENT_PRO") return { label: "Student pricing", colors: [{ bar: "bg-emerald-500", text: "text-emerald-300" }, { bar: "bg-cyan-500", text: "text-cyan-300" }] }
  if (code === "TEAM") return { label: "Team workspace", colors: [{ bar: "bg-orange-500", text: "text-orange-300" }, { bar: "bg-violet-500", text: "text-violet-300" }] }
  return { label: "Pro access", colors: [{ bar: "bg-primary", text: "text-primary" }, { bar: "bg-cyan-500", text: "text-cyan-300" }] }
}

function planToneByIndex(index: number) {
  const palette = [
    { bar: "bg-cyan-500", text: "text-cyan-300" },
    { bar: "bg-emerald-500", text: "text-emerald-300" },
    { bar: "bg-primary", text: "text-primary" },
    { bar: "bg-orange-500", text: "text-orange-300" },
  ]
  return palette[index % palette.length]
}

function getPlanPerks(code: string) {
  if (code === "FREE") return ["Basic AI chat", "Limited projects", "Standard models", "Community support"]
  if (code === "STUDENT_PRO") return ["Unlimited AI messages", "AI models", "Desktop companion", "Academic tools", "Priority support"]
  if (code === "TEAM") return ["Everything in Pro", "Team workspace", "Admin controls", "Usage analytics", "Dedicated support"]
  return ["Unlimited AI messages", "AI models", "Desktop companion", "Advanced tools", "Priority support"]
}

function getInvoiceRows(subscription: CommercialSubscription | null | undefined, plan: CommercialPlan | undefined) {
  const label = plan?.name || "CEASER Pro Monthly"
  const amount = plan ? `${formatPrice(plan.monthly_price, plan.currency)}` : "₹399"
  return [
    { id: "inv-1", date: formatLongDate(subscription?.current_period_end || new Date().toISOString()), reference: `Order #${subscription?.id || "order_0U8H6k2"}`, amount, plan: label, status: "paid" },
    { id: "inv-2", date: "28 Jun 2026", reference: "Order #order_N7G5jK1", amount, plan: label, status: "paid" },
    { id: "inv-3", date: "28 May 2026", reference: "Order #J2H4kL9", amount, plan: label, status: "paid" },
  ]
}

function formatLongDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" }).format(date)
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

function CapabilitySummary({ devices }: { devices: DesktopDevice[] }) {
  const active = devices.filter((device) => device.status !== "revoked")
  const capabilities = new Set(active.flatMap((device) => device.capabilities || []))
  const groups = [
    ["Apps", ["app.", "desktop.open_application"]], ["Windows", ["window."]], ["Network", ["network.", "wifi.", "bluetooth.", "vpn."]],
    ["Audio", ["audio.", "media."]], ["Display", ["display.", "monitor.", "screen."]], ["Files", ["file.", "directory.", "storage."]],
    ["Browser", ["browser."]], ["Development", ["project.", "git.", "development."]], ["Peripherals", ["printer.", "recycle."]],
  ] as const
  return <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{groups.map(([label, prefixes]) => {
    const count = [...capabilities].filter((id) => prefixes.some((prefix) => id.startsWith(prefix))).length
    const status = !active.length ? "Unsupported" : count ? "Available" : "Limited"
    return <div key={label} className="flex items-center justify-between rounded-lg border border-border bg-background/50 px-3 py-2"><span className="text-sm font-medium">{label}</span><span className={cn("text-xs", status === "Available" ? "text-emerald-400" : status === "Limited" ? "text-amber-400" : "text-muted-foreground")}>{status}{count ? ` (${count})` : ""}</span></div>
  })}</div>
}

function PreferenceSelect({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (value: string) => void }) {
  return <label className="block rounded-xl border border-border bg-background/50 p-3"><span className="mb-2 block text-sm font-medium">{label}</span><select value={value} onChange={(event) => onChange(event.target.value)} className="h-10 w-full rounded-lg border border-border bg-card px-3 text-sm outline-none focus:border-primary">{options.map((option) => <option key={option} value={option}>{option.replaceAll("_", " ")}</option>)}</select></label>
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

function PasswordField({ id, label, value, onChange, placeholder, autoComplete }: { id: string; label: string; value: string; onChange: (value: string) => void; placeholder: string; autoComplete: string }) {
  const [visible, setVisible] = useState(false)
  return <div><label htmlFor={id} className="mb-2 block text-sm font-medium">{label}</label><div className="relative"><input id={id} type={visible ? "text" : "password"} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} autoComplete={autoComplete} className="h-10 w-full rounded-lg border border-border bg-background px-3 pr-10 text-sm outline-none focus:border-primary" /><button type="button" onClick={() => setVisible((current) => !current)} aria-label={visible ? "Hide password" : "Show password"} className="absolute inset-y-0 right-0 px-3 text-muted-foreground hover:text-foreground">{visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button></div></div>
}

function PasswordRequirements({ password }: { password: string }) {
  return <div className="mt-2 grid gap-1 text-xs text-muted-foreground sm:grid-cols-2">{[["At least 8 characters", password.length >= 8], ["One uppercase letter", /[A-Z]/.test(password)], ["One lowercase letter", /[a-z]/.test(password)], ["One number", /\d/.test(password)], ["One special character", /[^A-Za-z0-9]/.test(password)]].map(([label, met]) => <span key={label as string} className={cn("flex items-center gap-1.5", met ? "text-emerald-500" : "text-muted-foreground")}><CircleCheck className="h-3.5 w-3.5" />{label as string}</span>)}</div>
}

function getMfaQr(enrollment: Record<string, unknown>) {
  const totp = enrollment.totp as Record<string, unknown> | undefined
  return String(totp?.qr_code || totp?.qrCode || "")
}

function getMfaSecret(enrollment: Record<string, unknown>) {
  const totp = enrollment.totp as Record<string, unknown> | undefined
  return String(totp?.secret || "")
}

function formatDeviceDate(value?: string | null) {
  if (!value) return "not seen yet"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "recently"
  return date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })
}




