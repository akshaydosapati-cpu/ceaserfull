const appShell = document.getElementById("app")
const compactTitle = document.getElementById("compactTitle")
const compactSubtitle = document.getElementById("compactSubtitle")
const compactProgressBar = document.getElementById("compactProgressBar")
const stateEyebrow = document.getElementById("stateEyebrow")
const stateTitle = document.getElementById("stateTitle")
const stateSubtitle = document.getElementById("stateSubtitle")
const progressBar = document.getElementById("progressBar")
const commandForm = document.getElementById("commandForm")
const commandInput = document.getElementById("commandInput")
const activeAgent = document.getElementById("activeAgent")
const intentType = document.getElementById("intentType")
const stepsList = document.getElementById("stepsList")
const progressPercent = document.getElementById("progressPercent")
const confirmationCard = document.getElementById("confirmationCard")
const confirmationText = document.getElementById("confirmationText")
const resultTitle = document.getElementById("resultTitle")
const resultSummary = document.getElementById("resultSummary")
const resultStats = document.getElementById("resultStats")
const currentApp = document.getElementById("currentApp")
const recentFile = document.getElementById("recentFile")
const sessionSummary = document.getElementById("sessionSummary")
const contextStatus = document.getElementById("contextStatus")
const dynamicPanel = document.getElementById("dynamicPanel")
const promptBubble = document.getElementById("promptBubble")
const diagnosticsPanel = document.getElementById("diagnosticsPanel")
const diagnosticsLog = document.getElementById("diagnosticsLog")
const diagnosticsSummary = document.getElementById("diagnosticsSummary")
const diagnosticsStatus = document.getElementById("diagnosticsStatus")
const accountButton = document.getElementById("accountButton")
const surfaceStateLabel = document.getElementById("surfaceStateLabel")
const guidePanel = document.getElementById("guidePanel")
const guideProgressBar = document.getElementById("guideProgressBar")
const guideStepLabel = document.getElementById("guideStepLabel")
const guideIcon = document.getElementById("guideIcon")
const guideTitle = document.getElementById("guideTitle")
const guideDescription = document.getElementById("guideDescription")
const guideExamples = document.getElementById("guideExamples")
const guideBackButton = document.getElementById("guideBackButton")
const guideNextButton = document.getElementById("guideNextButton")
const inactivityPromptCard = document.getElementById("inactivityPromptCard")
const inactivityPromptText = document.getElementById("inactivityPromptText")
const inactivityContinueButton = document.getElementById("inactivityContinueButton")
const inactivitySilentButton = document.getElementById("inactivitySilentButton")

let pendingIntent = null
let activeMode = "compact"
let fitTimer = null
let lastFit = { width: 0, height: 0 }
let recorder = null
let chunks = []
let mediaStream = null
let audioContext = null
let silenceFrame = null
let autoStopTimer = null
let hideTimer = null
let retractTimer = null
let listeningActive = false
let speakingActive = false
let speechGeneration = 0
let currentSpeechOnEnd = null
let currentProviderAudio = null
let mediaDuckedForListening = false
let mediaPlaybackExpected = window.localStorage.getItem("ceaser_media_playback_expected") === "true"
let linkedUser = null
let personalizedGreetingPlayed = false
let activeTask = null
let taskCounter = 0
let lastCommand = ""
let assistantSessionActive = false
let passiveListening = false
let restartListenTimer = null
let holdVoiceActive = false
let holdVoiceContext = null
let holdVoiceSessionId = null
let holdVoiceStartedAt = 0
let pendingHoldStop = false
let stoppingVoice = false
let voiceSession = null
let lastResultContext = loadLastResultContext()
let alwaysListenActive = false
const WAKE_WORD_LISTENING_ENABLED = false
let passiveWakeLoopRunning = false
let passiveWakeLoopOwner = null
let voiceCommandGeneration = 0
let smartCaptureActive = false
let holdSpeechRecognition = null
let holdSpeechTranscript = ""
let holdSpeechStopping = false
let selectedDesktopFileContext = null
let overlayInteractive = false
let diagnosticsOpen = false
const diagnosticsEntries = []
const DESKTOP_GUIDE_KEY = "ceaser_desktop_guide_v1_complete"
const DESKTOP_GUIDE_STEPS = [
  {
    icon: "01",
    title: "Welcome to CEASER",
    description: "Connect your CEASER account once to use AI, projects, memory, files, and integrations from your desktop.",
    examples: ["Select Connect in the header", "Complete sign-in in the web console", "Return here automatically"],
  },
  {
    icon: "02",
    title: "Speak naturally",
    description: "Press Ctrl + Shift + Space to start listening, then say the complete command in your own words.",
    examples: ["Open Chrome", "Set volume to 50 percent", "Explain quantum computing simply"],
  },
  {
    icon: "03",
    title: "Type or bring a file",
    description: "Type in the command bar, attach a file with +, or drag a supported file directly onto CEASER for contextual help.",
    examples: ["Summarize this PDF", "Create notes from this document", "What is shown in this image?"],
  },
  {
    icon: "04",
    title: "Keep the conversation going",
    description: "After a response, ask a short follow-up. CEASER keeps the active topic and can continue working with it.",
    examples: ["Summarize", "Make it shorter", "Tell me more", "Say goodbye when you are done"],
  },
]
let guideStepIndex = 0
const INACTIVITY_TIMEOUT_MS = 300000
const ACTIVITY_THROTTLE_MS = 1200
let inactivityTimer = null
let inactivityPromptVisible = false
let overlayVisible = true
let silentBackgroundActive = false
let lastActivityPulseAt = 0
let preSilentInteractionState = null

function renderGuideStep() {
  const step = DESKTOP_GUIDE_STEPS[guideStepIndex]
  if (!step || !guidePanel) return
  guideStepLabel.textContent = `Step ${guideStepIndex + 1} of ${DESKTOP_GUIDE_STEPS.length}`
  guideIcon.textContent = step.icon
  guideTitle.textContent = step.title
  guideDescription.textContent = step.description
  guideExamples.innerHTML = step.examples.map((example) => `<span>${escapeHtml(example)}</span>`).join("")
  guideProgressBar.style.width = `${((guideStepIndex + 1) / DESKTOP_GUIDE_STEPS.length) * 100}%`
  guideBackButton.disabled = guideStepIndex === 0
  guideNextButton.textContent = guideStepIndex === DESKTOP_GUIDE_STEPS.length - 1 ? "Start using CEASER" : "Next"
  fitOverlay()
}

function showDesktopGuide({ firstRun = false } = {}) {
  if (!guidePanel) return
  guideStepIndex = 0
  guidePanel.dataset.firstRun = firstRun ? "true" : "false"
  guidePanel.classList.remove("hidden")
  setMode("expanded")
  renderGuideStep()
}

function closeDesktopGuide({ completed = false } = {}) {
  if (!guidePanel) return
  if (completed || guidePanel.dataset.firstRun === "true") {
    window.localStorage.setItem(DESKTOP_GUIDE_KEY, "true")
  }
  guidePanel.classList.add("hidden")
  fitOverlay()
  commandInput?.focus()
}

function maybeShowFirstRunGuide() {
  if (window.localStorage.getItem(DESKTOP_GUIDE_KEY) === "true") return
  window.setTimeout(() => showDesktopGuide({ firstRun: true }), 450)
}

function clearInactivityTimer() {
  if (inactivityTimer) {
    window.clearTimeout(inactivityTimer)
    inactivityTimer = null
  }
}

function hideInactivityPrompt() {
  inactivityPromptVisible = false
  inactivityPromptCard?.classList.add("hidden")
}

function updateActivitySurface() {
  if (silentBackgroundActive) {
    appShell.dataset.background = "silent"
    setState("silent_background", "Running silently", overlayVisible ? "CEASER is paused in the background." : "CEASER will resume when you open it.")
  } else {
    appShell.dataset.background = "active"
  }
}

function restoreFromSilentBackground(reason = "resume") {
  if (!silentBackgroundActive) return
  silentBackgroundActive = false
  preSilentInteractionState = null
  hideInactivityPrompt()
  showPrompt("")
  updateActivitySurface()
  if (overlayVisible) {
    setState("idle", "CEASER ready", "How can I help?")
    renderIdlePanel()
  }
  console.log('[CEASER] Silent background ended: ' + reason)
  scheduleInactivityTimer(reason)
}

function forceStopVoiceCommand() {
  if (!listeningActive && !recorder && !mediaStream && !audioContext) return
  stoppingVoice = true
  setVoiceButtonState(false)
  if (recorder?.state === "recording") recorder.stop()
  else cleanupRecording()
}

function stopVoiceForSilentMode() {
  stopCurrentSpeech("silent-background")
  if (holdSpeechRecognition) stopHoldSpeechCommand()
  if (listeningActive) forceStopVoiceCommand()
  if (alwaysListenActive || assistantSessionActive || passiveWakeLoopRunning) {
    voiceCommandGeneration += 1
    alwaysListenActive = false
    assistantSessionActive = false
    passiveWakeLoopRunning = false
    passiveWakeLoopOwner = null
    window.clearTimeout(restartListenTimer)
    restartListenTimer = null
  }
  setVoiceButtonState(false)
  restoreMediaAfterListening("silent-mode")
}

function enterSilentBackground(reason = "timeout") {
  if (silentBackgroundActive) return
  clearInactivityTimer()
  hideInactivityPrompt()
  preSilentInteractionState = {
    activeMode,
    assistantSessionActive,
    alwaysListenActive,
  }
  silentBackgroundActive = true
  stopVoiceForSilentMode()
  updateActivitySurface()
  if (overlayVisible) {
    setState("silent_background", "Running silently", "CEASER will stay available in the tray.")
    showPrompt("CEASER is running silently in the background.")
    window.ceaserDesktop?.hideOverlay?.({ reason: 'silent_background_' + reason })
  }
  console.log('[CEASER] Silent background entered: ' + reason)
}

function showInactivityPrompt() {
  if (!overlayVisible || silentBackgroundActive) return
  inactivityPromptVisible = true
  clearInactivityTimer()
  setMode("expanded")
  updateActivitySurface()
  inactivityPromptCard?.classList.remove("hidden")
  if (inactivityPromptText) {
    inactivityPromptText.textContent = "You haven't interacted with CEASER for 5 minutes. Would you like CEASER to stay active or run silently in the background?"
  }
  setState("idle", "Still here?", "Choose how CEASER should behave.")
  fitOverlay()
}

function scheduleInactivityTimer(reason = "activity") {
  clearInactivityTimer()
  if (inactivityPromptVisible) return
  if (silentBackgroundActive && !overlayVisible) return
  inactivityTimer = window.setTimeout(() => handleInactivityTimeout(reason), INACTIVITY_TIMEOUT_MS)
}

function handleInactivityTimeout(reason = "timer") {
  if (silentBackgroundActive) return
  if (!overlayVisible) {
    enterSilentBackground(reason)
    return
  }
  showInactivityPrompt()
}

function markUserActivity(reason = "interaction", { force = false } = {}) {
  const now = Date.now()
  if (!force && reason === "pointermove" && now - lastActivityPulseAt < ACTIVITY_THROTTLE_MS) return
  lastActivityPulseAt = now
  if (inactivityPromptVisible) hideInactivityPrompt()
  if (silentBackgroundActive) restoreFromSilentBackground(reason)
  scheduleInactivityTimer(reason)
}

function bindInactivityActivityTracking() {
  const events = ["pointerdown", "keydown", "focusin", "submit", "dragstart", "drop", "wheel", "touchstart"]
  for (const eventName of events) {
    document.addEventListener(eventName, () => markUserActivity(eventName), true)
  }
  document.addEventListener("mousemove", () => markUserActivity("pointermove"), true)
}

bindInactivityActivityTracking()

function renderDiagnosticEntry(entry) {
  if (!diagnosticsLog || !entry) return
  diagnosticsEntries.push(entry)
  if (diagnosticsEntries.length > 250) diagnosticsEntries.splice(0, diagnosticsEntries.length - 250)
  diagnosticsLog.innerHTML = diagnosticsEntries.map((item) => {
    const level = String(item.level || "info").toLowerCase()
    const time = item.at ? new Date(item.at).toLocaleTimeString([], { hour12: false }) : "--:--:--"
    return `<div class="diagnostics-entry ${level}"><time>${escapeHtml(time)}</time><b>${escapeHtml(level)}</b><span>${escapeHtml(item.message || "")}</span></div>`
  }).join("")
  diagnosticsLog.scrollTop = diagnosticsLog.scrollHeight
}

async function showDiagnostics() {
  diagnosticsOpen = true
  diagnosticsPanel?.classList.remove("hidden")
  setMode("expanded")
  const snapshot = await window.ceaserDesktop?.getRuntimeLogs?.().catch(() => null)
  diagnosticsEntries.length = 0
  for (const entry of snapshot?.entries || []) renderDiagnosticEntry(entry)
  const python = snapshot?.python || {}
  const pythonState = python.ready ? { className: "ok", label: "Python ready" } : python.running ? { className: "pending", label: "Python starting" } : { className: "bad", label: "Python unavailable" }
  diagnosticsSummary.innerHTML = `<span class="${pythonState.className}">${pythonState.label}</span><span class="${python.running ? "ok" : "bad"}">Process ${python.running ? "running" : "stopped"}</span><span>Entries ${diagnosticsEntries.length}</span>`
  diagnosticsStatus.textContent = snapshot?.file ? "Recording safely to disk" : "Live session only"
  fitOverlay()
}

function hideDiagnostics() {
  diagnosticsOpen = false
  diagnosticsPanel?.classList.add("hidden")
  fitOverlay()
}

function setOverlayHitTesting(interactive) {
  const next = Boolean(interactive)
  if (overlayInteractive === next) return
  overlayInteractive = next
  window.ceaserDesktop?.setOverlayInteractive?.(next)
}

document.addEventListener("mousemove", (event) => {
  const target = event.target instanceof Element ? event.target : null
  setOverlayHitTesting(Boolean(target?.closest(".minimal-shell, .compact-shell, .expanded-shell")))
})
document.addEventListener("mouseleave", () => setOverlayHitTesting(false))

const WAKE_WORD_PATTERN = /\b(?:hey|hi|hello|ok|okay|a)\s+(?:ceaser|cesaer|caesar|cesar|seizer|sizer|sizzer|scissor|season|procedure|precision|c(?:\s|-)ser|see\s*sir|sea\s*sir|google|siri|alexa)\b|\b(?:ceaser|cesaer|caesar|cesar|seizer|sizer|sizzer|scissor|season|procedure|precision|see\s*sir|sea\s*sir|face\s+is\s+a|faces\s+a)\b/i
const EXIT_SESSION_PATTERN = /\b(?:bye|goodbye|exit ceaser|close ceaser|sleep ceaser|that's all|that is all|stop listening|go silent)\b/i
const REST_SESSION_PATTERN = /\b(?:take rest|rest now|turn off|shutdown voice|shut down voice|stop voice|goodbye|good bye|go silent|sleep ceaser|sleep caesar)\b/i
const ASSISTANT_INTENT_PATTERN = /\b(open|close|launch|start|search|find|play|pause|resume|next|previous|stop|summarize|research|create|generate|make|build|explain|translate|weather|news|calendar|meeting|event|task|todo|remind|timer|alarm|email|send|gmail|document|pdf|presentation|powerpoint|word|excel|settings|memory|project|agent|ceaser|who|when|where|why|how|who are you|what is|what's|tell me|show|check)\b/i
const EDITABLE_PROCESS_PATTERN = /\b(winword|notepad|code|cursor|chrome|msedge|firefox|brave|slack|discord|teams|whatsapp|notion|excel|outlook|electron)\b/i
const CONTEXT_REFERENCE_PATTERN = /\b(it|this|that|the draft|the email|the document|the result|the plan|the timetable|the report|the notes|same)\b/i

function usesPythonVoice() {
  return Boolean(window.ceaserDesktop?.pythonVoiceCommand)
}

const TRANSCRIPT_CORRECTIONS = [
  [/\bsuch a tender curve\b/gi, "Sachin Tendulkar"],
  [/\bsachin tendhulkar\b/gi, "Sachin Tendulkar"],
  [/\bsachin tendulkar\b/gi, "Sachin Tendulkar"],
  [/\btendhulkar\b/gi, "Tendulkar"],
  [/\bcaesar\b/gi, "CEASER"],
  [/\bcesar\b/gi, "CEASER"],
  [/\bseizer\b/gi, "CEASER"],
  [/\bsizer\b/gi, "CEASER"],
  [/\bscissor\b/gi, "CEASER"],
  [/\bclinic locker\b/gi, "Clinilocker"],
  [/\bvs coat\b/gi, "VS Code"],
  [/\bvs code\b/gi, "VS Code"],
  [/\bvisual studio coat\b/gi, "Visual Studio Code"],
  [/\bpower point\b/gi, "PowerPoint"],
  [/\bg mail\b/gi, "Gmail"],
  [/\byou tube\b/gi, "YouTube"],
]

function normalizeTranscript(raw = "", alternatives = []) {
  const candidates = [
    { transcript: raw, confidence: 0 },
    ...(Array.isArray(alternatives) ? alternatives : []).map((item) =>
      typeof item === "string" ? { transcript: item, confidence: 0 } : item
    ),
  ]
    .map((item) => ({
      transcript: String(item?.transcript || "").replace(/\s+/g, " ").trim(),
      confidence: Number(item?.confidence || 0),
    }))
    .filter((item) => item.transcript)
    .sort((a, b) => b.confidence - a.confidence)
  const preferred = candidates.find((item) => /sachin|tendhulkar|tendulkar/i.test(item.transcript)) || candidates[0] || { transcript: "", confidence: 0 }
  const original = preferred.transcript
  let corrected = original
  for (const [pattern, replacement] of TRANSCRIPT_CORRECTIONS) {
    corrected = corrected.replace(pattern, replacement)
  }
  corrected = corrected
    .replace(/^(hey\s+)?CEASER[,.\s-]*/i, "")
    .replace(/\s+/g, " ")
    .trim()
  return {
    transcript: corrected,
    original,
    confidence: preferred.confidence,
    alternatives: candidates,
  }
}

function isTranscriptReliable(result) {
  const transcript = String(result?.transcript || "").trim()
  const original = String(result?.original || "").trim()
  const confidence = Number(result?.confidence || 0)
  if (!transcript) return false
  const wordCount = transcript.split(/\s+/).filter(Boolean).length
  const commandLike = ASSISTANT_INTENT_PATTERN.test(transcript)
    || /^(open|close|play|pause|next|previous|stop|mute|unmute|increase|decrease|summarize|create|write|explain|search|show|check)\b/i.test(transcript)
  if (commandLike) return true
  if (wordCount >= 3 && confidence >= 0.35) return true
  if (wordCount >= 5) return true
  if (/\b(?:curve|tender|random|unknown)\b/i.test(original) && !/\bsachin|tendulkar/i.test(transcript)) return false
  return true
}

function fitOverlay() {
  window.clearTimeout(fitTimer)
  fitTimer = window.setTimeout(() => {
    const shell = document.querySelector(`.${activeMode}-shell`)
    if (!shell || !window.ceaserDesktop?.fitContent) return
    if (activeMode === "expanded") fitExpandedShell(shell)
    if (activeMode === "compact" && !appShell.classList.contains("full-answer")) {
      const next = { width: 386, height: 70 }
      if (Math.abs(next.width - lastFit.width) < 2 && Math.abs(next.height - lastFit.height) < 2) return
      lastFit = next
      window.ceaserDesktop.fitContent(next)
      return
    }
    const rect = shell.getBoundingClientRect()
    const minWidth = activeMode === "expanded" ? 458 : activeMode === "compact" ? 292 : 88
    const minHeight = activeMode === "expanded" ? 314 : activeMode === "compact" ? 96 : 88
    const next = {
      width: Math.max(Math.ceil(rect.width + 28), minWidth),
      height: Math.max(Math.ceil(rect.height + 28), minHeight),
    }
    if (Math.abs(next.width - lastFit.width) < 2 && Math.abs(next.height - lastFit.height) < 2) return
    lastFit = next
    window.ceaserDesktop.fitContent(next)
  }, 80)
}

function fitExpandedShell(shell) {
  const baseWidth = 430
  const maxWidth = Math.min(760, Math.max(430, window.screen.availWidth - 80))
  const maxPanelHeight = Math.min(560, Math.max(260, window.screen.availHeight - 220))
  const contentWidth = dynamicPanel ? dynamicPanel.scrollWidth + 34 : baseWidth
  const promptWidth = promptBubble && !promptBubble.classList.contains("hidden") ? promptBubble.scrollWidth + 70 : baseWidth
  const nextWidth = Math.min(maxWidth, Math.max(baseWidth, contentWidth, promptWidth))
  shell.style.setProperty("--expanded-width", `${nextWidth}px`)
  shell.style.setProperty("--dynamic-max-height", `${maxPanelHeight}px`)
  shell.style.setProperty("--expanded-max-height", `${Math.min(760, Math.max(430, window.screen.availHeight - 84))}px`)
}

function setMode(mode) {
  window.clearTimeout(hideTimer)
  window.clearTimeout(retractTimer)
  // Keep CEASER's compact capsule as the only resting surface. Legacy
  // minimal-mode callers collapse into the same capsule rather than an orb.
  activeMode = mode === "minimal" ? "compact" : mode
  appShell.className = `overlay ${activeMode}`
  updateActivitySurface()
  window.ceaserDesktop?.setMode(activeMode)?.finally(() => fitOverlay())
}

function retractToCompact(delay = 5600) {
  window.clearTimeout(retractTimer)
  retractTimer = window.setTimeout(() => {
    if (listeningActive || appShell.dataset.state === "error") return
    setMode("compact")
    appShell.classList.remove("full-answer")
    compactSubtitle.classList.remove("long", "full")
    setState("idle", "CEASER ready", assistantSessionActive ? "Say Hey CEASER when you need me." : "Say or type a command.")
    showPrompt("")
    renderIdlePanel()
  }, delay)
}

function isLikelyEditableContext(context = {}) {
  const active = context.activeWindow || {}
  const process = String(active.process || "")
  const title = String(active.title || "")
  return EDITABLE_PROCESS_PATTERN.test(process) || /\b(gmail|docs|compose|notion|slack|discord|teams|whatsapp|word|excel|notepad|visual studio code|cursor)\b/i.test(title)
}

function isAssistantIntent(text = "") {
  const value = String(text || "").trim()
  if (!value) return false
  if (ASSISTANT_INTENT_PATTERN.test(value)) return true
  return /^(can you|could you|please|hey ceaser|ceaser)\b/i.test(value)
}

function isExplicitCeaserCommand(text = "") {
  return /^(hey\s+)?(?:ceaser|caesar|cesar|seizer|sizer|scissor|season)\b/i.test(String(text || "").trim())
}

async function routeUnifiedVoice(command, context = {}) {
  const cleaned = String(command || "").trim()
  if (!cleaned) {
    setState("idle", "CEASER ready", "Say Hey CEASER when you need me.")
    window.ceaserDesktop?.hideOverlay?.()
    return
  }
  commandInput.value = cleaned
  const editable = isLikelyEditableContext(context)
  const explicitCeaserCommand = isExplicitCeaserCommand(cleaned)
  const shouldDictate = !explicitCeaserCommand && (editable || !isAssistantIntent(cleaned))
  if (shouldDictate) {
    setMode("compact")
    setState("voice_compose", "Polishing...", "Preparing text.")
    const result = await window.ceaserDesktop.voiceCompose({ text: cleaned, context })
    if (result?.status === "completed") {
      setState("completed", "Inserted", result.text || "Text inserted.")
      window.setTimeout(() => window.ceaserDesktop?.hideOverlay?.(), 900)
      return
    }
    setState("error", "Insert failed", result?.message || "Could not insert text.")
    return
  }
  await runCommand(cleaned.replace(/^(hey\s+)?(?:ceaser|caesar|cesar|seizer|sizer|scissor|season)[,.\s-]*/i, ""))
}

function setState(state, title, subtitle) {
  const hasLongAnswer = state === "completed" && (subtitle || "").length > 90
  if (hasLongAnswer && activeMode === "compact") setMode("expanded")
  appShell.dataset.state = state
  stateEyebrow.textContent = state.replace("_", " ")
  stateTitle.textContent = title
  stateSubtitle.textContent = subtitle || ""
  compactTitle.textContent = title
  compactSubtitle.textContent = capsuleCompactLabel(state, title)
  compactSubtitle.classList.remove("long", "full")
  appShell.classList.toggle("full-answer", state === "completed" && (subtitle || "").length > 120)
  if (surfaceStateLabel) surfaceStateLabel.textContent = capsuleStateLabel(state)
  if (compactProgressBar) compactProgressBar.style.width = progressWidthForState(state)
  fitOverlay()
}

function capsuleCompactLabel(state, title = "") {
  if (["executing", "working", "voice_compose"].includes(state) && title) {
    return String(title).replace(/\.{3}$/, "").slice(0, 28)
  }
  return capsuleStateLabel(state)
}

function capsuleStateLabel(state) {
  return ({
    idle: "Ready",
    listening: "Listening",
    command_listening: "Listening",
    follow_up_listening: "Listening",
    transcribing: "Understanding",
    thinking: "Thinking",
    routing: "Thinking",
    executing: "Executing",
    working: "Working",
    speaking: "Speaking",
    completed: "Ready",
    waiting_for_confirmation: "Needs attention",
    clarifying: "Needs input",
    offline: "Offline",
    silent_background: "Silent",
    error: "Needs attention",
  })[state] || "Ready"
}

function progressWidthForState(state) {
  if (state === "idle") return "18%"
  if (state === "listening") return "42%"
  if (state === "transcribing") return "52%"
  if (state === "thinking") return "64%"
  if (state === "working") return "76%"
  if (state === "waiting_for_confirmation") return "58%"
  if (state === "completed") return "100%"
  if (state === "error") return "100%"
  return "32%"
}

function renderIntent(intent) {
  pendingIntent = intent
  setMode(intent.overlay_mode || "expanded")
  const overlayState = intent.requires_confirmation ? "waiting_for_confirmation" : intent.overlay_state || "thinking"
  setState(overlayState, titleForIntent(intent), subtitleForIntent(intent))
  showPrompt(promptText(intent))
  renderDynamicIntent(intent)
  activeAgent.textContent = intent.active_agent || "CEASER"
  intentType.textContent = intent.intent?.replace("_", " ") || "Ready"
  resultTitle.textContent = intent.result_preview?.title || "Working"
  resultSummary.textContent = intent.result_preview?.summary || "CEASER is preparing this request."
  renderStats(intent.result_preview?.stats || [])
  renderSteps(intent.progress_steps || [])

  confirmationCard.classList.toggle("hidden", !intent.requires_confirmation)
  confirmationText.textContent = confirmationMessage(intent)
  if (!intent.requires_confirmation && intent.intent === "desktop_action") executeIntent(intent)
  else if (intent.intent === "agent_action") executeAgent(intent)
  else if (intent.intent === "identity_action") answerIdentity(intent)
  else if (intent.intent === "answer_action") answerQuestion(intent)
  else if (intent.intent === "blocked_action") complete({ status: "error", message: intent.result_preview?.summary || "CEASER blocked this action." })
  else if (intent.requires_confirmation) promptForVoiceConfirmation(intent)
  else if (intent.intent === "chat_action") answerQuestion({ parameters: { question: intent.parameters?.message } })
  fitOverlay()
}

function titleForIntent(intent) {
  if (intent.intent === "agent_action") return `${intent.active_agent} ${intent.agent_action || "Working"}`
  if (intent.intent === "desktop_action") return intent.requires_confirmation ? "Confirm Action" : "Working..."
  return "Thinking..."
}

function subtitleForIntent(intent) {
  if (intent.intent === "agent_action") return intent.result_preview?.summary || "Agent is working."
  if (intent.intent === "desktop_action") return intent.result_preview?.summary || "Preparing desktop action."
  if (intent.intent === "identity_action") return intent.result_preview?.summary || "Building CEASER identity."
  return "Analyzing your request"
}

function confirmationMessage(intent) {
  if (intent.action === "create_folder") return `Create folder "${intent.parameters?.name}" in ${intent.parameters?.base}?`
  if (intent.action === "take_screenshot") return "Allow CEASER to take a screenshot now?"
  if (intent.action === "clear_clipboard") return "Clear clipboard contents?"
  if (intent.action === "lock_computer") return "Lock this computer now?"
  return "Allow CEASER to continue?"
}

function renderSteps(steps) {
  if (!stepsList || !progressPercent) return
  stepsList.innerHTML = ""
  const normalized = steps.length ? steps : [{ label: "Ready", status: "done" }]
  let doneCount = 0
  normalized.forEach((step) => {
    const li = document.createElement("li")
    li.className = step.status || "pending"
    li.textContent = step.label
    if (step.status === "done") doneCount += 1
    stepsList.appendChild(li)
  })
  const percent = Math.round((doneCount / normalized.length) * 100)
  progressPercent.textContent = `${percent}%`
  progressBar.style.width = `${Math.max(percent, 12)}%`
  if (compactProgressBar && appShell.dataset.state === "working") compactProgressBar.style.width = `${Math.max(percent, 18)}%`
  fitOverlay()
}

function renderStats(stats) {
  resultStats.innerHTML = ""
  stats.forEach((value) => {
    const span = document.createElement("span")
    span.className = "stat"
    span.textContent = value
    resultStats.appendChild(span)
  })
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;")
}

function promptText(intent) {
  return intent?.parameters?.message
    || intent?.parameters?.question
    || intent?.parameters?.query
    || intent?.result_preview?.summary
    || commandInput.value
    || ""
}

function showPrompt(text) {
  if (!promptBubble) return
  const value = String(text || "").trim()
  promptBubble.textContent = value
  promptBubble.classList.toggle("hidden", !value)
}

function setDynamicPanel(className, html) {
  if (!dynamicPanel) return
  dynamicPanel.className = `dynamic-panel ${className}`
  dynamicPanel.innerHTML = html
  fitOverlay()
}

function loadLastResultContext() {
  try {
    return JSON.parse(window.localStorage.getItem("ceaser:lastResultContext") || "null")
  } catch (_error) {
    return null
  }
}

function saveLastResultContext(context) {
  if (!context?.content) return
  lastResultContext = {
    ...context,
    content: String(context.content || "").trim(),
    createdAt: new Date().toISOString(),
  }
  try {
    window.localStorage.setItem("ceaser:lastResultContext", JSON.stringify(lastResultContext))
  } catch (_error) {
    // Local context is helpful, not critical.
  }
}

function inferResultType(intent = {}, response = {}, content = "") {
  const prompt = String(promptText(intent) || lastCommand || "").toLowerCase()
  const action = intent?.action || ""
  if (action === "create_document" || /\b(document|pdf|docx|report|presentation|deck)\b/.test(prompt)) return "document"
  if (/\b(email|gmail|mail|cover letter)\b/.test(prompt)) return "email_draft"
  if (/\b(timetable|time table|study plan|schedule)\b/.test(prompt)) return "timetable"
  if (/\b(notes|mcq|flashcard|quiz)\b/.test(prompt)) return "study_content"
  if (/\b(research|sources|competitor|market)\b/.test(prompt)) return "research"
  if (action === "get_calendar_events") return "calendar"
  if (action === "get_news") return "news"
  if (action === "get_weather") return "weather"
  if (content.length > 220) return "generated_text"
  return "answer"
}

function captureResultContext(intent = {}, response = {}, fallback = "") {
  const content = String(response?.preview || response?.answer || response?.message || fallback || "").trim()
  if (!content || response?.status === "error" || response?.status === "cancelled") return
  const type = inferResultType(intent, response, content)
  saveLastResultContext({
    type,
    title: response?.document?.file_name || response?.file?.name || resultTitle.textContent || "CEASER result",
    content,
    prompt: promptText(intent) || lastCommand,
    action: intent?.action || "",
    metadata: {
      document: response?.document || null,
      file: response?.file || null,
    },
  })
}

function renderIdlePanel() {
  const name = displayNameFromUser(linkedUser)
  setDynamicPanel("idle-panel", `
    <div class="idle-orb">
      <div class="voice-circle">
        <img src="./assets/ceaser-orb.png" alt="CEASER" />
        <div class="waveform" aria-hidden="true">
          <i></i><i></i><i></i><i></i><i></i><i></i><i></i>
        </div>
      </div>
    </div>
    <h1>Hey ${escapeHtml(name)},</h1>
    <p>Speak, type, or drag a file here.</p>
    <div class="idle-actions">
      <span>Speak</span><span>Type</span><span>Drag & Drop</span>
    </div>
  `)
}

function displayNameFromUser(user) {
  const source = user?.user || user || {}
  const meta = source.user_metadata || source.metadata || {}
  const raw = source.name || source.full_name || source.display_name || source.username || meta.name || meta.full_name || meta.display_name || source.email || ""
  const value = String(raw || "").trim()
  if (!value) return "there"
  if (value.includes("@")) return value.split("@")[0].split(/[._-]/).filter(Boolean)[0] || "there"
  return value.split(/\s+/)[0] || "there"
}

function applyLinkedUser(auth) {
  linkedUser = auth?.user || null
  if (dynamicPanel?.classList?.contains("idle-panel")) renderIdlePanel()
}

function renderDynamicIntent(intent) {
  if (!dynamicPanel) return
  const action = intent?.action
  if (action === "get_weather") {
    setDynamicPanel("weather-card", `
      <div class="weather-location">${escapeHtml(intent.parameters?.location || "Hyderabad, IN")}<span>Checking weather...</span></div>
      <div class="weather-main">
        <div class="weather-icon">â›…</div>
        <div class="weather-temp">--Â°C</div>
        <div class="weather-meta"><span>Humidity</span><strong>--</strong><span>Wind</span><strong>--</strong></div>
      </div>
    `)
    return
  }
  if (action === "get_news") {
    setDynamicPanel("news-card", `<h3>Top News</h3><div class="view-more">Reading latest headlines...</div>`)
    return
  }
  if (action === "create_document") {
    setDynamicPanel("document-card", `
      <h2>Creating ${escapeHtml(String(intent.parameters?.kind || "document").toUpperCase())}</h2>
      <p>${escapeHtml(intent.parameters?.prompt || "Preparing your document.")}</p>
      <div class="doc-status">Saving to CEASER Files...</div>
    `)
    return
  }
  if (action === "play_youtube" || action === "media_key" || action === "now_playing") {
    renderMusicPanel(intent.parameters?.query || intent.result_preview?.summary || "Music")
    return
  }
  if (action === "stock_price") {
    renderStockPanel()
    return
  }
  if (action === "set_timer") {
    renderTimerPanel(intent.parameters)
    return
  }
  if (action === "get_tasks") {
    renderTasksPanel()
    return
  }
  if (action === "open_app" || action === "focus_app" || action === "check_app_running" || action === "close_app" || action === "restart_app") {
    renderLauncherPanel(intent.parameters?.label || intent.parameters?.app_name || "Application", "Launching application...", 80)
    return
  }
  if (action === "daily_brief" || /\bcalendar|schedule|meeting/i.test(promptText(intent))) {
    renderCalendarPanel()
    return
  }
  if (/\btask|todo|to-do/i.test(promptText(intent))) {
    renderTasksPanel()
    return
  }
  if (/\btimer|alarm/i.test(promptText(intent))) {
    renderTimerPanel()
    return
  }
  if (intent.intent === "agent_action") {
    setDynamicPanel("answer-card", `
      <h2>${escapeHtml(intent.active_agent || "CEASER")} ${escapeHtml(intent.agent_action || "Working")}</h2>
      <p>${escapeHtml(intent.result_preview?.summary || "CEASER is working on it.")}</p>
    `)
    return
  }
  if (intent.intent === "answer_action" || intent.intent === "chat_action") {
    setDynamicPanel("answer-card", `<h2>Thinking...</h2><p>${escapeHtml(promptText(intent))}</p>`)
  }
}

function renderDynamicResult(response, intent) {
  const action = intent?.action
  if (action === "get_weather") return renderWeatherPanel(response?.weather, response?.message)
  if (action === "get_news") return renderNewsPanel(response?.articles || [], response?.message)
  if (action === "create_document") return renderDocumentPanel(response)
  if (action === "play_youtube" || action === "media_key" || action === "now_playing") {
    return renderMusicPanel(response?.music || {
      title: action === "play_youtube" ? intent?.parameters?.query : "Playback Control",
      source: action === "play_youtube" ? "YouTube" : "System Media",
      message: response?.message,
      status: response?.message,
    })
  }
  if (action === "stock_price") return renderStockPanel(response?.stock, response?.message)
  if (action === "set_timer") return renderTimerPanel(response?.timer || intent?.parameters)
  if (action === "get_tasks") return renderTasksPanel(response?.message)
  if (action === "open_app" || action === "focus_app" || action === "check_app_running" || action === "close_app" || action === "restart_app") {
    return renderLauncherPanel(intent?.parameters?.label || intent?.parameters?.app_name || "Application", response?.message || "Action completed.", response?.status === "error" ? 15 : 100)
  }
  if (action === "get_calendar_events") return renderCalendarPanel(response?.message, response?.events || [], intent?.parameters?.range)
  if (action === "daily_brief" || /\bcalendar|schedule|meeting/i.test(promptText(intent))) return renderCalendarPanel(response?.message)
  if (/\btask|todo|to-do/i.test(promptText(intent))) return renderTasksPanel(response?.message)
  if (/\btimer|alarm/i.test(promptText(intent))) return renderTimerPanel()
  if (response?.message) {
    setDynamicPanel("answer-card", `<h2>${response.status === "error" ? "Something went wrong" : "Answer"}</h2><p>${escapeHtml(response.message)}</p>`)
  }
}

function renderWeatherPanel(weather, fallback) {
  const temp = Math.round(Number(weather?.temperature ?? 28))
  const location = weather?.location || "Hyderabad, Telangana"
  const description = weather?.description || fallback || "Current conditions"
  const humidity = weather?.humidity ? `${weather.humidity}%` : "--"
  const wind = weather?.wind_speed ? `${Math.round(weather.wind_speed)} km/h` : "--"
  setDynamicPanel("weather-card", `
    <div class="weather-location">${escapeHtml(location)}<span>${escapeHtml(new Date().toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" }))}</span></div>
    <div class="weather-main">
      <div class="weather-icon">${/rain/i.test(description) ? "ðŸŒ§ï¸" : /cloud/i.test(description) ? "â›…" : "â˜€ï¸"}</div>
      <div><div class="weather-temp">${temp}Â°C</div><p>${escapeHtml(description)}</p></div>
      <div class="weather-meta"><span>Humidity</span><strong>${humidity}</strong><span>Wind</span><strong>${wind}</strong></div>
    </div>
    <div class="forecast-row">${["Now","11 AM","12 PM","1 PM","2 PM","3 PM","4 PM"].map((label, index) => `<span>${label}<b>${index % 3 === 0 ? "â˜€ï¸" : "â›…"}</b><small>${temp + (index % 4)}Â°</small></span>`).join("")}</div>
  `)
}

function renderNewsPanel(articles, fallback) {
  const rows = articles.slice(0, 4).map((article) => `
    <div class="news-item">
      <div><div class="news-title">${escapeHtml(article.title || "News update")}</div><div class="news-source">${escapeHtml(article.source || article.publisher || "News")} Â· ${escapeHtml(article.published_at || "Latest")}</div></div>
      ${article.image_url || article.urlToImage ? `<img class="news-thumb" src="${escapeHtml(article.image_url || article.urlToImage)}" alt="">` : `<div class="news-thumb"></div>`}
    </div>
  `).join("")
  setDynamicPanel("news-card", `
    <h3>Top News</h3>
    ${rows || `<div class="view-more">${escapeHtml(fallback || "No live headlines available yet.")}</div>`}
    <div class="view-more">View more news â€º</div>
  `)
}

function renderMusicPanel(title) {
  setDynamicPanel("music-card", `
    <div class="album-art"></div>
    <div class="music-info">
      <h2>${escapeHtml(title || "Music")}</h2>
      <p>YouTube</p>
      <div class="player-line"></div>
      <div class="player-controls"><span>â—€</span><span class="play-circle">â…¡</span><span>â–¶</span></div>
    </div>
  `)
}

function renderCalendarPanel(message = "", events = [], range = "today") {
  const rows = events.length ? events.map((event) => [formatCalendarTime(event.start), event.title || "Untitled event", event.location || ""]) : [
    ["", message || "No events found.", range === "tomorrow" ? "Tomorrow" : "Calendar"],
  ]
  setDynamicPanel("calendar-card", `
    <h3>Today Â· ${escapeHtml(new Date().toLocaleDateString(undefined, { day: "numeric", month: "short" }))}</h3>
    ${rows.map(([time, title, duration]) => `<div class="calendar-item"><div class="calendar-time">${escapeHtml(time)}</div><div class="calendar-title">${escapeHtml(title)}</div><div class="calendar-meta">${escapeHtml(duration)}</div></div>`).join("")}
    <div class="view-more">${events.length ? "Open Calendar" : "Connect or sync Google Calendar in CEASER"}</div>
  `)
}

function renderTasksPanel(message = "") {
  const rows = [
    ["Finish CEASER overlay design", "high"],
    ["Fix document export issue", "medium"],
    ["Prepare pitch deck", "high"],
    ["Study system design", "low"],
  ]
  setDynamicPanel("tasks-card", `
    <h3>My Tasks</h3>
    ${rows.map(([title, priority]) => `<div class="task-item"><span class="task-check"></span><div class="task-title">${title}</div><span class="priority ${priority}">${priority}</span></div>`).join("")}
    <div class="view-more">${message ? escapeHtml(message) : "View all tasks â€º"}</div>
  `)
}

function renderStockPanel(stock, message = "") {
  setDynamicPanel("stock-card", `
    <div class="stock-logo">ï£¿</div>
    <div>
      <h2>${escapeHtml(stock?.query || "Market Snapshot")}</h2>
      <div class="stock-price">Live data</div>
      <div class="stock-up">${escapeHtml(message || "Connect a market API to enable live prices.")}</div>
    </div>
    <div class="stock-chart"></div>
  `)
}

function renderTimerPanel(timer) {
  const amount = Number(timer?.amount || 25)
  const unit = String(timer?.unit || "minutes")
  const minutes = /hour/.test(unit) ? amount * 60 : /sec/.test(unit) ? 1 : amount
  const label = `${String(minutes).padStart(2, "0")}:00`
  setDynamicPanel("timer-card", `
    <div class="timer-ring"><div class="timer-inner"><strong>${escapeHtml(label)}</strong><span>Timer</span></div></div>
    <div class="timer-actions"><span>â…¡ Pause</span><span>Ã— Cancel</span></div>
  `)
}

function renderLauncherPanel(appName, message, progress) {
  setDynamicPanel("launcher-card", `
    <div class="app-icon-large">${escapeHtml(String(appName || "A").slice(0, 1).toUpperCase())}</div>
    <div>
      <h2>${escapeHtml(appName || "Application")}</h2>
      <p>${escapeHtml(message || "Launching application...")}</p>
      <div class="launcher-progress" style="background: linear-gradient(90deg, #a65cff ${Number(progress || 80)}%, rgba(255,255,255,.15) ${Number(progress || 80)}%)"></div>
    </div>
  `)
}

async function refreshContext() {
  if (!window.ceaserDesktop?.getContext) return
  try {
    const context = await window.ceaserDesktop.getContext()
    currentApp.textContent = context.activeWindow?.process || "Unknown"
    recentFile.textContent = context.recentFiles?.[0]?.name || "None yet"
    sessionSummary.textContent = context.behavior?.suggestions?.[0] || context.session?.message || "No desktop activity tracked yet."
    contextStatus.textContent = `${context.openWindows?.length || 0} windows`
    fitOverlay()
  } catch (_error) {
    contextStatus.textContent = "Unavailable"
  }
}

async function executeIntent(intent) {
  if (intent.action === "create_document") {
    return executeDocumentIntent(intent)
  }
  const response = await window.ceaserDesktop.execute(intent)
  if (response.status === "permission_required") {
    confirmationCard.classList.remove("hidden")
    confirmationText.textContent = "Permission is required. Confirm once to allow this CEASER desktop capability."
    pendingIntent = { ...intent, permission: response.permission }
    return
  }
  if (response.status === "confirmation_required") {
    confirmationCard.classList.remove("hidden")
    return
  }
  complete(response)
  refreshContext()
}

async function executeDocumentIntent(intent) {
  setState("working", "Creating document", intent.parameters?.prompt || "Preparing document.")
  resultTitle.textContent = "Document generation"
  resultSummary.textContent = "CEASER is creating and saving the document."
  const task = startTask(intent, "document")
  const response = await window.ceaserDesktop.createDocument({
    intent,
    task_id: task.id,
  })
  if (!isCurrentTask(task)) return
  finishActiveTask()
  complete(response)
  refreshContext()
}

function promptForVoiceConfirmation(intent) {
  const message = `${confirmationMessage(intent)} Say confirm to continue, or cancel to stop.`
  resultTitle.textContent = "Confirmation needed"
  resultSummary.textContent = message
  const generation = speechGeneration + 1
  speak(message, () => {
    if (generation === speechGeneration && pendingIntent === intent && !listeningActive) {
      startVoiceCommand()
    }
  })
}

async function executeAgent(intent) {
  setState("working", titleForIntent(intent), subtitleForIntent(intent))
  resultTitle.textContent = intent.result_preview?.title || "Agent Working"
  resultSummary.textContent = intent.result_preview?.summary || "CEASER is preparing this request."
  const task = startTask(intent, "agent")
  const response = await window.ceaserDesktop.runAgent({
    intent,
    message: intent.parameters?.message,
    task_id: task.id,
    desktop_file_context: selectedDesktopFileContext,
  })
  selectedDesktopFileContext = null
  if (!isCurrentTask(task)) return
  finishActiveTask()
  complete(response)
  refreshContext()
}

async function answerQuestion(intent) {
  setState("thinking", "Thinking...", intent.parameters?.question || "Preparing an answer.")
  showPrompt(intent.parameters?.question || "")
  resultTitle.textContent = "Answering"
  resultSummary.textContent = intent.parameters?.question || ""
  const task = startTask(intent, "answer")
  const response = await window.ceaserDesktop.answerQuestion({ question: intent.parameters?.question, task_id: task.id })
  if (!isCurrentTask(task)) return
  finishActiveTask()
  const answer = response?.answer || "I could not get an answer."
  const state = response?.status === "completed" ? "completed" : response?.status === "cancelled" ? "idle" : "error"
  setState(state, response?.status === "completed" ? "Answered" : response?.status === "cancelled" ? "Stopped" : "Answer unavailable", answer)
  if (shouldKeepOutputVisible(answer, intent)) {
    renderStickyOutput(response?.status === "completed" ? "Answer" : "Answer unavailable", answer, intent, response)
  } else {
    setDynamicPanel("answer-card", `<h2>${response?.status === "completed" ? "Answer" : "Answer unavailable"}</h2><p>${escapeHtml(answer)}</p>`)
  }
  resultTitle.textContent = response?.status === "completed" ? "Answer" : response?.status === "cancelled" ? "Stopped" : "Answer unavailable"
  resultSummary.textContent = answer
  captureResultContext(intent, response, answer)
  if (response?.status !== "cancelled") {
    const spoken = spokenResponseFor(response, intent, answer)
    if (spoken) speak(spoken, () => afterAssistantTurn())
    else afterAssistantTurn()
  }
  fitOverlay()
  if (activeMode === "expanded" && response?.status === "completed" && !shouldKeepOutputVisible(answer, intent)) retractToCompact()
}

async function answerIdentity(intent) {
  setState("thinking", "Thinking...", intent.parameters?.question || "Building CEASER identity.")
  showPrompt(intent.parameters?.question || "")
  resultTitle.textContent = "CEASER Identity"
  resultSummary.textContent = intent.parameters?.question || ""
  const response = await window.ceaserDesktop.identity({
    question: intent.parameters?.question,
    previousCommand: lastCommand,
    currentAgent: activeAgent.textContent || "CEASER",
    currentWorkflow: activeTask?.type || "None",
    systemState: appShell.dataset.state || "Online",
  })
  const answer = response?.answer || "I'm CEASER, your voice-first personal AI operating system."
  setState("completed", "CEASER", answer)
  setDynamicPanel("answer-card", `<h2>CEASER</h2><p>${escapeHtml(answer)}</p>`)
  resultTitle.textContent = "Identity"
  resultSummary.textContent = answer
  captureResultContext(intent, response, answer)
  speak(answer, () => afterAssistantTurn())
  fitOverlay()
  if (activeMode === "expanded") retractToCompact()
}

function speak(text, onend) {
  if (!text) {
    if (typeof onend === "function") window.setTimeout(onend, 0)
    return
  }
  window.speechSynthesis?.cancel()
  if (currentProviderAudio) {
    currentProviderAudio.pause()
    currentProviderAudio = null
  }
  speechGeneration += 1
  const generation = speechGeneration
  currentSpeechOnEnd = typeof onend === "function" ? onend : null
  let finished = false
  speakingActive = true
  window.ceaserDesktop?.pythonVoiceCommand?.({ type: "voice_playback", state: "speaking", spoken_response: text }).catch(() => {})
  const finish = () => {
    if (finished) return
    finished = true
    currentProviderAudio = null
    speakingActive = false
    window.ceaserDesktop?.pythonVoiceCommand?.({ type: "voice_playback", state: "finished" }).catch(() => {})
    if (generation === speechGeneration) currentSpeechOnEnd = null
    restoreMediaAfterListening("speech-finished")
    if (generation === speechGeneration && typeof onend === "function") onend()
  }

  const speakWithSystem = () => {
    if (generation !== speechGeneration || !window.speechSynthesis) return finish()
    const utterance = new SpeechSynthesisUtterance(text)
    let started = false
    const fallbackTimer = window.setTimeout(() => {
      if (!started && !window.speechSynthesis?.speaking && !window.speechSynthesis?.pending) finish()
    }, 2500)
    utterance.rate = 1.12
    utterance.volume = 1
    utterance.lang = "en-US"
    utterance.onstart = () => {
      started = true
      window.clearTimeout(fallbackTimer)
    }
    utterance.onend = finish
    utterance.onerror = finish
    window.speechSynthesis.speak(utterance)
  }

  window.ceaserDesktop?.pythonVoiceCommand?.({ type: "synthesize_speech", text })
    .then((response) => {
      if (generation !== speechGeneration) return
      if (response?.status !== "completed" || !response?.audio_base64) {
        console.log(`[CEASER Voice] tts_fallback provider=${response?.provider || "system"} reason=${response?.reason || "unavailable"}`)
        speakWithSystem()
        return
      }
      const audio = new Audio(`data:${response.mime_type || "audio/mpeg"};base64,${response.audio_base64}`)
      currentProviderAudio = audio
      audio.onended = finish
      audio.onerror = () => {
        currentProviderAudio = null
        speakWithSystem()
      }
      audio.play().catch(() => {
        currentProviderAudio = null
        speakWithSystem()
      })
      console.log(`[CEASER Voice] tts_provider=elevenlabs first_audio_ms=${response.first_audio_ms || 0} total_ms=${response.total_ms || 0}`)
    })
    .catch(speakWithSystem)
}

function compactLogText(value, limit = 260) {
  const text = String(value || "").replace(/\s+/g, " ").trim()
  return text.length > limit ? `${text.slice(0, limit - 1)}â€¦` : text
}

function logSpokenResponse(command, spoken, response = {}) {
  if (!spoken) return
  console.log("[CEASER speech]", JSON.stringify({
    command: compactLogText(command, 180),
    status: response?.status || "",
    capability: response?.capability || "",
    spoken_response: compactLogText(spoken, 320),
  }))
}

async function duckMediaForListening(reason = "listening") {
  if (mediaDuckedForListening) return
  try {
    const result = await window.ceaserDesktop?.duckMedia?.({ reason, presses: 6, mediaActive: mediaPlaybackExpected })
    const ducked = result?.status === "ducked" || result?.status === "already_ducked"
    mediaDuckedForListening = ducked
    if (ducked) console.log("[CEASER] Media ducked:", reason)
    else console.log("[CEASER] Media duck skipped:", result?.status || "unavailable")
  } catch (error) {
    mediaDuckedForListening = false
    console.warn("[CEASER] Media duck failed:", error.message || error)
  }
}

async function restoreMediaAfterListening(reason = "restore") {
  if (!mediaDuckedForListening) return
  mediaDuckedForListening = false
  try {
    await window.ceaserDesktop?.restoreMedia?.()
    console.log("[CEASER] Media restored:", reason)
  } catch (error) {
    console.warn("[CEASER] Media restore failed:", error.message || error)
  }
}

function stopCurrentSpeech(reason = "user-interrupt") {
  speechGeneration += 1
  currentSpeechOnEnd = null
  if (window.speechSynthesis) window.speechSynthesis.cancel()
  if (currentProviderAudio) {
    currentProviderAudio.pause()
    currentProviderAudio = null
  }
  window.ceaserDesktop?.pythonVoiceCommand?.({ type: "voice_playback", state: "interrupted", reason }).catch(() => {})
  speakingActive = false
  voiceCommandGeneration += 1
  voiceSession = null
  setVoiceButtonState(false)
  restoreMediaAfterListening("speech-stopped")
  console.log("[CEASER] Speech stopped:", reason)
  setState("idle", "Stopped speaking", "Say Hey CEASER for the next command.")
  return true
}

function isSpeechStopCommand(command) {
  return /\b(stop|cancel|wait|never mind|nevermind|stop talking|stop speaking|stop reading|be quiet|quiet|silence|enough|cancel speech|stop voice|mute ceaser|mute caesar)\b/i.test(String(command || ""))
}

function spokenResponseFor(response = {}, intent = {}, fallback = "") {
  if (response.status === "cancelled") return null
  const action = intent?.action || ""
  const intentType = intent?.intent || ""
  const prompt = String(promptText(intent) || lastCommand || "").toLowerCase()
  const text = String(response.message || response.answer || fallback || "").trim()
  if (!text) return null

  if (response.status === "error") return shortSpeech(text, 18)

  const alwaysSpeakActions = new Set([
    "open_app",
    "close_app",
    "restart_app",
    "focus_app",
    "open_url",
    "open_folder",
    "create_folder",
    "play_youtube",
    "media_key",
    "set_timer",
  ])
  const voiceFriendlyActions = new Set([
    "get_weather",
    "get_news",
    "get_calendar_events",
    "system_info",
    "daily_brief",
    "read_clipboard",
  ])
  const silentLongActions = new Set([
    "create_document",
    "get_tasks",
    "session_summary",
    "recent_activity",
    "behavior_summary",
    "summarize_active_pdf",
    "web_search",
  ])

  if (alwaysSpeakActions.has(action)) return shortSpeech(text, 18)
  if (voiceFriendlyActions.has(action)) return shortSpeech(text, 55)
  if (silentLongActions.has(action)) return actionCompletedSpeech(action)
  if (intentType === "answer_action" || intentType === "identity_action") return shortSpeech(text, 65)
  if (intentType === "agent_action") return actionCompletedSpeech(action)
  if (/\b(timetable|time table|study plan|schedule plan|email draft|draft email|document|pdf|presentation|report|notes|mcq|flashcard)\b/i.test(prompt)) {
    return "Done. I prepared it on screen."
  }
  return text.length > 260 ? "Done. I prepared the full result on screen." : shortSpeech(text, 45)
}

function shouldKeepOutputVisible(text = "", intent = {}) {
  const value = String(text || "").trim()
  const prompt = String(promptText(intent) || lastCommand || "").toLowerCase()
  if (value.length > 120) return true
  return /\b(email|draft|document|pdf|report|presentation|timetable|time table|study plan|notes|mcq|flashcard|essay|letter|proposal|summary|explain|research|what do you know|tell me about|what is|who is|why|how)\b/i.test(prompt)
}

function renderStickyOutput(title, content, intent = {}, response = {}) {
  const text = String(content || "").trim()
  if (!text) return false
  setMode("expanded")
  setState(response.status === "error" ? "error" : "completed", title || "Answer", text)
  resultTitle.textContent = title || "Answer"
  resultSummary.textContent = text
  setDynamicPanel(response.status === "error" ? "error-card" : "answer-card", `
    <h2>${escapeHtml(title || "Answer")}</h2>
    <div class="sticky-output">${escapeHtml(text)}</div>
    <div class="sticky-actions">
      <button id="copyStickyOutput" type="button">Copy</button>
      <button id="saveStickyOutput" type="button">Save</button>
      <button id="hideStickyOutput" type="button">Hide</button>
    </div>
  `)
  window.setTimeout(() => {
    const copy = document.getElementById("copyStickyOutput")
    const save = document.getElementById("saveStickyOutput")
    const hide = document.getElementById("hideStickyOutput")
    if (copy) copy.onclick = () => window.ceaserDesktop?.copyText?.(text)
    if (save) save.onclick = () => {
      const saved = loadSavedResults()
      saved.unshift({
        id: `saved-${Date.now()}`,
        title: title || "CEASER result",
        type: inferResultType(intent, response, text),
        content: text,
        savedAt: new Date().toISOString(),
      })
      saveSavedResults(saved.slice(0, 50))
      showFollowUpResult("Saved", "Saved the result locally.")
    }
    if (hide) hide.onclick = () => {
      setMode("compact")
      appShell.classList.remove("full-answer")
      window.ceaserDesktop?.hideOverlay?.()
    }
  }, 0)
  captureResultContext(intent, response, text)
  fitOverlay()
  return true
}

function actionCompletedSpeech(action) {
  if (action === "create_document") return "Done. I created the document and opened CEASER Files."
  if (action === "get_tasks") return "Done. I prepared your tasks on screen."
  if (action === "summarize_active_pdf") return "Done. I prepared the summary on screen."
  if (action === "read_screen_text") return "Done. I read the screen and prepared the text on screen."
  if (action === "analyze_screen") return "Done. I analyzed the screen and prepared the result on screen."
  return "Done. I prepared it on screen."
}

function spokenPythonResponse(message = "", command = "", keepVisible = false) {
  const prompt = String(command || "").toLowerCase()
  const text = String(message || "").trim()
  if (!text) return "Done."
  if (/\b(screen\s*shot|screenshot|capture screen|take screen)\b/i.test(prompt)) {
    return "Done. I saved the screenshot."
  }
  if (/\b(email|draft|document|report|presentation|timetable|time table|study plan|notes|mcq|flashcard)\b/i.test(prompt)) {
    return "Done. I prepared it on screen."
  }
  if (/\b(explain|summary|summarize|summarise|research|answer|question|what is|who is|why|how|tell me|read|ocr|screen|analyze|analyse|table|chart)\b/i.test(prompt)) {
    return shortSpeech(text, 75)
  }
  if (keepVisible || text.length > 260) return shortSpeech(text, 55)
  return shortSpeech(text, 24)
}

function shortSpeech(value, maxWords = 40) {
  const words = String(value || "").replace(/\s+/g, " ").trim().split(" ").filter(Boolean)
  if (words.length <= maxWords) return words.join(" ")
  return `${words.slice(0, maxWords).join(" ")}. I prepared the rest on screen.`
}

function cleanOverlayText(value) {
  const text = String(value || "").trim()
  if (!text || (!text.startsWith("{") && !text.startsWith("["))) return text
  try {
    const data = JSON.parse(text)
    if (Array.isArray(data)) {
      return data.slice(0, 10).map((item) => `- ${typeof item === "string" ? item : item?.name || item?.title || JSON.stringify(item)}`).join("\n")
    }
    if (!data || typeof data !== "object") return text
    const lines = []
    const title = data.title || data.type
    const summary = data.summary || data.message || data.answer
    if (title) lines.push(String(title))
    if (summary) lines.push(String(summary))
    ;(data.sections || []).forEach((section) => {
      if (!section || typeof section !== "object") return
      if (section.title || section.name) lines.push(`\n${section.title || section.name}`)
      if (section.description || section.details) lines.push(String(section.description || section.details))
      ;(section.items || []).slice(0, 8).forEach((item) => {
        if (typeof item === "string") lines.push(`- ${item}`)
        else lines.push(`- ${item?.name || item?.title || "Item"}${item?.description || item?.details ? `: ${item.description || item.details}` : ""}`)
      })
    })
    ;["actions", "next_steps", "warnings"].forEach((key) => {
      if (!Array.isArray(data[key]) || !data[key].length) return
      lines.push(`\n${key.replace("_", " ").replace(/\b\w/g, (char) => char.toUpperCase())}`)
      data[key].slice(0, 5).forEach((item) => lines.push(`- ${item}`))
    })
    return lines.filter(Boolean).join("\n").trim() || text
  } catch {
    return text
  }
}

async function runCommand(command) {
  const cleaned = String(command || "").trim()
  console.log(`[CEASER command] source=typed submitted=${JSON.stringify(cleaned.slice(0, 240))}`)
  if (!cleaned) return
  if (speakingActive || window.speechSynthesis?.speaking || window.speechSynthesis?.pending) stopCurrentSpeech("new-command")
  if (/\b(calibrate|test|check)\b.*\b(mic|microphone|voice)\b/i.test(cleaned) || /\bmic(?:rophone)? calibration\b/i.test(cleaned)) {
    await showMicCalibration()
    return
  }
  lastCommand = cleaned
  if (await handleConfirmationCommand(cleaned)) return
  if (await handleFollowUpCommand(cleaned)) return
  setState("thinking", "Working...", cleaned)
  if (window.ceaserDesktop?.pythonVoiceCommand) {
    try {
      const obviousLocalCommand = /^(?:please\s+)?(?:open|launch|start|run|switch\s+to|focus|close|quit|exit|play|pause|resume|continue|stop|next|previous|forward|backward|set|increase|decrease|mute|unmute|take|capture|lock)\b/i.test(cleaned)
      const desktopContext = obviousLocalCommand ? null : await window.ceaserDesktop?.getContext?.().catch(() => null)
      const response = await executePythonTextCommand(cleaned, { source: "typed", context: { ...(desktopContext || {}), desktop_file_context: selectedDesktopFileContext } })
      console.log(`[CEASER command] source=typed status=${response?.status || "unknown"} capability=${response?.capability || response?.action_result?.capability || "unknown"} error_code=${response?.error_code || response?.action_result?.error_code || "none"}`)
      selectedDesktopFileContext = null
      await renderPythonCommandResult(cleaned, response || { status: "error", message: "Command failed." }, { fromTyped: true })
      return
    } catch (error) {
      console.warn("[CEASER] Desktop Brain typed path failed; controlled recovery shown:", error.message || error)
      await renderPythonCommandResult(cleaned, {
        status: "error",
        message: "CEASER could not reach its command service. Please try again.",
        spoken_response: "I could not reach my command service. Please try again.",
        verified: false,
        error_code: "command_service_unavailable",
        fallback_used: false,
      }, { fromTyped: true })
      return
    }
  }
  await renderPythonCommandResult(cleaned, {
    status: "error",
    message: "CEASER command service is unavailable. Please restart CEASER and try again.",
    spoken_response: "My command service is unavailable. Please restart CEASER.",
    verified: false,
    error_code: "command_service_unavailable",
    fallback_used: false,
  }, { fromTyped: true })
}

async function handleFollowUpCommand(command) {
  const text = String(command || "").trim()
  const lower = text.toLowerCase()
  const context = lastResultContext
  if (!context?.content) return false
  const referencesPrevious = CONTEXT_REFERENCE_PATTERN.test(lower)
    || /\b(copy|save|open|send|gmail|calendar|shorten|rewrite|formal|casual|summarize|make it|change it|add it)\b/i.test(lower)
  if (!referencesPrevious) return false

  if (/\b(copy|copy it|copy this|copy that|copy result|copy the draft)\b/i.test(lower)) {
    await window.ceaserDesktop.copyText(context.content)
    return showFollowUpResult("Copied", "Copied the last CEASER result.")
  }

  if (/\b(open|add|put|draft|compose).*\b(gmail|mail|email)\b|\b(gmail|mail|email).*\b(open|add|put|draft|compose)\b/i.test(lower)) {
    return openGmailDraft(context)
  }

  if (/\b(add|put|create).*\b(calendar|schedule)\b|\bcalendar\b.*\b(add|put|create)\b/i.test(lower)) {
    return openCalendarWithContext(context)
  }

  if (/\b(open|show|view).*\b(ceaser|console|app|files|document)\b|\bopen it\b/i.test(lower)) {
    await window.ceaserDesktop.openFullApp()
    return showFollowUpResult("Opened CEASER", "Opened CEASER so you can continue there.")
  }

  if (/\b(save|keep|remember)\b/i.test(lower)) {
    const saved = loadSavedResults()
    saved.unshift({
      id: `saved-${Date.now()}`,
      title: context.title || "Saved CEASER result",
      type: context.type,
      content: context.content,
      savedAt: new Date().toISOString(),
    })
    saveSavedResults(saved.slice(0, 50))
    return showFollowUpResult("Saved", "Saved the last CEASER result locally.")
  }

  if (/\b(shorten|make it shorter|summarize|formal|casual|friendly|professional|rewrite|change tone|improve)\b/i.test(lower)) {
    const transform = `${text}\n\nApply this to the previous CEASER result below. Return only the improved result.\n\nPrevious result:\n${context.content}`
    await answerQuestion({ intent: "answer_action", parameters: { question: transform } })
    return true
  }

  if (/\b(send|submit|delete|disconnect|clear)\b/i.test(lower)) {
    return showFollowUpResult("Confirmation needed", "For safety, I can prepare this on screen, but I will not send, delete, or submit it automatically.")
  }

  return false
}

function showFollowUpResult(title, message) {
  setMode("compact")
  setState("completed", title, message)
  resultTitle.textContent = title
  resultSummary.textContent = message
  setDynamicPanel("answer-card", `<h2>${escapeHtml(title)}</h2><p>${escapeHtml(message)}</p>`)
  speak(shortSpeech(message, 16), () => afterAssistantTurn())
  retractToCompact(2400)
  return true
}

async function showAuthRequired() {
  setMode("expanded")
  setState("idle", "Connect your account", "Link CEASER Desktop to continue.")
  resultTitle.textContent = "Connect your account"
  resultSummary.textContent = "Sign in securely through the CEASER web console."
  setDynamicPanel("answer-card", `
    <h2>Connect your CEASER account</h2>
    <p>Connect once to use AI answers, projects, files, memory, and integrations. Your session is stored securely on this device.</p>
    <button id="linkAccountButton" class="primary-action">Connect account</button>
  `)
  if (accountButton) accountButton.textContent = "Connect"
  window.setTimeout(() => {
    const button = document.getElementById("linkAccountButton")
    if (button) button.onclick = () => window.ceaserDesktop?.openAuth?.()
  }, 0)
  fitOverlay()
}

function isAuthError(response = {}) {
  const value = `${response?.error_code || ""} ${response?.context_kind || ""} ${response?.message || ""}`.toLowerCase()
  return /auth|session expired|reconnect|sign in|not connected/.test(value)
}

function friendlyCommandMessage(response = {}, fallback = "") {
  const status = String(response?.status || "").toLowerCase()
  const code = String(response?.error_code || response?.action_result?.error_code || "").toLowerCase()
  const raw = String(response?.message || response?.summary || fallback || "").trim()
  if (code.includes("unsupported") || response?.capability === "unsupported") {
    return "That action isn't available yet, but we're adding more controls."
  }
  if (code.includes("permission")) return "I need permission for that action before I can continue."
  if (code.includes("not_found")) return "I couldn't find what you asked for. Please check the name and try again."
  if (code.includes("offline") || code.includes("unavailable") || status === "unavailable") {
    return "CEASER is temporarily offline for that service. Please try again shortly."
  }
  if (status === "failed" || status === "error") {
    if (code.includes("ambiguous") || status === "needs_clarification") return raw
    return raw && !/^(action failed|command failed|error)$/i.test(raw) ? raw : "I couldn't complete that action this time. Try again in a moment."
  }
  return raw
}

async function showAuthRecovery(message = "") {
  setMode("expanded")
  setState("error", "Account connection needed", "Reconnect to continue using account features.")
  resultTitle.textContent = "Reconnect CEASER"
  resultSummary.textContent = "Your local desktop controls still work. Reconnect for AI and cloud features."
  setDynamicPanel("error-card", `
    <h2>Reconnect your account</h2>
    <p>${escapeHtml(message || "Your saved session is no longer valid. Sign in securely through the CEASER web console.")}</p>
    <button id="reconnectAccountButton" class="primary-action" type="button">Connect account</button>
  `)
  document.getElementById("reconnectAccountButton")?.addEventListener("click", () => window.ceaserDesktop?.openAuth?.())
  if (accountButton) accountButton.textContent = "Connect"
  fitOverlay()
}

async function showMicCalibration() {
  setMode("expanded")
  setState("working", "Voice engine check", "Python owns microphone capture.")
  resultTitle.textContent = "Voice Engine"
  resultSummary.textContent = "Checking Python companion status."
  setDynamicPanel("answer-card", `
    <h2>Python Voice Engine</h2>
    <p>Electron no longer captures microphone audio. CEASER voice runs through the Python companion.</p>
  `)
  fitOverlay()
  try {
    const status = await window.ceaserDesktop?.pythonVoiceStatus?.()
    setState(status?.ready ? "completed" : "working", status?.ready ? "Voice engine ready" : "Voice engine loading", status?.ready ? "Say Hey CEASER after pressing the hotkey." : "Keep CEASER open for a moment.")
  } catch (error) {
    setState("error", "Voice engine unavailable", "Restart CEASER and check Python runtime.")
    resultSummary.textContent = error.message || "Python voice engine could not be reached."
  }
}

function loadSavedResults() {
  try {
    return JSON.parse(window.localStorage.getItem("ceaser:savedResults") || "[]")
  } catch (_error) {
    return []
  }
}

function saveSavedResults(items) {
  try {
    window.localStorage.setItem("ceaser:savedResults", JSON.stringify(items))
  } catch (_error) {
    // Best effort local save.
  }
}

async function openGmailDraft(context) {
  const { subject, body, to } = parseEmailDraft(context)
  const url = new URL("https://mail.google.com/mail/")
  url.searchParams.set("view", "cm")
  url.searchParams.set("fs", "1")
  if (to) url.searchParams.set("to", to)
  if (subject) url.searchParams.set("su", subject)
  url.searchParams.set("body", body || context.content)
  await window.ceaserDesktop.openUrl(url.toString())
  return showFollowUpResult("Gmail draft opened", "I opened Gmail compose with the draft filled in. Review it before sending.")
}

function parseEmailDraft(context) {
  const content = String(context?.content || "")
  const subjectMatch = content.match(/(?:^|\n)\s*(?:subject|sub)\s*:\s*(.+)/i)
  const toMatch = content.match(/(?:^|\n)\s*(?:to|recipient)\s*:\s*([^\n]+)/i)
  const body = content
    .replace(/(?:^|\n)\s*(?:subject|sub)\s*:\s*.+/ig, "")
    .replace(/(?:^|\n)\s*(?:to|recipient)\s*:\s*[^\n]+/ig, "")
    .trim()
  return {
    subject: subjectMatch?.[1]?.trim() || context.title || "CEASER draft",
    to: toMatch?.[1]?.trim() || "",
    body: body || content,
  }
}

async function openCalendarWithContext(context) {
  const details = String(context.content || "").slice(0, 1800)
  const url = new URL("https://calendar.google.com/calendar/render")
  url.searchParams.set("action", "TEMPLATE")
  url.searchParams.set("text", context.title || "CEASER item")
  url.searchParams.set("details", details)
  await window.ceaserDesktop.openUrl(url.toString())
  return showFollowUpResult("Calendar opened", "I opened Google Calendar with the details. Review the date and time before saving.")
}

function timeGreeting() {
  const hour = new Date().getHours()
  if (hour < 12) return "Good morning"
  if (hour < 17) return "Good afternoon"
  if (hour < 21) return "Good evening"
  return "Hello"
}

function assistantGreeting() {
  return `${timeGreeting()}, ${displayNameFromUser(linkedUser)}. I'm listening.`
}

function wakeGreeting() {
  return `${timeGreeting()}. I'm listening.`
}

async function playStartupGreeting() {
  if (personalizedGreetingPlayed) return
  const auth = await window.ceaserDesktop?.getAuthStatus?.().catch(() => null)
  applyLinkedUser(auth)
  if (personalizedGreetingPlayed || voiceSession || listeningActive || speakingActive) return
  personalizedGreetingPlayed = true
  const name = displayNameFromUser(linkedUser)
  const greeting = name
    ? `${timeGreeting()}, ${name}. CEASER is ready.`
    : `${timeGreeting()}. CEASER is ready.`
  console.log(`[CEASER] Startup greeting: ${greeting}`)
  speak(greeting)
}

async function waitForPythonReady(timeoutMs = 5000) {
  const status = await window.ceaserDesktop?.pythonVoiceStatus?.().catch(() => null)
  if (status?.ready) return true
  return new Promise((resolve) => {
    let done = false
    const finish = (ready) => {
      if (done) return
      done = true
      cleanup?.()
      window.clearTimeout(timer)
      resolve(ready)
    }
    const cleanup = window.ceaserDesktop?.onPythonReady?.(() => finish(true))
    const timer = window.setTimeout(async () => {
      const latest = await window.ceaserDesktop?.pythonVoiceStatus?.().catch(() => null)
      finish(Boolean(latest?.ready))
    }, timeoutMs)
  })
}

async function startAssistantSession() {
  console.log("[CEASER] Hotkey voice session starting")
  window.clearTimeout(hideTimer)
  window.clearTimeout(restartListenTimer)
  voiceCommandGeneration += 1
  passiveWakeLoopRunning = false
  passiveWakeLoopOwner = null
  assistantSessionActive = true
  pendingIntent = null
  confirmationCard.classList.add("hidden")
  setMode("compact")
  renderSteps([])
  alwaysListenActive = WAKE_WORD_LISTENING_ENABLED
  setState("working", "Preparing CEASER", "Starting microphone.")
  resultTitle.textContent = "Voice session active"
  resultSummary.textContent = "Preparing packages and voice services."
  const ready = await waitForPythonReady(5000)
  if (!ready) {
    setState("working", "Still preparing", "CEASER is loading voice modules. Keep this open for a moment.")
    await waitForPythonReady(60000)
  }
  if (!assistantSessionActive) return
  console.log("[CEASER] Python ready; entering direct hotkey command listening")
  await startPythonVoiceCommand({ source: "hotkey", singleCommand: true })
}

function endAssistantSession(message = "Goodbye. CEASER is going silent.") {
  assistantSessionActive = false
  passiveListening = false
  window.clearTimeout(restartListenTimer)
  stopVoiceCommand()
  pendingIntent = null
  confirmationCard.classList.add("hidden")
  setState("completed", "Going silent", message)
  resultTitle.textContent = "Session ended"
  resultSummary.textContent = message
  speak(message, () => {
    // Goodbye is the one intentional hide. The global hotkey always summons
    // this same overlay again for the next request.
    window.ceaserDesktop?.hideOverlay?.({ force: true })
    setState("idle", "CEASER ready", "Say Hey CEASER when you need me.")
  })
}

function schedulePassiveListening(delay = 450) {
  window.clearTimeout(restartListenTimer)
  if (!WAKE_WORD_LISTENING_ENABLED) return
  if (!assistantSessionActive && !alwaysListenActive) return
  restartListenTimer = window.setTimeout(() => startPassiveWakeLoop(), delay)
}

function afterAssistantTurn() {
  window.clearTimeout(restartListenTimer)
  if (assistantSessionActive) {
    setState("listening", "Listening...", "Tell me your next command.")
    restartListenTimer = window.setTimeout(() => {
      if (assistantSessionActive && !listeningActive && !speakingActive) {
        startPythonVoiceCommand({ source: "follow_up", singleCommand: true, noPassiveRestart: true })
      }
    }, 300)
    return
  }
  setState("idle", "CEASER ready", "Press the hotkey or type a command.")
}

async function handleVoiceTranscript(command, options = {}) {
  const cleaned = String(command || "").trim()
  if (options.holdToTalk) {
    if (!cleaned) {
      holdVoiceActive = false
      holdVoiceSessionId = null
      holdVoiceContext = null
      setState("idle", "I did not catch that", "Say Hey CEASER and try again.")
      window.setTimeout(() => window.ceaserDesktop?.hideOverlay?.(), 1000)
      return
    }
    commandInput.value = cleaned
    await runCommand(cleaned.replace(/^(hey\s+)?(?:ceaser|caesar|cesar|seizer|sizer|scissor|season)[,.\s-]*/i, ""))
    holdVoiceActive = false
    holdVoiceSessionId = null
    holdVoiceContext = null
    return
  }
  if (!cleaned) {
    if (options.singleCommand) {
      setState("idle", "I did not catch that", "Say Hey CEASER and try again.")
      window.setTimeout(() => window.ceaserDesktop?.hideOverlay?.(), 1200)
      return
    }
    if (options.requireWakeWord) {
      schedulePassiveListening(900)
      return
    }
    if (assistantSessionActive) {
      setState("idle", "I did not catch that", "Say Hey CEASER and speak clearly.")
      schedulePassiveListening(700)
    } else {
      setState("error", "No command heard", "Try again and speak clearly.")
    }
    return
  }

  if (assistantSessionActive && EXIT_SESSION_PATTERN.test(cleaned)) {
    endAssistantSession()
    return
  }

  if (pendingIntent?.requires_confirmation || pendingIntent?.permission) {
    await runCommand(cleaned)
    return
  }

  if (options.requireWakeWord) {
    const extracted = extractWakeCommand(cleaned)
    if (!extracted.woke) {
      schedulePassiveListening(900)
      return
    }
    commandInput.value = extracted.command || cleaned
    if (!extracted.command) {
      setState("listening", "Listening...", "Tell me what you need.")
      speak(wakeGreeting(), () => {
        if (assistantSessionActive) startVoiceCommand({ passive: true, requireWakeWord: false })
      })
      return
    }
    await runCommand(extracted.command)
    return
  }

  commandInput.value = cleaned
  await runCommand(cleaned)
}

function extractWakeCommand(command) {
  const source = String(command || "").replace(/\s+/g, " ").trim()
  const match = source.match(WAKE_WORD_PATTERN)
  if (!match || match.index === undefined) return { woke: false, command: "" }
  const before = source.slice(0, match.index).trim()
  const after = source.slice(match.index + match[0].length).replace(/^[,.:;\-\s]+/, "").trim()
  const ignoredPrefixes = /^(please|can you|could you|would you)\s+/i
  const cleanedAfter = after.replace(ignoredPrefixes, "").trim()
  const cleanBefore = before.replace(ignoredPrefixes, "").trim()
  const beforeLooksLikeCommand = cleanBefore && !/^(hey|hi|hello|ok|okay|a)$/i.test(cleanBefore) && isPassiveCommandLike(cleanBefore)
  return { woke: true, command: cleanedAfter || (beforeLooksLikeCommand ? cleanBefore : "") }
}

function normalizeSpokenCommand(command) {
  let cleaned = String(command || "").replace(/\s+/g, " ").trim()
  if (!cleaned) return ""
  cleaned = cleaned
    .replace(/^(?:hey|hi|hello|ok|okay)\s+(?:ceaser|cesaer|caesar|cesar|seizer|sizer|sizzer|scissor|season|procedure|precision|see\s*sir|sea\s*sir|google|siri|alexa)\b[,\s]*/i, "")
    .replace(/^(?:ceaser|cesaer|caesar|cesar|seizer|sizer|sizzer|scissor|season|procedure|precision|see\s*sir|sea\s*sir|google|siri|alexa)\b[,\s]*/i, "")
    .trim()
  cleaned = cleaned
    .replace(/\b(?:paper|people|pepper|paypal)\s+pause\s+(?:the\s+)?(?:music|song|track)\b/i, "pause music")
    .replace(/\b(?:paper|people|pepper|paypal)\s+play\s+(?:the\s+)?(?:music|song|track)\b/i, "play music")
    .replace(/\b(?:pause|stop)\s+(?:the\s+)?(?:song|track|audio)\b/i, "pause music")
    .replace(/\b(?:resume|continue)\s+(?:the\s+)?(?:song|track|audio|music)\b/i, "resume music")
    .replace(/\b(?:skip|next)\s+(?:the\s+)?(?:song|track|audio|music)\b/i, "next music")
    .replace(/\b(?:previous|last|back)\s+(?:the\s+)?(?:song|track|audio|music)\b/i, "previous music")
    .replace(/\b(?:screen\s*capture|capture\s+(?:the\s+)?screen|grab\s+(?:the\s+)?screen|take\s+a\s+screen\s*shot)\b/i, "take screenshot")
    .replace(/\b(?:go to|visit|browse to|open website|open site)\s+/i, "open ")
    .replace(/\b(?:compose|draft|prepare|send|write)\s+(?:a\s+)?(?:mail|message|gmail)\b/i, "write email")
    .replace(/\b(?:which|show|list)\s+(?:are\s+)?(?:my\s+)?projects\b/i, "what projects do I have")
    .replace(/\b(?:who am i|my profile|account details|signed in account)\b/i, "what is my account")
  const openKaro = cleaned.match(/^(.+?)\s+(?:open|launch|start|run)\s+(?:karo|kar do|please)?$/i)
  if (openKaro?.[1]) return `open ${openKaro[1].trim()}`
  const playKaro = cleaned.match(/^(.+?)\s+play\s+(?:karo|kar do|please)?$/i)
  if (playKaro?.[1]) return `play ${playKaro[1].trim()}`
  cleaned = cleaned
    .replace(/^(?:open up|bring up|show me|show|start|launch|run)\s+/i, "open ")
    .replace(/\b(?:hey\s+)?ceaser\s*(?:dot|point)\s*(?:tech|in)\b/i, "heyceaser.in")
    .replace(/\bcaesar\s*(?:dot|point)\s*(?:tech|in)\b/i, "heyceaser.in")
    .replace(/\bcesar\s*(?:dot|point)\s*(?:tech|in)\b/i, "heyceaser.in")
  return cleaned
}

function isPassiveCommandLike(command) {
  const normalized = normalizeSpokenCommand(command).toLowerCase()
  return /\b(open|launch|start|run|play|pause|resume|continue|stop|next|skip|previous|back|search|find|tell|explain|summarize|summarise|read|analyze|analyse|write|draft|compose|mail|message|generate|create|make|copy|save|show|check|list|visit|browse|website|site|what|who|why|how|weather|time|date|news|email|gmail|word|chrome|settings|calculator|facebook|youtube|projects?|files?|documents?|memory|name|profile|account|screenshot|capture|volume|mute)\b/.test(normalized)
}

function isLikelyFullCommand(command) {
  const normalized = normalizeSpokenCommand(command).toLowerCase()
  const words = normalized.split(/\s+/).filter(Boolean)
  if (words.length < 4) return false
  return /^(open|launch|start|run|play|pause|resume|search|find|tell|explain|summarize|summarise|read|analyze|analyse|write|draft|compose|generate|create|make|show|check|list|what|who|why|how|visit|browse)\b/.test(normalized)
    || /\b(email|mail|message|gmail|document|report|project|projects|file|files|memory|weather|news|calendar|meeting|quantum|computing|music|song|website|site|profile|account|screenshot|screen)\b/.test(normalized)
}

function startTask(intent, type) {
  const task = {
    id: `task_${Date.now()}_${taskCounter += 1}`,
    type,
    intent,
    command: intent.parameters?.message || intent.parameters?.question || "",
    status: "running",
    agent: intent.active_agent || "CEASER",
    startedAt: new Date().toISOString(),
  }
  activeTask = task
  activeAgent.textContent = task.agent
  intentType.textContent = `${type} running`
  resultStats.innerHTML = ""
  renderStats([`Task: ${task.id.split("_").slice(-1)[0]}`])
  return task
}

function isCurrentTask(task) {
  return activeTask?.id === task.id
}

function finishActiveTask() {
  if (activeTask) {
    renderStats(["Completed"])
  }
  activeTask = null
}

async function handleConfirmationCommand(command) {
  if (!pendingIntent?.requires_confirmation && !pendingIntent?.permission) return false
  if (isCancelCommand(command)) {
    pendingIntent = null
    confirmationCard.classList.add("hidden")
    setState("idle", "Cancelled", "No action was taken.")
    speak("Cancelled.")
    return true
  }
  if (!isConfirmCommand(command)) return false
  if (pendingIntent.permission) {
    await window.ceaserDesktop.setPermission(pendingIntent.permission, true)
  }
  const intent = { ...pendingIntent, confirmed: true }
  pendingIntent = null
  confirmationCard.classList.add("hidden")
  executeIntent(intent)
  return true
}

function isConfirmCommand(command) {
  return /\b(confirm|yes|yeah|yep|do it|continue|proceed|allow|approve|ok|okay)\b/i.test(command)
}

function isCancelCommand(command) {
  return /\b(cancel|no|stop|dont|don't|abort|never mind|nevermind)\b/i.test(command)
}

function setVoiceButtonState(active) {
  listeningActive = active
}

function cleanupRecording() {
  stopRecordingResources()
  voiceSession = null
}

function stopRecordingResources() {
  if (silenceFrame) {
    window.cancelAnimationFrame(silenceFrame)
    silenceFrame = null
  }
  if (autoStopTimer) {
    window.clearTimeout(autoStopTimer)
    autoStopTimer = null
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop())
  }
  mediaStream = null
  audioContext?.close?.()
  audioContext = null
  pendingHoldStop = false
  stoppingVoice = false
}

function stopVoiceCommand() {
  if (!listeningActive) return
  if (stoppingVoice) return
  const listenedFor = Date.now() - (voiceSession?.startedAt || Date.now())
  const minListenMs = voiceSession?.options?.holdToTalk ? 260 : 3200
  if (listenedFor < minListenMs) {
    window.setTimeout(() => stopVoiceCommand(), minListenMs - listenedFor)
    return
  }
  stoppingVoice = true
  setVoiceButtonState(false)
  if (recorder?.state === "recording") recorder.stop()
  else cleanupRecording()
}

function resetAfterVoiceMiss(title = "I did not catch that", message = "Say Hey CEASER and try again.") {
  setVoiceButtonState(false)
  restoreMediaAfterListening("voice-miss")
  setMode("compact")
  setState("idle", title, message)
  window.setTimeout(() => {
    commandInput.value = ""
    setState("idle", "CEASER ready", "Say Hey CEASER when you need me.")
    if (alwaysListenActive) startPassiveWakeLoop()
    else window.ceaserDesktop?.hideOverlay?.()
    window.ceaserDesktop?.hideOverlay?.()
  }, 1800)
}

function stopAlwaysListenSession(message = "CEASER voice is resting.") {
  alwaysListenActive = false
  assistantSessionActive = false
  passiveWakeLoopRunning = false
  passiveWakeLoopOwner = null
  setVoiceButtonState(false)
  setMode("compact")
  setState("completed", "Going silent", message)
  speak(message, () => {
    window.ceaserDesktop?.hideOverlay?.()
  })
}

async function executePythonTextCommand(text, options = {}) {
  const command = normalizeSpokenCommand(text)
  if (!command) return null
  if (speakingActive || window.speechSynthesis?.speaking || window.speechSynthesis?.pending) stopCurrentSpeech("new-command")
  if (isSpeechStopCommand(command)) {
    stopCurrentSpeech("python-text-command")
    return { status: "cancelled", message: "Stopped speaking.", context_kind: "desktop_action" }
  }
  console.log("[CEASER] Python text command requested")
  return window.ceaserDesktop.pythonVoiceCommand?.({
    version: "2.0",
    type: "execute_command",
    payload: {
      source: options.source || "typed",
      text: command,
      session_id: options.sessionId || "overlay_typed",
      context: options.context || {},
    },
  })
}

async function startPassiveWakeLoop() {
  if (!WAKE_WORD_LISTENING_ENABLED) return
  if (!alwaysListenActive || passiveWakeLoopRunning) return
  const loopGeneration = voiceCommandGeneration
  const loopOwner = Symbol("passive-wake-loop")
  passiveWakeLoopOwner = loopOwner
  let lastWakeRequestAt = 0
  console.log("[CEASER] Python wake-command loop starting")
  passiveWakeLoopRunning = true
  while (alwaysListenActive) {
    try {
      if (passiveWakeLoopOwner !== loopOwner || loopGeneration !== voiceCommandGeneration) break
      if (voiceSession || speakingActive || window.speechSynthesis?.speaking || window.speechSynthesis?.pending) {
        await new Promise((resolve) => window.setTimeout(resolve, 250))
        continue
      }
      const now = Date.now()
      const sinceLastWakeRequest = now - lastWakeRequestAt
      if (sinceLastWakeRequest < 900) {
        await new Promise((resolve) => window.setTimeout(resolve, 900 - sinceLastWakeRequest))
      }
      console.log("[CEASER] Python owns wake listening")
      lastWakeRequestAt = Date.now()
      await duckMediaForListening("python-wake-command")
      const response = await window.ceaserDesktop.pythonVoiceCommand?.({
        type: "listen_wake_command",
        persistent_command_mode: true,
        payload: { persistent_command_mode: true },
      })
      await restoreMediaAfterListening("python-command-complete")
      if (loopGeneration !== voiceCommandGeneration) break
      if (!alwaysListenActive) break
      if ((response?.status === "wake_listening" || response?.recoverable) && !String(response?.transcript || "").trim()) {
        console.log("[CEASER] Wake listener returned without speech; delaying degraded restart", response?.reason || response?.voice_control || "")
        window.ceaserDesktop?.hideOverlay?.()
        await new Promise((resolve) => window.setTimeout(resolve, 4000))
        continue
      }
      await window.ceaserDesktop?.showOverlay?.()
      await renderPythonCommandResult(response?.transcript || "", response || { status: "empty", message: "No command heard." }, { fromWake: true })
    } catch (error) {
      console.warn("[CEASER] Python wake loop paused:", error.message || error)
      await restoreMediaAfterListening("wake-listen-error")
      await new Promise((resolve) => window.setTimeout(resolve, 1000))
    }
  }
  if (passiveWakeLoopOwner === loopOwner) {
    passiveWakeLoopOwner = null
    passiveWakeLoopRunning = false
  }
}

async function renderPythonCommandResult(transcript, response, options = {}) {
  const command = String(transcript || response?.transcript || "").trim()
  response = await resolveIndexedAppFollowUp(command, response)
  response = await recoverApplicationLaunch(command, response)
  response = await recoverApplicationClose(command, response)
  const message = cleanOverlayText(friendlyCommandMessage(response, ""))
  if (response?.status === "resting") {
    stopAlwaysListenSession(message || "CEASER is going silent.")
    return
  }
  if (!command || response?.status === "empty") {
    resetAfterVoiceMiss("I did not catch that", message || "Please repeat the command.")
    return
  }
  if (REST_SESSION_PATTERN.test(command)) {
    stopAlwaysListenSession()
    return
  }
  commandInput.value = command
  lastCommand = command
  updateTrackedMediaState(command, response)
  if (response?.status === "needs_clarification") {
    const matches = Array.isArray(response.matches) ? response.matches.slice(0, 5) : []
    if (response?.recovered_by === "desktop_app_index" && matches.length) {
      window.sessionStorage.setItem("ceaser_pending_indexed_apps", JSON.stringify({ matches, expires_at: Date.now() + 40000 }))
    }
    setState("completed", "Choose an app", message || "I found more than one matching app.")
    resultTitle.textContent = "Choose an app"
    resultSummary.textContent = message || "I found more than one matching app."
    setDynamicPanel("answer-card", `
      <h2>Choose an app</h2>
      <p>${escapeHtml(message || "I found more than one matching app.")}</p>
      ${matches.length ? `<div class="choice-list">${matches.map((item) => `<button type="button" class="choice-pill" data-choice="${escapeHtml(item.name || "")}">${escapeHtml(item.name || "Unknown app")}</button>`).join("")}</div>` : ""}
    `)
    dynamicPanel?.querySelectorAll?.(".choice-pill")?.forEach((button) => {
      button.addEventListener("click", () => runCommand(`open ${button.dataset.choice || ""}`))
    })
    renderStats(["Needs clarification", `${matches.length} matches`])
    fitOverlay()
    speak("I found more than one app. Please choose one on screen.", () => afterAssistantTurn())
    return
  }
  const ok = response?.status !== "error"
  if (!ok && isAuthError(response)) {
    await showAuthRecovery(message)
    return
  }
  const title = ok ? "Completed" : "Action failed"
  const keepVisible = ok && shouldKeepOutputVisible(message || command, { action: "python_companion", parameters: { message: command } })
  if (keepVisible) {
    renderStickyOutput(title, message || command, { action: "python_companion", parameters: { message: command } }, response || {})
  } else {
    setState(ok ? "completed" : "error", title, message || command)
    resultTitle.textContent = title
    resultSummary.textContent = message || command
    setDynamicPanel(ok ? "answer-card" : "error-card", `<h2>${escapeHtml(title)}</h2><p>${escapeHtml(message || command)}</p>`)
  }
  captureResultContext({ action: "python_companion", parameters: { message: command } }, response || {}, message)
  renderStats(["Python Companion", `STT: ${response?.stt_provider || "unknown"}`])
  fitOverlay()
  const spoken = speechSafeText(message || response?.spoken_response || (ok ? "Done." : "I could not complete that."))
  if (spoken) {
    logSpokenResponse(command, spoken, response)
    speak(spoken, () => afterAssistantTurn())
  }
  else {
    restoreMediaAfterListening("no-spoken-response")
    afterAssistantTurn()
  }
  if (ok && !keepVisible) {
    retractToCompact()
  }
}

async function recoverApplicationLaunch(command, response = {}) {
  if (response?.status !== "error" || response?.capability !== "desktop.open_application") return response
  const match = String(command || "").match(/^\s*(?:open|launch|start|run|switch\s+to|focus)\s+(.+?)\s*$/i)
  if (!match || !window.ceaserDesktop?.appAction) return response
  let target = match[1].trim()
  const profile = target.match(/^(?:google\s+)?chrome\s+(?:with|using|in)\s+(?:the\s+)?(.+?)\s+profile$/i)
  if (profile) target = "Chrome"
  console.warn(`[CEASER] Python app lookup missed "${target}"; using indexed desktop launcher`)
  const recovered = await window.ceaserDesktop.appAction({
    action: "open",
    app: target,
    profile_name: profile?.[1] || "",
    force_new: /\bnew\s+(?:window|instance)\b/i.test(command),
  })
  return recovered ? { ...response, ...recovered, capability: "desktop.open_application", recovered_by: "desktop_app_index" } : response
}

async function recoverApplicationClose(command, response = {}) {
  if (!['error', 'failed', 'needs_clarification'].includes(String(response?.status || '').toLowerCase())) return response
  const match = String(command || "").match(/^\s*(?:close|quit|exit|terminate|kill)\s+(?!.*\btab\b)(?:the\s+)?(.+?)(?:\s+(?:app|application))?\s*$/i)
  if (!match || !window.ceaserDesktop?.appAction) return response
  const target = match[1].trim()
  console.warn(`[CEASER] Python app close did not resolve "${target}"; checking live Windows applications`)
  const recovered = await window.ceaserDesktop.appAction({ action: "close", app: target })
  return recovered?.status === "completed"
    ? { ...response, ...recovered, capability: "desktop.close_application", recovered_by: "live_windows_app_index" }
    : response
}

async function resolveIndexedAppFollowUp(command, response = {}) {
  let pending
  try {
    pending = JSON.parse(window.sessionStorage.getItem("ceaser_pending_indexed_apps") || "null")
  } catch (_error) {
    pending = null
  }
  if (!pending?.matches?.length || Number(pending.expires_at || 0) < Date.now()) {
    window.sessionStorage.removeItem("ceaser_pending_indexed_apps")
    return response
  }
  const choice = String(command || "").trim().toLowerCase()
  const ordinal = { first: 0, one: 0, "1": 0, second: 1, two: 1, "2": 1, third: 2, three: 2, "3": 2, fourth: 3, four: 3, "4": 3 }[choice]
  const selected = ordinal !== undefined
    ? pending.matches[ordinal]
    : pending.matches.find((item) => choice === String(item.name || "").toLowerCase() || String(item.name || "").toLowerCase().includes(choice))
  if (!selected || !window.ceaserDesktop?.appAction) return response
  window.sessionStorage.removeItem("ceaser_pending_indexed_apps")
  const result = await window.ceaserDesktop.appAction({ action: "open", app: selected.name })
  return { ...response, ...result, capability: "desktop.open_application", recovered_by: "desktop_app_choice" }
}

function updateTrackedMediaState(command, response = {}) {
  if (response?.status === "error" || response?.status === "failed") return
  const text = String(command || "").trim().toLowerCase()
  if (/^(?:pause|stop)(?:\s+(?:the\s+)?(?:music|song|track|media|playback))?$/.test(text)) {
    mediaPlaybackExpected = false
  } else if (/^(?:play|resume|continue)(?:\s|$)/.test(text) || response?.context_kind === "music") {
    mediaPlaybackExpected = true
  } else {
    return
  }
  window.localStorage.setItem("ceaser_media_playback_expected", String(mediaPlaybackExpected))
  console.log(`[CEASER] Media playback tracking: ${mediaPlaybackExpected ? "playing" : "inactive"}`)
}

function speechSafeText(value) {
  return String(value || "")
    .replace(/```[\s\S]*?```/g, " Code example available on screen. ")
    .replace(/https?:\/\/\S+/g, "")
    .replace(/[*#_`>|~]+/g, " ")
    .replace(/\[([^\]]+)\]\([^\)]+\)/g, "$1")
    .replace(/\s+/g, " ")
    .trim()
}

function detectDroppedFile(file) {
  const name = file?.name || "Dropped file"
  const ext = name.includes(".") ? name.split(".").pop().toLowerCase() : ""
  const typeMap = {
    pdf: "PDF",
    docx: "Word Document",
    doc: "Word Document",
    pptx: "PowerPoint",
    ppt: "PowerPoint",
    xlsx: "Excel Spreadsheet",
    xls: "Excel Spreadsheet",
    csv: "CSV Spreadsheet",
    txt: "Text Document",
    md: "Markdown Document",
    png: "Image",
    jpg: "Image",
    jpeg: "Image",
    gif: "Image",
    webp: "Image",
    zip: "ZIP Archive",
  }
  return {
    name,
    type: typeMap[ext] || "File",
    ext,
    size: file?.size || 0,
    seconds: file?.size > 6_000_000 ? 8 : 4,
  }
}

function renderSmartCaptureDrop(file) {
  const info = detectDroppedFile(file)
  setMode("expanded")
  setState("listening", "Drop to Analyze", info.name)
  setDynamicPanel("smart-capture-drop", `
    <div class="capture-zone">
      <div class="capture-icon">+</div>
      <h2>Drop to Analyze</h2>
      <p>${escapeHtml(info.name)}</p>
      <div class="capture-meta">
        <span>${escapeHtml(info.type)}</span>
        <span>${formatBytes(info.size)}</span>
        <span>~${info.seconds}s</span>
      </div>
      <div class="capture-actions">
        <span>Summarize</span><span>Explain</span><span>Ask Questions</span><span>Create Notes</span>
      </div>
    </div>
  `)
}

function renderSmartCaptureProgress(stage = "Scanning Document...", progress = 12, fileName = "") {
  setMode("expanded")
  setState("thinking", stage, fileName || "Smart Capture")
  setDynamicPanel("smart-capture-progress", `
    <div class="capture-scanner">
      <h2>${escapeHtml(stage)}</h2>
      <p>${escapeHtml(fileName || "Reading your file")}</p>
      <div class="scanner-frame"><span></span></div>
      <div class="capture-progress"><span style="width:${Math.max(5, Math.min(Number(progress) || 0, 100))}%"></span></div>
      <ul>
        <li>Reading...</li>
        <li>Extracting text...</li>
        <li>Understanding structure...</li>
        <li>Finding key topics...</li>
        <li>Preparing summary...</li>
      </ul>
    </div>
  `)
}

function renderSmartCaptureReady(response = {}) {
  const file = response.file || {}
  const capture = response.capture || {}
  const message = cleanOverlayText(response.message || capture.summary || "")
  const actions = Array.isArray(capture.actions) && capture.actions.length
    ? capture.actions
    : ["Summary", "Topics", "Questions", "Timeline", "Explain", "Translate"]
  setMode("expanded")
  setState("completed", "Smart Capture Ready", file.name || "File analyzed")
  resultTitle.textContent = "Smart Capture"
  resultSummary.textContent = message
  setDynamicPanel("smart-capture-ready", `
    <div class="capture-ready-head">
      <span class="capture-file-type">${escapeHtml(file.type || "File")}</span>
      <h2>${escapeHtml(file.name || "Analyzed file")}</h2>
      <p>${escapeHtml(formatBytes(file.size || 0))}</p>
    </div>
    <div class="capture-checks">
      <span>Summary</span><span>Key Topics</span><span>Important Dates</span><span>People</span><span>Action Items</span>
    </div>
    <div class="capture-summary">${escapeHtml(message).replace(/\n/g, "<br>")}</div>
    <div class="capture-action-row">
      ${actions.map((item) => `<button type="button" class="capture-action" data-action="${escapeHtml(item)}">${escapeHtml(item)}</button>`).join("")}
    </div>
  `)
  dynamicPanel?.querySelectorAll?.(".capture-action")?.forEach((button) => {
    button.addEventListener("click", () => {
      const action = button.dataset.action || "Summary"
      executePythonTextCommand(`${action} this document`).then((res) => renderPythonCommandResult(`${action} this document`, res))
    })
  })
  captureResultContext({ action: "smart_capture", parameters: { message: file.name || "Dropped file" } }, response, message)
  speak("I've finished analyzing the file. The key details are on screen.", () => afterAssistantTurn())
}

async function analyzeDroppedFile(file) {
  const filePath = window.ceaserDesktop?.filePath?.(file) || file?.path || file?.webkitRelativePath || ""
  if (!filePath) {
    setState("error", "File path unavailable", "Please drag the file from File Explorer.")
    return
  }
  const contextResult = await window.ceaserDesktop?.registerFileContext?.(filePath)
  if (contextResult?.status !== "selected") {
    setState("error", "File not supported", "I can't read that file type yet, but we're adding support for more formats.")
    return
  }
  selectedDesktopFileContext = contextResult.desktop_file_context
  smartCaptureActive = true
  renderSmartCaptureProgress("Scanning Document...", 12, file.name)
  try {
    const response = await window.ceaserDesktop.pythonVoiceCommand?.({ type: "analyze_file", path: filePath })
    if (response?.status === "completed") renderSmartCaptureReady(response)
    else renderPythonCommandResult(`analyze ${file.name}`, response || { status: "error", message: "Smart Capture failed." })
  } catch (error) {
    renderPythonCommandResult(`analyze ${file.name}`, { status: "error", message: "Smart Capture failed." })
  } finally {
    smartCaptureActive = false
  }
}

function formatBytes(value) {
  const size = Number(value) || 0
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

async function startPythonVoiceCommand(options = {}) {
  voiceCommandGeneration += 1
  passiveWakeLoopRunning = false
  passiveWakeLoopOwner = null
  if (listeningActive) {
    setVoiceButtonState(false)
    voiceSession = null
  }
  window.clearTimeout(hideTimer)
  window.clearTimeout(retractTimer)
  if (speakingActive || window.speechSynthesis?.speaking || window.speechSynthesis?.pending) stopCurrentSpeech("hotkey")
  cleanupRecording()
  alwaysListenActive = WAKE_WORD_LISTENING_ENABLED
  assistantSessionActive = true
  const session = {
    id: `python_voice_${Date.now()}`,
    startedAt: Date.now(),
    options: { ...options, singleCommand: true },
  }
  if (session.options.holdToTalk) {
    holdVoiceActive = true
    holdVoiceSessionId = session.options.sessionId || session.id
    holdVoiceContext = session.options.context || null
  }
  voiceSession = session
  setVoiceButtonState(true)
  setMode("compact")
  setState("listening", "Listening...", "Speak your command now.")
  try {
    console.log("[CEASER] Python voice command requested")
    if (!options.mediaAlreadyDucked) await duckMediaForListening(options.fromWake ? "wake-command" : "hotkey-command")
    const response = await window.ceaserDesktop.pythonVoiceCommand?.({
      type: "listen_wake_command",
      persistent_command_mode: true,
      payload: {
        persistent_command_mode: true,
        context: options.context || null,
      },
    })
    if (voiceSession?.id !== session.id) return
    setVoiceButtonState(false)
    voiceSession = null
    const heard = String(response?.transcript || "").trim()
    const wakeOnly = extractWakeCommand(heard)
    if (wakeOnly.woke && !wakeOnly.command && !options.secondListen) {
      setState("listening", "Listening...", "Tell me your command.")
      await startPythonVoiceCommand({ ...options, secondListen: true, noPassiveRestart: true, mediaAlreadyDucked: true })
      return
    }
    if (wakeOnly.woke && wakeOnly.command) {
      response.transcript = normalizeSpokenCommand(wakeOnly.command)
    }
    await renderPythonCommandResult(response?.transcript, response, session.options)
  } catch (error) {
    console.error("[CEASER] Python voice failed:", error.message || error)
    setVoiceButtonState(false)
    voiceSession = null
    restoreMediaAfterListening("voice-error")
    if (/timed out/i.test(String(error?.message || error))) {
      setState("idle", "Listening reset", "Press the hotkey and speak again.")
      if (WAKE_WORD_LISTENING_ENABLED && assistantSessionActive && !options.noPassiveRestart) {
        alwaysListenActive = true
        startPassiveWakeLoop()
      }
      return
    }
    resetAfterVoiceMiss("Voice unavailable", "Python companion could not start.")
  }
}

async function prepareVoiceInput() {
  console.log("[CEASER] Python voice input owns microphone")
  return usesPythonVoice()
}

function monitorSilence(stream) {
  if (holdVoiceActive) return
  const AudioContextClass = window.AudioContext || window.webkitAudioContext
  autoStopTimer = window.setTimeout(() => stopVoiceCommand(), 22000)
  if (!AudioContextClass) return
  audioContext = new AudioContextClass()
  const analyser = audioContext.createAnalyser()
  analyser.fftSize = 1024
  audioContext.createMediaStreamSource(stream).connect(analyser)
  const data = new Uint8Array(analyser.frequencyBinCount)
  const startedAt = Date.now()
  let speechStarted = false
  let lastVoiceAt = startedAt
  let speechFrames = 0

  const tick = () => {
    analyser.getByteTimeDomainData(data)
    let sum = 0
    for (const value of data) {
      const centered = (value - 128) / 128
      sum += centered * centered
    }
    const level = Math.sqrt(sum / data.length)
    const now = Date.now()
    if (level > 0.01) {
      speechFrames += 1
      if (speechFrames >= 2) speechStarted = true
      lastVoiceAt = now
    } else if (!speechStarted) {
      speechFrames = Math.max(0, speechFrames - 1)
    }
    const finishedSpeaking = speechStarted && now - lastVoiceAt > 2600 && now - startedAt > 4200
    const noSpeechTimeout = !speechStarted && now - startedAt > 12000
    const maxDuration = now - startedAt > 22000
    if (finishedSpeaking || noSpeechTimeout || maxDuration) {
      stopVoiceCommand()
      return
    }
    silenceFrame = window.requestAnimationFrame(tick)
  }
  silenceFrame = window.requestAnimationFrame(tick)
}

async function startVoiceCommand(options = {}) {
  if (window.ceaserDesktop?.pythonVoiceCommand) {
    return startPythonVoiceCommand(options)
  }
  setState("error", "Voice engine unavailable", "Python voice engine is required for CEASER Desktop.")
  resultTitle.textContent = "Voice engine unavailable"
  resultSummary.textContent = "Restart CEASER after installing the packaged voice engine."
}
function complete(response) {
  const intent = pendingIntent
  const content = String(response.message || response.answer || response.preview || "").trim()
  if (response?.status === "error" && isAuthError(response)) {
    showAuthRecovery(content)
    return
  }
  if (response?.status === "needs_clarification") {
    const matches = Array.isArray(response.matches) ? response.matches.slice(0, 5) : []
    const message = content || "I found more than one match."
    setState("completed", "Choose one", message)
    resultTitle.textContent = "Choose one"
    resultSummary.textContent = message
    setDynamicPanel("answer-card", `
      <h2>Choose one</h2>
      <p>${escapeHtml(message)}</p>
      ${matches.length ? `<div class="choice-list">${matches.map((item) => `<button type="button" class="choice-pill" data-choice="${escapeHtml(item.name || "")}">${escapeHtml(item.name || "Unknown app")}</button>`).join("")}</div>` : ""}
    `)
    dynamicPanel?.querySelectorAll?.(".choice-pill")?.forEach((button) => {
      button.addEventListener("click", () => runCommand(`open ${button.dataset.choice || ""}`))
    })
    captureResultContext(intent, response)
    renderStats(["Needs clarification", `${matches.length} matches`])
    fitOverlay()
    speak("I found more than one match. Please choose one on screen.", () => afterAssistantTurn())
    return
  }
  const keepVisible = response.status !== "error" && shouldKeepOutputVisible(content, intent || {})
  if (keepVisible) {
    renderStickyOutput("Completed", content, intent || {}, response || {})
  } else {
    setState(response.status === "error" ? "error" : "completed", response.status === "error" ? "Something went wrong" : "Completed", response.message || "")
    renderDynamicResult(response, intent)
  }
  if (!keepVisible) {
    resultTitle.textContent = response.status === "error" ? "Action failed" : "Done"
    resultSummary.textContent = response.message || "CEASER finished the request."
  }
  captureResultContext(intent, response)
  const items = [...stepsList.querySelectorAll("li")]
  items.forEach((item) => {
    item.className = "done"
  })
  progressPercent.textContent = response.status === "error" ? "0%" : "100%"
  progressBar.style.width = response.status === "error" ? "12%" : "100%"
  if (compactProgressBar) compactProgressBar.style.width = "100%"
  const spoken = spokenResponseFor(response, intent)
  if (spoken) speak(spoken, () => afterAssistantTurn())
  else afterAssistantTurn()
  fitOverlay()
  if (activeMode === "expanded" && response.status !== "error" && !keepVisible) retractToCompact()
  // The V1 overlay stays visible; command results transition back to the
  // persistent listening/idle state through afterAssistantTurn().
}

commandForm.addEventListener("submit", async (event) => {
  event.preventDefault()
  await runCommand(commandInput.value)
})

document.getElementById("confirmAction").addEventListener("click", async () => {
  if (!pendingIntent) return
  if (pendingIntent.permission) {
    await window.ceaserDesktop.setPermission(pendingIntent.permission, true)
  }
  confirmationCard.classList.add("hidden")
  executeIntent({ ...pendingIntent, confirmed: true })
})

document.getElementById("cancelAction").addEventListener("click", () => {
  confirmationCard.classList.add("hidden")
  setState("idle", "Cancelled", "No action was taken.")
})

document.getElementById("minimalButton")?.addEventListener("click", () => window.ceaserDesktop?.hideOverlay?.({ reason: "toolbar_minimize" }))
document.getElementById("compactButton")?.addEventListener("click", () => window.ceaserDesktop?.hideOverlay?.({ reason: "toolbar_close" }))
document.getElementById("expandButton")?.addEventListener("click", () => setMode("expanded"))
document.querySelector(".minimal-shell")?.addEventListener("dblclick", () => setMode("compact"))
document.querySelector(".compact-shell")?.addEventListener("dblclick", () => setMode("expanded"))
document.getElementById("openAppButton").addEventListener("click", () => window.ceaserDesktop.openFullApp())
document.getElementById("diagnosticsButton")?.addEventListener("click", () => diagnosticsOpen ? hideDiagnostics() : showDiagnostics())
document.getElementById("helpButton")?.addEventListener("click", () => showDesktopGuide())
document.getElementById("closeGuideButton")?.addEventListener("click", () => closeDesktopGuide())
document.getElementById("guideSkipButton")?.addEventListener("click", () => closeDesktopGuide({ completed: true }))
guideBackButton?.addEventListener("click", () => {
  guideStepIndex = Math.max(0, guideStepIndex - 1)
  renderGuideStep()
})
guideNextButton?.addEventListener("click", () => {
  if (guideStepIndex >= DESKTOP_GUIDE_STEPS.length - 1) {
    closeDesktopGuide({ completed: true })
    return
  }
  guideStepIndex += 1
  renderGuideStep()
})
accountButton?.addEventListener("click", () => window.ceaserDesktop?.openAuth?.())
document.getElementById("closeDiagnosticsButton")?.addEventListener("click", hideDiagnostics)
document.getElementById("openLogsButton")?.addEventListener("click", () => window.ceaserDesktop?.openLogsFolder?.())
window.ceaserDesktop?.onRuntimeLog?.((entry) => {
  if (diagnosticsOpen) renderDiagnosticEntry(entry)
})
document.getElementById("attachFileButton").addEventListener("click", async () => {
  const result = await window.ceaserDesktop.pickMedia()
  if (result?.status !== "selected") return
  selectedDesktopFileContext = result.desktop_file_context
  commandInput.placeholder = `Ask about ${selectedDesktopFileContext.filename}`
  commandInput.focus()
})
document.getElementById("resetButton").addEventListener("click", () => {
  commandInput.value = ""
  pendingIntent = null
  confirmationCard.classList.add("hidden")
  setState("idle", "How can I help?", "Say or type a command.")
  showPrompt("")
  renderIdlePanel()
  renderSteps([])
  resultTitle.textContent = "Ready"
  resultSummary.textContent = "CEASER is available on your desktop."
})

inactivityContinueButton?.addEventListener("click", () => {
  hideInactivityPrompt()
  restoreFromSilentBackground("continue-active")
  setState("idle", "CEASER ready", "How can I help?")
  renderIdlePanel()
  showPrompt("")
  scheduleInactivityTimer("continue-active")
})

inactivitySilentButton?.addEventListener("click", () => {
  hideInactivityPrompt()
  enterSilentBackground("user_choice")
})

function renderDynamicIntent(intent) {
  if (!dynamicPanel) return
  const action = intent?.action
  if (action === "get_weather") {
    setDynamicPanel("weather-card", `
      <div class="weather-location">${escapeHtml(intent.parameters?.location || "Hyderabad, IN")}<span>Checking weather...</span></div>
      <div class="weather-main">
        <div class="weather-icon cloud"></div>
        <div class="weather-copy"><div class="weather-temp">--Â°C</div><p>Loading forecast</p></div>
        <div class="weather-meta"><span>Humidity</span><strong>--</strong><span>Wind</span><strong>--</strong></div>
      </div>
    `)
    return
  }
  if (action === "get_news") {
    setDynamicPanel("news-card", `<h3>Top News</h3><div class="view-more">Reading latest headlines...</div>`)
    return
  }
  if (action === "create_document") {
    setDynamicPanel("document-card", `
      <h2>Creating ${escapeHtml(String(intent.parameters?.kind || "document").toUpperCase())}</h2>
      <p>${escapeHtml(intent.parameters?.prompt || "Preparing your document.")}</p>
      <div class="doc-status">Saving to CEASER Files...</div>
    `)
    return
  }
  if (action === "play_youtube" || action === "media_key" || action === "now_playing") return renderMusicPanel(intent.parameters?.query || intent.result_preview?.summary || "Music")
  if (action === "stock_price") return renderStockPanel()
  if (action === "set_timer") return renderTimerPanel(intent.parameters)
  if (action === "get_tasks") return renderTasksPanel()
  if (action === "open_app" || action === "focus_app" || action === "check_app_running" || action === "close_app" || action === "restart_app") {
    return renderLauncherPanel(intent.parameters?.label || intent.parameters?.app_name || "Application", "Launching application...", 80)
  }
  if (action === "daily_brief" || /\bcalendar|schedule|meeting/i.test(promptText(intent))) return renderCalendarPanel()
  if (/\btask|todo|to-do/i.test(promptText(intent))) return renderTasksPanel()
  if (/\btimer|alarm/i.test(promptText(intent))) return renderTimerPanel()
  if (intent.intent === "agent_action") {
    setDynamicPanel("answer-card", `<h2>${escapeHtml(intent.active_agent || "CEASER")} ${escapeHtml(intent.agent_action || "Working")}</h2><p>${escapeHtml(intent.result_preview?.summary || "CEASER is working on it.")}</p>`)
    return
  }
  if (intent.intent === "answer_action" || intent.intent === "chat_action") {
    setDynamicPanel("answer-card", `<h2>Thinking...</h2><p>${escapeHtml(promptText(intent))}</p>`)
  }
}

function renderWeatherPanel(weather, fallback) {
  const temp = Math.round(Number(weather?.temperature ?? 28))
  const location = weather?.location || "Hyderabad, Telangana"
  const description = weather?.condition || weather?.description || fallback || "Current conditions"
  const humidity = weather?.humidity ? `${weather.humidity}%` : "--"
  const wind = weather?.wind_speed ? `${Number(weather.wind_speed).toFixed(1)} m/s` : "--"
  const iconClass = /rain/i.test(description) ? "rain" : /cloud|overcast/i.test(description) ? "cloud" : "sun"
  setDynamicPanel("weather-card", `
    <div class="weather-location">${escapeHtml(location)}<span>${escapeHtml(new Date().toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" }))}</span></div>
    <div class="weather-main">
      <div class="weather-icon ${iconClass}"></div>
      <div class="weather-copy"><div class="weather-temp">${temp}Â°C</div><p>${escapeHtml(description)}</p></div>
      <div class="weather-meta"><span>Humidity</span><strong>${humidity}</strong><span>Wind</span><strong>${wind}</strong></div>
    </div>
    <div class="forecast-row">${["Now","11 AM","12 PM","1 PM","2 PM","3 PM","4 PM"].map((label, index) => `<span>${label}<b>${index % 3 === 0 ? "Clear" : "Cloud"}</b><small>${temp + (index % 4)}Â°</small></span>`).join("")}</div>
  `)
}

function renderNewsPanel(articles, fallback) {
  const rows = articles.slice(0, 4).map((article) => `
    <div class="news-item">
      <div><div class="news-title">${escapeHtml(article.title || "News update")}</div><div class="news-source">${escapeHtml(article.source || article.publisher || "News")} Â· ${escapeHtml(article.published_at || "Latest")}</div></div>
      ${article.image_url || article.urlToImage ? `<img class="news-thumb" src="${escapeHtml(article.image_url || article.urlToImage)}" alt="">` : `<div class="news-thumb"></div>`}
    </div>
  `).join("")
  setDynamicPanel("news-card", `
    <h3>Top News</h3>
    ${rows || `<div class="view-more">${escapeHtml(fallback || "No live headlines available yet.")}</div>`}
    <div class="view-more">View more news â€º</div>
  `)
}

function renderDocumentPanel(response = {}) {
  const name = response?.document?.file_name || response?.file?.name || "Generated document"
  const preview = response?.preview || response?.message || "Document created."
  setDynamicPanel("document-card", `
    <h2>${escapeHtml(response.status === "error" ? "Document not created" : "Document created")}</h2>
    <p class="doc-name">${escapeHtml(name)}</p>
    <p>${escapeHtml(preview).slice(0, 520)}</p>
    <div class="doc-status">${response.status === "error" ? "Check CEASER sign-in and backend status." : "Opened CEASER Files so you can review it."}</div>
  `)
}

function renderMusicPanel(music) {
  const item = typeof music === "string" ? { title: music, source: "YouTube" } : (music || {})
  const title = item.title || item.query || "Music"
  const source = item.source || "YouTube"
  const thumbnail = item.thumbnail || ""
  const status = item.status || item.message || (item.direct === false ? "Search opened" : "Now playing")
  setDynamicPanel("music-card", `
    <div class="album-art" ${thumbnail ? `style="background-image: linear-gradient(135deg, rgba(10, 13, 30, 0.15), rgba(10, 13, 30, 0.5)), url('${escapeHtml(thumbnail)}')"` : ""}></div>
    <div class="music-info">
      <div class="music-source"><span></span>${escapeHtml(source)}</div>
      <h2>${escapeHtml(title)}</h2>
      <p>${escapeHtml(status)}</p>
      <div class="player-line"></div>
      <div class="player-controls"><span>Prev</span><span class="play-circle">Pause</span><span>Next</span></div>
    </div>
  `)
}

window.ceaserDesktop?.onStartListening?.((payload = {}) => {
  window.clearTimeout(hideTimer)
  commandInput.value = ""
  pendingIntent = null
  confirmationCard.classList.add("hidden")
  setMode("compact")
  renderSteps([])
  if (payload.mode === "wake_session") {
    startAssistantSession()
  } else if (payload.mode === "hold") {
    return
  } else {
    startVoiceCommand({ passive: false, requireWakeWord: false, singleCommand: true })
  }
})

window.ceaserDesktop?.onStopListening?.((payload = {}) => {
  if (payload.mode === "hold") {
    if (holdVoiceSessionId && payload.sessionId && payload.sessionId !== holdVoiceSessionId) return
    holdVoiceContext = payload.context || holdVoiceContext
    if (!stopHoldSpeechCommand()) stopVoiceCommand()
  }
})

window.ceaserDesktop?.onOverlayVisibility?.((payload = {}) => {
  overlayVisible = payload.visible !== false
  if (!overlayVisible) {
    if (inactivityPromptVisible) hideInactivityPrompt()
    if (!silentBackgroundActive) scheduleInactivityTimer('hidden:' + (payload.reason || 'unknown'))
    return
  }
  markUserActivity('visible:' + (payload.reason || 'unknown'), { force: true })
  restoreFromSilentBackground(payload.reason || 'overlay_restored')
})

async function startRightCtrlHoldFromRenderer() {
  if (listeningActive || holdVoiceActive) return
  const auth = await window.ceaserDesktop?.getAuthStatus?.()
  if (!auth?.linked) {
    await showAuthRequired()
    return
  }
  const context = await window.ceaserDesktop?.getContext?.().catch(() => null)
  startHoldSpeechCommand({ context, sessionId: `renderer_hold_${Date.now()}` })
}

function startHoldSpeechCommand(options = {}) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!SpeechRecognition) {
    setState("error", "Voice unavailable", "Hold voice is not supported here.")
    return
  }
  if (holdSpeechRecognition || listeningActive) return
  holdVoiceActive = true
  holdVoiceSessionId = options.sessionId || `hold_${Date.now()}`
  holdVoiceContext = options.context || null
  holdSpeechTranscript = ""
  holdSpeechStopping = false
  setVoiceButtonState(true)
  setMode("compact")
  setState("listening", "Listening...", "Speak your command.")
  const recognition = new SpeechRecognition()
  holdSpeechRecognition = recognition
  recognition.lang = "en-IN"
  recognition.continuous = true
  recognition.interimResults = true
  recognition.maxAlternatives = 1
  recognition.onresult = (event) => {
    let text = ""
    for (let index = 0; index < event.results.length; index += 1) {
      text += event.results[index][0]?.transcript || ""
    }
    holdSpeechTranscript = text.replace(/\s+/g, " ").trim()
    if (holdSpeechTranscript) setState("listening", "Listening...", holdSpeechTranscript)
  }
  recognition.onerror = (event) => {
    console.warn("[CEASER] Hold speech error:", event.error)
    if (holdSpeechStopping && holdSpeechTranscript) return
    if (!holdSpeechTranscript) resetAfterVoiceMiss("Voice unavailable", "Please try again.")
  }
  recognition.onend = async () => {
    const transcript = holdSpeechTranscript.trim()
    holdSpeechRecognition = null
    setVoiceButtonState(false)
    holdSpeechStopping = false
    if (!transcript) {
      holdVoiceActive = false
      holdVoiceSessionId = null
      holdVoiceContext = null
      resetAfterVoiceMiss("I did not catch that", "Please speak again.")
      return
    }
    setState("transcribing", "Transcribing...", transcript)
    await handleVoiceTranscript(transcript, { holdToTalk: true, context: options.context || holdVoiceContext || {} })
  }
  try {
    recognition.start()
  } catch (error) {
    holdSpeechRecognition = null
    holdVoiceActive = false
    setVoiceButtonState(false)
    console.warn("[CEASER] Hold speech start failed:", error.message || error)
    resetAfterVoiceMiss("Voice unavailable", "Hold voice could not start.")
  }
}

function stopHoldSpeechCommand() {
  if (!holdSpeechRecognition) return false
  holdSpeechStopping = true
  setState("transcribing", "Transcribing...", holdSpeechTranscript || "Understanding your command.")
  try {
    holdSpeechRecognition.stop()
  } catch (_error) {
    holdSpeechRecognition = null
    setVoiceButtonState(false)
  }
  return true
}

window.ceaserDesktop?.onPythonVoiceStatus?.((payload = {}) => {
  if (payload.status === "capture_progress") {
    renderSmartCaptureProgress(payload.stage || "Scanning Document...", payload.progress || 0, payload.file || "")
    return
  }
  if (!voiceSession?.id?.startsWith("python_voice_")) return
  if (payload.status === "listening") {
    setState("listening", "Listening...", "Speak your command.")
  } else if (payload.status === "transcribing") {
    setState("transcribing", "Transcribing...", "Understanding your command.")
  } else if (payload.status === "executing") {
    const command = String(payload.command || "").trim()
    commandInput.value = command
    const isLocal = /\b(open|launch|start|run|close|quit|exit|play|pause|resume|next|previous|forward|backward|volume|mute|screenshot|lock|settings|calculator|notepad|chrome|edge|whatsapp|word|excel|powerpoint|vs code|visual studio code)\b/i.test(command)
    setState("thinking", isLocal ? "Executing..." : "Thinking...", command || "Working on it.")
  }
})

window.ceaserDesktop?.onPythonEvent?.((event = {}) => {
  if (event.event !== "proactive_message") return
  const payload = event.payload || {}
  const message = cleanOverlayText(payload.message || "")
  if (!message) return
  window.ceaserDesktop?.showOverlay?.()
  renderStickyOutput("CEASER", message, { action: "proactive_message", parameters: {} }, {
    status: "completed",
    verified: payload.verified !== false,
    proactive: true,
    priority: payload.priority,
  })
  const hide = document.getElementById("hideStickyOutput")
  if (hide) hide.onclick = () => {
    window.ceaserDesktop?.pythonVoiceCommand?.({ type: "proactive_dismiss" }).catch(() => {})
    window.ceaserDesktop?.hideOverlay?.()
  }
  if (payload.should_speak && !speakingActive && !voiceSession) {
    speak(payload.spoken_response || message)
  }
})

appShell.addEventListener("dragenter", (event) => {
  event.preventDefault()
  const file = event.dataTransfer?.files?.[0]
  renderSmartCaptureDrop(file || { name: "Your file", size: 0 })
})

appShell.addEventListener("dragover", (event) => {
  event.preventDefault()
  event.dataTransfer.dropEffect = "copy"
})

appShell.addEventListener("dragleave", (event) => {
  event.preventDefault()
  if (smartCaptureActive) return
  if (!appShell.contains(event.relatedTarget)) renderIdlePanel()
})

appShell.addEventListener("drop", async (event) => {
  event.preventDefault()
  const file = event.dataTransfer?.files?.[0]
  if (!file) return
  await analyzeDroppedFile(file)
})

window.ceaserDesktop?.onAuthLinked?.(async (payload = {}) => {
  if (payload?.linked === false) {
    const reason = payload?.error === "invalid_state"
      ? "The connection request expired. Please start the connection again."
      : "CEASER could not complete the secure account connection. Please try again."
    await showAuthRecovery(reason)
    return
  }
  const auth = await window.ceaserDesktop?.getAuthStatus?.().catch(() => null)
  applyLinkedUser(auth)
  setMode("compact")
  setState("completed", "Account connected", "CEASER Desktop is linked.")
  resultTitle.textContent = "Connected"
  resultSummary.textContent = "Your desktop companion can now use your CEASER account."
  if (accountButton) accountButton.textContent = "Account"
  setDynamicPanel("answer-card", `<h2>Account connected</h2><p>Your desktop companion is ready.</p>`)
  speak("Account connected. CEASER Desktop is ready.")
  window.setTimeout(() => window.ceaserDesktop?.hideOverlay?.(), 2200)
})

window.ceaserDesktop?.onSystemPower?.((payload = {}) => {
  console.log("[CEASER] system power", payload)
  if (payload.state === "resume" || payload.state === "unlock-screen") {
    if (alwaysListenActive || assistantSessionActive) {
      window.setTimeout(() => startPassiveWakeLoop(), 900)
    }
  }
})

renderSteps([])
fitOverlay()
refreshContext()
setInterval(refreshContext, 15000)
window.ceaserDesktop?.onPythonReady?.(() => {
  window.setTimeout(() => playStartupGreeting(), 250)
})
window.ceaserDesktop?.getAuthStatus?.().then((auth) => {
  applyLinkedUser(auth)
  if (!auth?.linked) showAuthRequired()
  else {
    if (accountButton) accountButton.textContent = "Account"
    renderIdlePanel()
  }
}).catch(() => {}).finally(() => {
  maybeShowFirstRunGuide()
  scheduleInactivityTimer("startup")
})

new ResizeObserver(() => fitOverlay()).observe(appShell)


