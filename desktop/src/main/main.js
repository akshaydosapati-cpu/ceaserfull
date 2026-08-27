const { app, BrowserWindow, Menu, Tray, ipcMain, nativeImage, protocol, screen, session, shell, globalShortcut, clipboard, powerMonitor, safeStorage, dialog } = require("electron")
const fs = require("fs")
const path = require("path")
const crypto = require("crypto")
const os = require("os")
const { execFile, spawn, spawnSync } = require("child_process")
const { DeviceGatewayClient } = require("../services/device-gateway-client")
const { LocalDevelopmentRuntime, LOCAL_DEVELOPMENT_CAPABILITIES } = require("../services/local-development-runtime")
const { BrowserAutomationRuntime, CAPS: BROWSER_CAPABILITIES } = require("../services/browser-automation-runtime")
const { FileContextResolver } = require("../services/file-context-resolver")
const { launchApp, closeApp, refreshApps, refreshApplicationIndex, applicationIndexNeedsRefresh } = require("../services/app-launcher")

let overlayWindow

function terminalTimestamp() {
  const now = new Date()
  const pad = (value, size = 2) => String(value).padStart(size, "0")
  return `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}.${pad(now.getMilliseconds(), 3)}`
}

const runtimeLogEntries = []
const RUNTIME_LOG_LIMIT = 400
const RUNTIME_LOG_MAX_BYTES = 5 * 1024 * 1024

function redactRuntimeLog(value) {
  return String(value ?? "")
    .replace(/(authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)(\s*[:=]\s*)([^\s,;]+)/gi, "$1$2[REDACTED]")
    .replace(/Bearer\s+[A-Za-z0-9._~+\/-]+/gi, "Bearer [REDACTED]")
    .replace(/([?&](?:code|token|state)=)[^&\s]+/gi, "$1[REDACTED]")
    .slice(0, 4000)
}

function runtimeLogPath() {
  const dir = path.join(process.env.APPDATA || process.cwd(), "CEASER", "logs")
  fs.mkdirSync(dir, { recursive: true })
  return path.join(dir, "ceaser-desktop.log")
}

function appendRuntimeLog(level, args) {
  try {
    const entry = {
      at: new Date().toISOString(),
      level,
      message: redactRuntimeLog(args.map((item) => item instanceof Error ? item.stack || item.message : typeof item === "string" ? item : JSON.stringify(item)).join(" ")),
    }
    runtimeLogEntries.push(entry)
    if (runtimeLogEntries.length > RUNTIME_LOG_LIMIT) runtimeLogEntries.splice(0, runtimeLogEntries.length - RUNTIME_LOG_LIMIT)
    const file = runtimeLogPath()
    if (fs.existsSync(file) && fs.statSync(file).size >= RUNTIME_LOG_MAX_BYTES) {
      const previous = `${file}.1`
      if (fs.existsSync(previous)) fs.rmSync(previous, { force: true })
      fs.renameSync(file, previous)
    }
    fs.appendFileSync(file, `${JSON.stringify(entry)}\n`, "utf8")
    const contents = overlayWindow?.webContents
    if (contents && !contents.isDestroyed()) {
      try {
        contents.send("ceaser:runtime-log", entry)
      } catch (_sendError) {
        // A renderer can disappear between the lifecycle check and send.
      }
    }
  } catch (_error) {
    // Diagnostics must never interfere with the desktop runtime.
  }
}

function installTerminalTimestamps() {
  const original = {
    log: console.log.bind(console),
    warn: console.warn.bind(console),
    error: console.error.bind(console),
  }
  const wrap = (method) => (...args) => {
    appendRuntimeLog(method, args)
    original[method](`[${terminalTimestamp()}]`, ...args)
  }
  console.log = wrap("log")
  console.warn = wrap("warn")
  console.error = wrap("error")
}

installTerminalTimestamps()

function startupLog(message, error) {
  try {
    const dir = path.join(process.env.APPDATA || process.cwd(), "CEASER")
    fs.mkdirSync(dir, { recursive: true })
    const detail = error ? ` ${error.stack || error.message || error}` : ""
    fs.appendFileSync(path.join(dir, "startup.log"), `[${new Date().toISOString()}] ${message}${detail}\n`, "utf8")
    appendRuntimeLog(error ? "error" : "info", ["[startup]", message, detail])
  } catch (_error) {
    // Startup logging must never block launch.
  }
}

const startupStartedAt = Date.now()
function startupPhase(name) {
  const memoryMb = Math.round(process.memoryUsage().rss / 1024 / 1024)
  startupLog(`startup_phase=${name} elapsed_ms=${Date.now() - startupStartedAt} memory_mb=${memoryMb}`)
}

startupLog("main_loaded")
startupPhase("electron_main_loaded")

let CommandRouter
let BehaviorMemory
let ContextService
let IdentityService
let getEnv
let PermissionStore
let insertTextAtFocus
let resolveAppUrl
try {
  ;({ CommandRouter } = require("../controllers/command-router"))
  ;({ BehaviorMemory } = require("../services/behavior-memory"))
  ;({ ContextService } = require("../services/context-service"))
  ;({ IdentityService } = require("../services/identity-service"))
  ;({ getEnv } = require("../services/env"))
  ;({ PermissionStore } = require("../services/permissions"))
  ;({ insertTextAtFocus } = require("../services/voice-compose"))
  ;({ resolveAppUrl } = require("./app-shell"))
  startupLog("modules_loaded")
} catch (error) {
  startupLog("module_load_failed", error)
  throw error
}

protocol.registerSchemesAsPrivileged([
  {
    scheme: "ceaser-app",
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      corsEnabled: true,
    },
  },
])

let mainWindow
let tray
let localDevelopmentRuntime
let browserAutomationRuntime
let fileContextResolver
let lastOverlaySize = { width: 0, height: 0 }
let holdKeyWatcher
let holdVoiceContext = null
let overlayReady = false
let holdSessionActive = false
let holdSessionId = 0
let holdWatcherRestartTimer = null
let pythonVoiceProcess = null
let pythonVoiceBuffer = ""
let pythonVoiceRequestCounter = 0
let pythonVoiceReady = false
let pythonVoiceUnavailable = null
let deviceGateway = null
let pythonVoiceRestartTimer = null
let appIsQuitting = false
const pythonVoiceReadyWaiters = []
const pythonVoiceRequests = new Map()
const VOICE_HOTKEY = String(process.env.CEASER_VOICE_HOTKEY || "CommandOrControl+Shift+Space").trim()
const VOICE_HOTKEY_FALLBACKS = [
  "CommandOrControl+Alt+Space",
  "CommandOrControl+Shift+C",
  "CommandOrControl+Alt+C",
  "CommandOrControl+Shift+X",
]
let activeVoiceHotkey = VOICE_HOTKEY
let mediaDuckDepth = 0
let mediaDuckPresses = 0
let authStatusCache = { value: null, expiresAt: 0 }
let pendingPkce = null
let deviceRegistrationPromise = null
let deviceRegistrationRetryTimer = null
let deviceRegistrationAttempt = 0
let overlayVisibilityState = "hidden"

function sendVolumeKey(keyCode, presses = 1) {
  return new Promise((resolve) => {
    const safePresses = Math.max(1, Math.min(Number(presses) || 1, 50))
    const script = `
      $ws = New-Object -ComObject WScript.Shell
      for ($i = 0; $i -lt ${safePresses}; $i++) {
        $ws.SendKeys([char]${keyCode})
        Start-Sleep -Milliseconds 12
      }
    `
    execFile("powershell.exe", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], { windowsHide: true, timeout: 2500 }, () => resolve())
  })
}

async function duckMediaForListening(payload = {}) {
  if (!/^(1|true|yes|on)$/i.test(String(getEnv("CEASER_MEDIA_DUCK_ENABLED", "false")).trim())) {
    return { status: "disabled" }
  }
  if (!payload.mediaActive) return { status: "no_active_media" }
  if (mediaDuckDepth > 0) {
    mediaDuckDepth += 1
    return { status: "already_ducked", depth: mediaDuckDepth }
  }
  const presses = Math.max(4, Math.min(Number(payload.presses) || 12, 24))
  mediaDuckDepth = 1
  mediaDuckPresses = presses
  await sendVolumeKey(174, presses)
  return { status: "ducked", presses }
}

async function restoreMediaAfterListening() {
  if (mediaDuckDepth <= 0) return { status: "not_ducked" }
  mediaDuckDepth -= 1
  if (mediaDuckDepth > 0) return { status: "still_ducked", depth: mediaDuckDepth }
  const presses = mediaDuckPresses || 12
  mediaDuckPresses = 0
  await sendVolumeKey(175, presses)
  return { status: "restored", presses }
}
const activeTasks = new Map()
const permissions = new PermissionStore()
const router = new CommandRouter({ permissions })
const contextService = new ContextService()
const behaviorMemory = new BehaviorMemory()
const identityService = new IdentityService({
  getDesktopContext: () => contextService.snapshot(),
  getSystemState: () => overlayWindow?.isVisible() ? "Online" : "Idle",
})

function persistentEnvPath() {
  const dir = path.join(app.getPath("appData"), "CEASER")
  fs.mkdirSync(dir, { recursive: true })
  return path.join(dir, ".env")
}

function writePersistentEnv(updates = {}) {
  const file = persistentEnvPath()
  const existing = fs.existsSync(file) ? fs.readFileSync(file, "utf8").split(/\r?\n/) : []
  const values = new Map()
  for (const line of existing) {
    const match = line.match(/^([^#=]+)=(.*)$/)
    if (match) values.set(match[1].trim(), match[2].trim())
  }
  for (const [key, value] of Object.entries(updates)) {
    const cleaned = String(value || "").trim()
    if (cleaned && !["undefined", "null", "false"].includes(cleaned.toLowerCase())) values.set(key, cleaned)
  }
  const next = [...values.entries()].map(([key, value]) => `${key}=${value}`).join("\n") + "\n"
  fs.writeFileSync(file, next, "utf8")
}

function removePersistentEnvKeys(keys = []) {
  const file = persistentEnvPath()
  const existing = fs.existsSync(file) ? fs.readFileSync(file, "utf8").split(/\r?\n/) : []
  const remove = new Set(keys)
  const next = existing.filter((line) => {
    const match = line.match(/^([^#=]+)=/)
    return !match || !remove.has(match[1].trim())
  }).join("\n")
  fs.writeFileSync(file, next ? `${next}\n` : "", "utf8")
}

function secureSessionPath() {
  const dir = app.getPath("userData")
  fs.mkdirSync(dir, { recursive: true })
  return path.join(dir, "desktop-session.secure.json")
}

function deviceIdPath() {
  const dir = app.getPath("userData")
  fs.mkdirSync(dir, { recursive: true })
  return path.join(dir, "desktop-device.json")
}

function getDesktopDevice() {
  const file = deviceIdPath()
  try {
    if (fs.existsSync(file)) {
      const existing = JSON.parse(fs.readFileSync(file, "utf8"))
      if (existing?.device_id) {
        return {
          device_id: existing.device_id,
          device_name: existing.device_name || os.hostname(),
          app_version: app.getVersion(),
          platform: process.platform,
        }
      }
    }
  } catch (_error) {
    // Regenerate below.
  }
  const device = {
    device_id: crypto.randomUUID(),
    device_name: os.hostname(),
    app_version: app.getVersion(),
    platform: process.platform,
  }
  fs.writeFileSync(file, JSON.stringify(device, null, 2), "utf8")
  return device
}

function encryptSessionValue(value) {
  if (!safeStorage.isEncryptionAvailable()) {
    throw new Error("secure_storage_unavailable")
  }
  return safeStorage.encryptString(String(value || "")).toString("base64")
}

function decryptSessionValue(value) {
  if (!value || !safeStorage.isEncryptionAvailable()) return ""
  return safeStorage.decryptString(Buffer.from(String(value), "base64"))
}

function writeSecureDesktopSession(sessionData = {}) {
  const refreshToken = String(sessionData.refresh_token || sessionData.refreshToken || "").trim()
  if (!refreshToken) return false
  const accessToken = String(sessionData.access_token || sessionData.accessToken || "").trim()
  const user = sessionData.user || {}
  const payload = {
    version: 1,
    refresh_token: encryptSessionValue(refreshToken),
    access_token: accessToken ? encryptSessionValue(accessToken) : "",
    user_id: user?.id || sessionData.user_id || sessionData.userId || "",
    user,
    linked_at: new Date().toISOString(),
    device: getDesktopDevice(),
  }
  fs.writeFileSync(secureSessionPath(), JSON.stringify(payload, null, 2), "utf8")
  return true
}

function readSecureDesktopSession() {
  try {
    const file = secureSessionPath()
    if (!fs.existsSync(file)) return null
    const payload = JSON.parse(fs.readFileSync(file, "utf8"))
    const refreshToken = decryptSessionValue(payload.refresh_token)
    const accessToken = decryptSessionValue(payload.access_token)
    if (!refreshToken && !accessToken) return null
    return {
      refresh_token: refreshToken,
      access_token: accessToken,
      user_id: payload.user_id || payload.user?.id || "",
      user: payload.user || null,
      linked_at: payload.linked_at || "",
      device: payload.device || getDesktopDevice(),
    }
  } catch (error) {
    startupLog("secure_session_read_failed", error)
    return null
  }
}

function clearSecureDesktopSession() {
  try {
    const file = secureSessionPath()
    if (fs.existsSync(file)) fs.unlinkSync(file)
  } catch (_error) {
    // Best effort.
  }
  removePersistentEnvKeys(["CEASER_ACCESS_TOKEN", "CEASER_REFRESH_TOKEN", "CURRENT_USER_ID", "CEASER_LINKED_AT"])
  authStatusCache = { value: null, expiresAt: 0 }
}

function persistRuntimeAccess(sessionData = {}) {
  writePersistentEnv({
    CEASER_ACCESS_TOKEN: sessionData.access_token || sessionData.accessToken || "",
    CURRENT_USER_ID: sessionData.user?.id || sessionData.user_id || sessionData.userId || "",
    CEASER_LINKED_AT: new Date().toISOString(),
    CEASER_DESKTOP_DEVICE_ID: getDesktopDevice().device_id,
  })
  removePersistentEnvKeys(["CEASER_REFRESH_TOKEN"])
}

function base64Url(input) {
  return Buffer.from(input).toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "")
}

function createPkceChallenge() {
  const verifier = base64Url(crypto.randomBytes(48))
  const challenge = base64Url(crypto.createHash("sha256").update(verifier).digest())
  return { verifier, challenge, state: crypto.randomUUID() }
}

function authRedirectUri() {
  return "ceaser://auth/callback"
}

function consoleAppUrl() {
  const configured = String(getEnv("CEASER_APP_URL", "")).trim().replace(/\/$/, "")
  if (configured && !/app\.ceaser\.ai/i.test(configured)) return configured
  return "https://heyceaser.in/console"
}

function parseDeepLinkPayload(rawUrl) {
  const value = String(rawUrl || "")
  if (!value.startsWith("ceaser-app://") && !value.startsWith("ceaser://")) return null
  const [, fragment = ""] = value.split("#")
  const url = new URL(value.replace("#" + fragment, ""))
  const params = new URLSearchParams(url.search)
  if (fragment) {
    const hashParams = new URLSearchParams(fragment)
    for (const [key, val] of hashParams.entries()) params.set(key, val)
  }
  const cleanParam = (name) => {
    const value = String(params.get(name) || "").trim()
    return value && !["undefined", "null", "false"].includes(value.toLowerCase()) ? value : ""
  }
  const accessToken = cleanParam("access_token") || cleanParam("token") || cleanParam("desktop_token")
  const refreshToken = cleanParam("refresh_token")
  const userId = cleanParam("user_id") || cleanParam("sub")
  const code = cleanParam("code")
  const state = cleanParam("state")
  if (!accessToken && !refreshToken && !userId && !code) return null
  return { accessToken, refreshToken, userId, code, state }
}

let lastDesktopAuthCallback = null
const DESKTOP_AUTH_EXCHANGE_TIMEOUT_MS = 45000
const DESKTOP_SESSION_CHECK_TIMEOUT_MS = 20000
const DESKTOP_DEVICE_REGISTER_TIMEOUT_MS = 30000
const DESKTOP_BACKEND_WARM_TIMEOUT_MS = 20000

function handleDeepLink(rawUrl) {
  const payload = parseDeepLinkPayload(rawUrl)
  if (!payload) return false
  startupLog("desktop_auth_callback_received")
  if (payload.code) {
    const now = Date.now()
    if (lastDesktopAuthCallback
      && lastDesktopAuthCallback.code === payload.code
      && lastDesktopAuthCallback.state === payload.state
      && now - lastDesktopAuthCallback.at < 30000) {
      startupLog("desktop_auth_duplicate_callback_ignored")
      return true
    }
    lastDesktopAuthCallback = { code: payload.code, state: payload.state, at: now }
    exchangeDesktopAuthCode(payload).then((result) => {
      if (result?.ok) showLinkedOverlay()
      else overlayWindow?.webContents.send("ceaser:auth-linked", { linked: false, error: result?.reason || "exchange_failed" })
    })
    return true
  }
  if (payload.refreshToken) {
    writeSecureDesktopSession({
      access_token: payload.accessToken,
      refresh_token: payload.refreshToken,
      user_id: payload.userId,
      user: { id: payload.userId },
    })
  }
  persistRuntimeAccess({ access_token: payload.accessToken, user_id: payload.userId })
  authStatusCache = { value: null, expiresAt: 0 }
  if (pythonVoiceProcess && !pythonVoiceProcess.killed) {
    pythonVoiceProcess.kill()
    pythonVoiceProcess = null
  }
  showLinkedOverlay()
  return true
}

async function exchangeDesktopAuthCode(payload = {}) {
  const pkce = pendingPkce
  const stateValid = Boolean(pkce && payload.state === pkce.state)
  startupLog(`desktop_auth_state_validation ${stateValid ? "ok" : "failed"}`)
  if (!stateValid) return { ok: false, reason: "invalid_state" }
  pendingPkce = null
  const apiUrl = getEnv("CEASER_API_URL", "https://ceaser-backend-production-ur04.onrender.com").replace(/\/$/, "")
  const device = getDesktopDevice()
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), DESKTOP_AUTH_EXCHANGE_TIMEOUT_MS)
  try {
    const response = await fetch(`${apiUrl}/auth/desktop/exchange`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        code: payload.code,
        code_verifier: pkce.verifier,
        redirect_uri: authRedirectUri(),
        device,
      }),
      signal: controller.signal,
    })
    startupLog(`desktop_auth_exchange_http_${response.status}`)
    if (!response.ok) return { ok: false, reason: `http_${response.status}` }
    const data = await response.json()
    if (!data?.access_token || !data?.refresh_token) return { ok: false, reason: "missing_tokens" }
    const saved = writeSecureDesktopSession(data)
    startupLog(`desktop_auth_secure_session_save_${saved ? "ok" : "failed"}`)
    persistRuntimeAccess(data)
    registerDesktopDeviceInBackground(apiUrl, data.access_token, data.user || {}, "desktop_auth")
    authStatusCache = { value: null, expiresAt: 0 }
    syncPythonAccessSession(data)
    return { ok: true, user: data.user || null }
  } catch (error) {
    startupLog("desktop_auth_exchange_failed", error)
    return { ok: false, reason: error.name || "network" }
  } finally {
    clearTimeout(timer)
  }
}

function showLinkedOverlay() {
  if (!overlayWindow || overlayWindow.isDestroyed()) return
  restoreOverlayWindow({ reason: "auth_linked", resize: "compact" })
  overlayWindow.webContents.send("ceaser:auth-linked", { linked: true })
}

function syncPythonAccessSession(sessionData = {}) {
  if (!pythonVoiceProcess || pythonVoiceProcess.killed) return
  const accessToken = sessionData.access_token || sessionData.accessToken || ""
  const user = sessionData.user || {}
  const userId = user.id || sessionData.user_id || sessionData.userId || ""
  if (!accessToken) return
  pythonVoiceCommand({ type: "session_update", access_token: accessToken, user_id: userId, user })
    .then(() => startupLog("python_session_updated_without_restart"))
    .catch((error) => startupLog("python_session_update_deferred", error))
}

async function validateDesktopSession() {
  const secureSession = readSecureDesktopSession()
  const token = secureSession?.access_token || getEnv("CEASER_ACCESS_TOKEN")
  const refreshToken = secureSession?.refresh_token || getEnv("CEASER_REFRESH_TOKEN")
  if (!token && !refreshToken) return { linked: false, valid: false, reason: "missing" }
  if (authStatusCache.value && Date.now() < authStatusCache.expiresAt) return authStatusCache.value
  const apiUrl = getEnv("CEASER_API_URL", "https://ceaser-backend-production-ur04.onrender.com")
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), DESKTOP_SESSION_CHECK_TIMEOUT_MS)
  try {
    const response = await fetch(`${apiUrl.replace(/\/$/, "")}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: controller.signal,
    })
    if (response.ok) {
      const user = await response.json().catch(() => null)
      if (token !== getEnv("CEASER_ACCESS_TOKEN")) persistRuntimeAccess({ access_token: token, user })
      registerDesktopDeviceInBackground(apiUrl, token, user || {}, "session_validation")
      const result = { linked: true, valid: true, linked_at: secureSession?.linked_at || getEnv("CEASER_LINKED_AT", ""), user, device: getDesktopDevice() }
      authStatusCache = { value: result, expiresAt: Date.now() + 5 * 60 * 1000 }
      return result
    }
    if (response.status === 401 && refreshToken && refreshToken.length > 20) {
      const refreshed = await refreshDesktopSession(apiUrl, refreshToken)
      if (refreshed) return { linked: true, valid: true, linked_at: getEnv("CEASER_LINKED_AT", ""), refreshed: true, user: refreshed.user || null }
    }
    if (response.status === 401) {
      authStatusCache = { value: null, expiresAt: 0 }
      clearSecureDesktopSession()
      if (pythonVoiceProcess && !pythonVoiceProcess.killed) {
        pythonVoiceProcess.kill()
        pythonVoiceProcess = null
        pythonVoiceReady = false
      }
    }
    return { linked: false, valid: false, reason: `http_${response.status}`, linked_at: getEnv("CEASER_LINKED_AT", "") }
  } catch (error) {
    const fallback = { linked: true, valid: null, reason: error.name || "network", linked_at: getEnv("CEASER_LINKED_AT", "") }
    authStatusCache = { value: fallback, expiresAt: Date.now() + 60 * 1000 }
    return fallback
  } finally {
    clearTimeout(timer)
  }
}

async function refreshDesktopSession(apiUrl, refreshToken) {
  try {
    const response = await fetch(`${apiUrl.replace(/\/$/, "")}/auth/desktop/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken, device_id: getDesktopDevice().device_id }),
    })
    if (!response.ok) return false
    const data = await response.json()
    if (!data?.access_token) return false
    writeSecureDesktopSession({ ...data, refresh_token: data.refresh_token || refreshToken })
    persistRuntimeAccess(data)
    registerDesktopDeviceInBackground(apiUrl, data.access_token, data.user || {}, "session_refresh")
    authStatusCache = { value: null, expiresAt: 0 }
    syncPythonAccessSession(data)
    return { ok: true, user: data.user || null }
  } catch (_error) {
    return false
  }
}

async function registerDesktopDevice(apiUrl, accessToken, user = {}) {
  if (!apiUrl || !accessToken) return { ok: false, reason: "missing_auth" }
  const device = getDesktopDevice()
  try {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), DESKTOP_DEVICE_REGISTER_TIMEOUT_MS)
    let response
    try {
      response = await fetch(`${apiUrl.replace(/\/$/, "")}/desktop/devices`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
        body: JSON.stringify({
          ...device,
          user_id: user?.id || getEnv("CURRENT_USER_ID", ""),
          last_seen: new Date().toISOString(),
        }),
        signal: controller.signal,
      })
    } finally {
      clearTimeout(timer)
    }
    if (response.status === 401 || response.status === 403) {
      clearSecureDesktopSession()
      return { ok: false, reason: "revoked" }
    }
    if (response.ok) ensureDeviceGateway(apiUrl)
    return { ok: response.ok, status: response.status }
  } catch (error) {
    startupLog(`desktop_device_register_deferred reason=${error?.name || "network"}`)
    return { ok: false, reason: error.name || "network" }
  }
}

function registerDesktopDeviceInBackground(apiUrl, accessToken, user = {}, source = "background") {
  if (deviceRegistrationPromise) {
    startupLog(`${source}_device_register_joined_active_request`)
    return deviceRegistrationPromise
  }
  deviceRegistrationPromise = registerDesktopDevice(apiUrl, accessToken, user)
    .then((result) => {
      startupLog(`${source}_device_register_${result?.ok ? "ok" : result?.reason || result?.status || "failed"}`)
      if (result?.ok) {
        deviceRegistrationAttempt = 0
        overlayWindow?.webContents?.send("ceaser:gateway-status", { status: "connected" })
        return result
      }
      if (result?.reason !== "revoked" && !appIsQuitting && !deviceRegistrationRetryTimer) {
        const delay = Math.min(60000, 2000 * (2 ** Math.min(deviceRegistrationAttempt, 5)))
        deviceRegistrationAttempt += 1
        overlayWindow?.webContents?.send("ceaser:gateway-status", { status: "connecting", retry_in_ms: delay })
        deviceRegistrationRetryTimer = setTimeout(() => {
          deviceRegistrationRetryTimer = null
          registerDesktopDeviceInBackground(apiUrl, accessToken, user, "retry")
        }, delay)
        deviceRegistrationRetryTimer.unref?.()
      }
      return result
    })
    .catch((error) => {
      startupLog(`${source}_device_register_failed`, error)
      return { ok: false, reason: error?.name || "network" }
    })
    .finally(() => { deviceRegistrationPromise = null })
  return deviceRegistrationPromise
}

function deviceCapabilityCommand(request = {}) {
  const args = request.arguments || {}
  const explicit = args.command || args.text || args.raw_text || request.metadata?.command
  if (explicit) return String(explicit).trim()
  const value = (...keys) => keys.map((key) => args[key]).find((item) => item !== undefined && item !== null && String(item).trim())
  const capability = String(request.capability || "")
  const mappings = {
    "desktop.open_application": () => `open ${value("application", "app", "name") || ""}`,
    "desktop.close_application": () => `close ${value("application", "app", "name") || ""}`,
    "desktop.open_folder": () => `open ${value("folder", "path", "name") || "folder"}`,
    "desktop.open_file": () => `open ${value("file", "path", "name", "query") || "file"}`,
    "desktop.open_url": () => `open ${value("url") || ""}`,
    "desktop.take_screenshot": () => "take a screenshot",
    "desktop.set_volume": () => value("level") !== undefined ? `set volume to ${value("level")}%` : `${value("direction") || "increase"} volume`,
    "desktop.get_battery": () => "show battery status",
    "desktop.media_play_pause": () => String(value("action") || "play pause music"),
    "ai.answer": () => String(value("question", "prompt", "query") || ""),
    "ai.news": () => `show latest news about ${value("query", "topic") || "today"}`,
    "github.list_repositories": () => "list my GitHub repositories",
    "github.resolve_repository": () => `find my GitHub repository ${value("repository", "repo", "query") || ""}`,
    "github.get_readme": () => `read the README for ${value("repository", "repo") || "the active repository"}`,
    "github.list_commits": () => `show commits for ${value("repository", "repo") || "the active repository"}`,
    "github.list_issues": () => `show issues for ${value("repository", "repo") || "the active repository"}`,
    "github.list_pull_requests": () => `show pull requests for ${value("repository", "repo") || "the active repository"}`,
    "github.summarize_repository": () => `summarize ${value("repository", "repo") || "the active GitHub repository"}`,
    "notion.search_pages": () => `search my Notion for ${value("query") || "recent pages"}`,
    "notion.get_page": () => `read my Notion page ${value("page", "name", "query") || ""}`,
    "notion.list_tasks": () => "show my Notion tasks",
    "cloud.list": () => "list my CEASER cloud files",
    "cloud.search": () => `search my CEASER files for ${value("query") || ""}`,
    "cloud.latest": () => "show my latest CEASER cloud file",
    "cloud.read": () => `read my CEASER file ${value("resource", "name", "resource_id") || ""}`,
    "cloud.download": () => `download my CEASER file ${value("resource", "name", "resource_id") || ""}`,
    "study.generate_viva_questions": () => `generate viva questions ${value("topic", "context") ? `about ${value("topic", "context")}` : "from the active study material"}`,
    "study.generate_revision_notes": () => `generate revision notes ${value("topic", "context") ? `about ${value("topic", "context")}` : "from the active study material"}`,
    "study.generate_quiz": () => `generate a quiz ${value("topic", "context") ? `about ${value("topic", "context")}` : "from the active study material"}`,
    "ai.summarize_activity": () => "summarize my recent GitHub activity",
    "workflow.plan": () => String(value("goal", "prompt", "objective") || ""),
  }
  return mappings[capability]?.().trim() || ""
}

async function executeDeviceCapability(request) {
  if (request.confirmation_requirement === "required") {
    return { status: "failed", verified: true, error_code: "confirmation_required", message: "This action still requires user confirmation." }
  }
  if (!localDevelopmentRuntime) {
    localDevelopmentRuntime = new LocalDevelopmentRuntime({ dataDir: app.getPath("userData") })
  }
  if (!browserAutomationRuntime) {
    browserAutomationRuntime = new BrowserAutomationRuntime({ BrowserWindow, session, dataDir: path.join(app.getPath("userData"), "browser-automation"), downloadsDir: app.getPath("downloads"), maxSteps: getEnv("CEASER_BROWSER_MAX_STEPS", "25"), actionTimeout: getEnv("CEASER_BROWSER_ACTION_TIMEOUT_SECONDS", "15"), navigationTimeout: getEnv("CEASER_BROWSER_NAVIGATION_TIMEOUT_SECONDS", "30") })
  }
  const browserAliases = {
    "browser.open": "browser.start",
    "browser.tab.list": "browser.tabs",
    "browser.tab.open": "browser.open_tab",
    "browser.tab.close": "browser.close_tab",
    "browser.tab.switch": "browser.switch_tab",
  }
  if (browserAliases[request.capability]) {
    request = { ...request, capability: browserAliases[request.capability] }
  }
  if (request.capability === "browser.search") {
    const query = String(request.arguments?.query || request.arguments?.text || "").trim()
    if (!query) return { status: "failed", verified: true, error_code: "missing_query", message: "Tell me what to search for." }
    request = { ...request, capability: "browser.navigate", arguments: { ...(request.arguments || {}), url: `https://www.google.com/search?q=${encodeURIComponent(query)}` } }
  }
  if (browserAutomationRuntime.capabilities().includes(request.capability)) {
    if (request.capability === "browser.upload") {
      if (!fileContextResolver) fileContextResolver = new FileContextResolver({ deviceId: getDesktopDevice().device_id })
      const resolved = fileContextResolver.resolve(request.arguments?.file_context || request.arguments || {})
      if (resolved.status === "clarification_required") return { status: "failed", verified: true, error_code: resolved.error_code, message: resolved.message }
      request = { ...request, arguments: { ...(request.arguments || {}), file_path: resolved.local_path, authorized_roots: [path.dirname(resolved.local_path)], asset_fingerprint: resolved.fingerprint, file_reference: resolved.file_reference } }
    }
    console.log(`[CEASER] Browser request_id=${request.request_id} capability=${request.capability}`)
    return browserAutomationRuntime.execute(request)
  }
  if (localDevelopmentRuntime.capabilities().includes(request.capability) || request.capability === "development.cancel") {
    console.log(`[CEASER] Local development request_id=${request.request_id} capability=${request.capability}`)
    return localDevelopmentRuntime.execute(request)
  }
  const text = deviceCapabilityCommand(request)
  if (!text) {
    return { status: "failed", verified: true, error_code: "invalid_device_request", message: "The device command did not include enough information." }
  }
  console.log(`[CEASER] Device gateway executing request_id=${request.request_id} capability=${request.capability}`)
  return pythonVoiceCommand({
    type: "execute_command",
    version: "2.0",
    payload: {
      text,
      source: "automation",
      session_id: `device_gateway_${request.device_id}`,
      context: {
        device_gateway: true,
        task_id: request.task_id,
        agent_id: request.agent_id,
        requested_capability: request.capability,
        confirmation_requirement: request.confirmation_requirement,
      },
    },
  })
}

function ensureDeviceGateway(apiUrl = getEnv("CEASER_API_URL", "https://ceaser-backend-production-ur04.onrender.com")) {
  if (deviceGateway) {
    if (!deviceGateway.stopped) return deviceGateway
    deviceGateway.start()
    return deviceGateway
  }
  deviceGateway = new DeviceGatewayClient({
    apiUrl: apiUrl.replace(/\/$/, ""),
    getSession: readSecureDesktopSession,
    getDevice: getDesktopDevice,
    execute: executeDeviceCapability,
    capabilities: [
      ...require("../services/device-gateway-client").DEVICE_CAPABILITIES,
      ...LOCAL_DEVELOPMENT_CAPABILITIES,
      ...BROWSER_CAPABILITIES,
      "browser.open", "browser.search", "browser.tab.list", "browser.tab.open", "browser.tab.close", "browser.tab.switch",
      "development.cancel",
    ],
    onUnauthorized: async () => {
      const session = readSecureDesktopSession()
      if (!session?.refresh_token) return false
      const refreshed = await refreshDesktopSession(apiUrl, session.refresh_token)
      startupLog(`device_gateway_token_refresh_${refreshed ? "ok" : "failed"}`)
      return Boolean(refreshed)
    },
    onRevoked: () => {
      startupLog("device_gateway_revoked")
      clearSecureDesktopSession()
      authStatusCache = { value: null, expiresAt: 0 }
      overlayWindow?.webContents?.send("ceaser:auth-linked", { linked: false, reason: "revoked" })
    },
    log: (message) => {
      console.log(`[CEASER] ${message}`)
      startupLog(message)
    },
  })
  deviceGateway.start()
  return deviceGateway
}

async function refreshSecureSessionOnStartup() {
  const session = readSecureDesktopSession()
  if (!session?.refresh_token) return { linked: false, reason: "missing" }
  const apiUrl = getEnv("CEASER_API_URL", "https://ceaser-backend-production-ur04.onrender.com")
  const refreshed = await refreshDesktopSession(apiUrl, session.refresh_token)
  if (refreshed) return { linked: true, refreshed: true }
  if (session.access_token) {
    persistRuntimeAccess({ access_token: session.access_token, user_id: session.user_id, user: session.user })
    return { linked: true, refreshed: false, offline: true }
  }
  return { linked: false, reason: "refresh_failed" }
}

function warmDesktopBackend() {
  const apiUrl = getEnv("CEASER_API_URL", "https://ceaser-backend-production-ur04.onrender.com").replace(/\/$/, "")
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), DESKTOP_BACKEND_WARM_TIMEOUT_MS)
  void fetch(`${apiUrl}/health`, { signal: controller.signal })
    .then((response) => startupLog(`desktop_auth_backend_warm_http_${response.status}`))
    .catch((error) => startupLog("desktop_auth_backend_warm_deferred", error))
    .finally(() => clearTimeout(timer))
}

function pythonCompanionPath() {
  const candidates = [
    path.join(__dirname, "../../python_companion"),
    path.join(process.resourcesPath || "", "python_companion"),
  ]
  return candidates.find((candidate) => fs.existsSync(path.join(candidate, "desktop_voice_server.py"))) || candidates[0]
}

function resolvePythonLaunch() {
  const explicit = getEnv("CEASER_PYTHON", getEnv("PYTHON", ""))
  const candidatePaths = [
    explicit,
    path.join(process.resourcesPath || "", "python", "ceaser_voice_runtime.exe"),
    path.join(process.resourcesPath || "", "python", "python.exe"),
    path.join(app.getAppPath(), "python", "python.exe"),
    path.join(process.env.LOCALAPPDATA || "", "Programs", "Python", "Python313", "python.exe"),
    path.join(process.env.LOCALAPPDATA || "", "Programs", "Python", "Python312", "python.exe"),
    path.join(process.env.LOCALAPPDATA || "", "Programs", "Python", "Python311", "python.exe"),
    path.join(process.env.PROGRAMFILES || "", "Python313", "python.exe"),
    path.join(process.env.PROGRAMFILES || "", "Python312", "python.exe"),
    path.join(process.env.PROGRAMFILES || "", "Python311", "python.exe"),
  ].filter(Boolean)
  const found = candidatePaths.find((candidate) => path.isAbsolute(candidate) && fs.existsSync(candidate))
  if (found) return { command: found, argsPrefix: [], label: found }
  const pyLauncher = spawnSync("where.exe", ["py.exe"], { windowsHide: true, encoding: "utf8" })
  if (pyLauncher.status === 0) return { command: "py", argsPrefix: ["-3"], label: "py -3" }
  const pythonPath = spawnSync("where.exe", ["python.exe"], { windowsHide: true, encoding: "utf8" })
  if (pythonPath.status === 0) return { command: "python", argsPrefix: [], label: "python" }
  return { command: "", argsPrefix: [], label: "missing" }
}

function rejectPythonVoicePending(message) {
  pythonVoiceReady = false
  while (pythonVoiceReadyWaiters.length) pythonVoiceReadyWaiters.shift()?.reject(new Error(message))
  for (const { reject, timer } of pythonVoiceRequests.values()) {
    clearTimeout(timer)
    reject(new Error(message))
  }
  pythonVoiceRequests.clear()
}

function ensurePythonVoiceProcess() {
  if (pythonVoiceProcess && !pythonVoiceProcess.killed) return pythonVoiceProcess
  if (pythonVoiceUnavailable) return null
  const companionDir = pythonCompanionPath()
  const pythonDataDir = path.join(app.getPath("userData"), "python-data")
  fs.mkdirSync(pythonDataDir, { recursive: true })
  const pythonLaunch = resolvePythonLaunch()
  if (!pythonLaunch.command) {
    pythonVoiceUnavailable = {
      reason: "python_missing",
      message: "CEASER voice engine needs the bundled voice runtime or Python 3.11+ on this device.",
      launcher: "missing",
    }
    startupLog("python_voice_missing")
    return null
  }
  const apiUrl = getEnv("CEASER_API_URL", "https://ceaser-backend-production-ur04.onrender.com")
  const secureSession = readSecureDesktopSession()
  if (secureSession?.access_token && secureSession.access_token !== getEnv("CEASER_ACCESS_TOKEN")) {
    persistRuntimeAccess({ access_token: secureSession.access_token, user_id: secureSession.user_id, user: secureSession.user })
  }
  const sharedEnvNames = [
    "OPENAI_API_KEY", "OPENAI_MODEL",
    "GEMINI_API_KEY", "GEMINI_MODEL",
    "GROQ_API_KEY", "GROQ_MODEL",
    "HUGGINGFACE_API_KEY", "HUGGINGFACE_MODEL", "HF_TOKEN", "HF_MODEL",
    "WEATHER_API_KEY", "WEATHER_DEFAULT_LOCATION", "WEATHER_DEFAULT_UNITS",
    "NEWS_API_KEY", "NEWS_API_BASE_URL", "NEWS_PROVIDER", "NEWS_DEFAULT_LANGUAGE", "NEWS_DEFAULT_REGION",
    "DEEPGRAM_API_KEY", "DEEPGRAM_MODEL", "DEEPGRAM_LANGUAGE",
    "CEASER_STT_PROVIDER", "CEASER_STT_LANGUAGE", "CEASER_STT_GOOGLE_FALLBACK", "CEASER_STT_DEEPGRAM_FALLBACK", "CEASER_DEEPGRAM_STT_MODE",
    "CEASER_WAKE_WORD_ENABLED",
    "CEASER_END_SILENCE_MS", "CEASER_MAX_COMMAND_SECONDS",
    "GOOGLE_CLOUD_PROJECT", "GOOGLE_APPLICATION_CREDENTIALS",
    "CEASER_GOOGLE_STT_PRIMARY_LANGUAGE", "CEASER_GOOGLE_STT_ALTERNATIVE_LANGUAGES",
    "CEASER_TRANSLATION_PROVIDER", "CEASER_TRANSLATION_TARGET_LANGUAGE",
    "CEASER_TTS_PROVIDER", "CEASER_TTS_LANGUAGE", "CEASER_TTS_STREAMING",
    "ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID", "ELEVENLABS_BASE_URL",
    "ELEVENLABS_STT_MODEL", "ELEVENLABS_TTS_MODEL", "ELEVENLABS_TIMEOUT_SECONDS",
    "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SERVICE_KEY",
    "RAPIDAPI_KEY", "SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET",
    "CEASER_ACCESS_TOKEN", "CURRENT_USER_ID", "CEASER_DESKTOP_DEVICE_ID",
  ]
  const sharedEnv = {}
  for (const name of sharedEnvNames) {
    const value = getEnv(name)
    if (value) sharedEnv[name] = value
  }
  pythonVoiceBuffer = ""
  pythonVoiceReady = false
  pythonVoiceUnavailable = null
  pythonVoiceProcess = spawn(pythonLaunch.command, [...pythonLaunch.argsPrefix, path.join(companionDir, "desktop_voice_server.py")], {
    cwd: pythonDataDir,
    windowsHide: true,
    env: {
      ...process.env,
      ...sharedEnv,
      CEASER_PYTHON_COMPANION_DIR: companionDir,
      CEASER_LOCAL_DATA_DIR: pythonDataDir,
      CEASER_API_URL: apiUrl,
      CEASER_COMMAND_URL: `${apiUrl.replace(/\/$/, "")}/command`,
      BACKEND_URL: apiUrl,
      API_BASE_URL: apiUrl,
      VITE_BACKEND_URL: apiUrl,
      BACKEND_API_URL: apiUrl,
      OPENWEATHER_API_KEY: sharedEnv.WEATHER_API_KEY || sharedEnv.OPENWEATHER_API_KEY || "",
      GNEWS_API_KEY: sharedEnv.NEWS_API_KEY || sharedEnv.GNEWS_API_KEY || "",
      HF_TOKEN: sharedEnv.HF_TOKEN || sharedEnv.HUGGINGFACE_API_KEY || "",
      HF_MODEL: sharedEnv.HF_MODEL || sharedEnv.HUGGINGFACE_MODEL || "",
      PYTHONUTF8: "1",
    },
  })
  pythonVoiceProcess.on("error", (error) => {
    const message = error?.code === "ENOENT"
      ? "CEASER voice engine could not start because Python runtime was not found."
      : `CEASER voice engine failed to start: ${error.message || error}`
    pythonVoiceUnavailable = { reason: error?.code || "spawn_error", message, launcher: pythonLaunch.label }
    startupLog("python_voice_spawn_failed", error)
    console.warn("[CEASER] Python companion unavailable:", message)
    pythonVoiceProcess = null
    rejectPythonVoicePending(message)
    overlayWindow?.webContents?.send("ceaser:python-voice-status", { status: "error", message })
  })
  pythonVoiceProcess.stdout.on("data", (chunk) => {
    pythonVoiceBuffer += chunk.toString()
    const lines = pythonVoiceBuffer.split(/\r?\n/)
    pythonVoiceBuffer = lines.pop() || ""
    for (const line of lines) handlePythonVoiceLine(line)
  })
  pythonVoiceProcess.stderr.on("data", (chunk) => {
    const lines = chunk.toString().split(/\r?\n/).map((line) => line.trim()).filter(Boolean)
    for (const text of lines) {
      console.warn("[CEASER Python]", text)
      if (/Microphone listening started/i.test(text)) {
        overlayWindow?.webContents?.send("ceaser:python-voice-status", { status: "listening" })
      } else if (/Transcript:/i.test(text)) {
        overlayWindow?.webContents?.send("ceaser:python-voice-status", { status: "transcribing" })
      }
    }
  })
  pythonVoiceProcess.on("exit", (code, signal) => {
    startupLog(`python_voice_exited code=${code ?? "null"} signal=${signal || "none"}`)
    pythonVoiceProcess = null
    pythonVoiceReady = false
    rejectPythonVoicePending("Python companion stopped.")
    if (!appIsQuitting && !pythonVoiceUnavailable) {
      startupLog("python_voice_exited_restart_scheduled")
      if (pythonVoiceRestartTimer) clearTimeout(pythonVoiceRestartTimer)
      pythonVoiceRestartTimer = setTimeout(() => {
        pythonVoiceRestartTimer = null
        try {
          ensurePythonVoiceProcess()
        } catch (error) {
          startupLog("python_voice_restart_failed", error)
        }
      }, 1200)
    }
  })
  return pythonVoiceProcess
}

function cleanupBundledPythonState(companionDir) {
  const names = [
    "chroma_db",
    "amazon_shopping.db",
    "language_learning.db",
    "memory.db",
    "memory.db-shm",
    "memory.db-wal",
    "multimodal.db",
    "multiuser.db",
    "proactive.db",
    "reminders_local.db",
    "vault.db",
    "vision.db",
    "web_automation.db",
  ]
  for (const name of names) {
    const target = path.join(companionDir, name)
    try {
      if (fs.existsSync(target)) fs.rmSync(target, { recursive: true, force: true })
    } catch (_error) {
      // Existing dev process may still hold the copied reference DB. It will be retried next launch.
    }
  }
}

function handlePythonVoiceLine(line) {
  const value = String(line || "").trim()
  if (!value) return
  if (!value.startsWith("CEASER_JSON:")) {
    console.log("[CEASER Python]", value)
    return
  }
  let payload
  try {
    payload = JSON.parse(value.slice("CEASER_JSON:".length))
  } catch (_error) {
    return
  }
  if (payload.id === "ready") {
    pythonVoiceReady = true
    console.log("[CEASER] Python companion ready")
    overlayWindow?.webContents?.send("ceaser:python-ready", payload)
    while (pythonVoiceReadyWaiters.length) pythonVoiceReadyWaiters.shift()?.resolve()
    return
  }
  if (payload.id === "voice_status") {
    console.log(`[CEASER] Python voice status: ${payload.status}${payload.provider ? ` (${payload.provider})` : ""}${payload.passive ? " passive" : ""}`)
    overlayWindow?.webContents?.send("ceaser:python-voice-status", payload)
    return
  }
  if (payload.version === "2.0" && payload.type === "event") {
    if (payload.event === "voice_state") {
      const statusPayload = {
        id: "voice_status",
        status: payload.payload?.state || payload.payload?.status || "unknown",
        ...(payload.payload || {}),
      }
      console.log(`[CEASER] Python voice state: ${statusPayload.status}`)
      overlayWindow?.webContents?.send("ceaser:python-voice-status", statusPayload)
    } else {
      console.log(`[CEASER] Python event: ${payload.event}`)
      overlayWindow?.webContents?.send("ceaser:python-event", payload)
    }
    return
  }
  const pending = pythonVoiceRequests.get(payload.id)
  if (!pending) return
  clearTimeout(pending.timer)
  pythonVoiceRequests.delete(payload.id)
  pending.resolve(payload)
}

function pythonVoiceCommand(payload = {}) {
  const proc = ensurePythonVoiceProcess()
  if (!proc) {
    const message = pythonVoiceUnavailable?.message || "CEASER voice engine is unavailable."
    return Promise.resolve({ status: "error", message, context_kind: "voice_engine", transcript: "" })
  }
  const id = `pyvoice_${Date.now()}_${pythonVoiceRequestCounter += 1}`
  return new Promise((resolve, reject) => {
    let waiter = null
    const requestType = payload?.type || "listen_once"
    const requestTimeoutMs = requestType === "listen_wake_command" ? 24 * 60 * 60 * 1000 : 90000
    const timer = setTimeout(() => {
      pythonVoiceRequests.delete(id)
      if (waiter) waiter.cancelled = true
      reject(new Error("Python voice command timed out."))
    }, requestTimeoutMs)
    pythonVoiceRequests.set(id, { resolve, reject, timer })
    const send = () => {
      console.log(`[CEASER] Python companion request: ${requestType}`)
      try {
        proc.stdin.write(`${JSON.stringify({ id, type: "listen_once", ...payload })}\n`)
      } catch (error) {
        clearTimeout(timer)
        pythonVoiceRequests.delete(id)
        reject(error)
      }
    }
    if (pythonVoiceReady) send()
    else {
      waiter = {
        cancelled: false,
        resolve: () => {
          if (!waiter.cancelled) send()
        },
        reject,
      }
      pythonVoiceReadyWaiters.push(waiter)
    }
  })
}

app.disableHardwareAcceleration()
app.commandLine.appendSwitch("disable-gpu")
app.commandLine.appendSwitch("disable-gpu-compositing")
app.commandLine.appendSwitch("disable-features", "HardwareMediaKeyHandling")
app.setName("CEASER")
if (process.env.CEASER_DEV_USER_DATA === "true" || process.defaultApp) {
  app.setPath("userData", path.join(app.getPath("appData"), "CEASER Dev"))
}
function registerDesktopProtocolClient() {
  try {
    if (process.defaultApp && process.argv.length >= 2) {
      app.setAsDefaultProtocolClient("ceaser-app", process.execPath, [path.resolve(process.argv[1])])
      app.setAsDefaultProtocolClient("ceaser", process.execPath, [path.resolve(process.argv[1])])
    } else {
      app.setAsDefaultProtocolClient("ceaser-app")
      app.setAsDefaultProtocolClient("ceaser")
    }
  } catch (error) {
    console.warn("[CEASER] Could not register desktop auth protocol:", error.message || error)
  }
}

function isHiddenStartupLaunch() {
  return process.argv.some((arg) => /--hidden|--hide|--minimized|--background|--startup/i.test(String(arg || "")))
}

function configureLoginStartup() {
  if (!app.isPackaged || process.env.CEASER_DISABLE_AUTOSTART === "true") return
  try {
    app.setLoginItemSettings({
      openAtLogin: true,
      openAsHidden: true,
      path: process.execPath,
    })
    startupLog(`autostart_enabled=${app.getLoginItemSettings().openAtLogin}`)
  } catch (error) {
    startupLog("autostart_failed", error)
    console.warn("[CEASER] Could not enable launch on startup:", error.message || error)
  }
}

function findDeepLinkArg(argv = process.argv) {
  return (argv || []).find((arg) => {
    const value = String(arg || "")
    return value.startsWith("ceaser-app://") || value.startsWith("ceaser://")
  })
}

registerDesktopProtocolClient()
startupLog("protocol_registered")

const gotSingleInstanceLock = app.requestSingleInstanceLock()
startupLog(`single_instance_lock=${gotSingleInstanceLock}`)
if (!gotSingleInstanceLock) {
  app.quit()
} else {
  app.on("second-instance", (_event, argv) => {
    const deepLink = findDeepLinkArg(argv)
    if (deepLink && handleDeepLink(deepLink)) return
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.show()
      mainWindow.focus()
    }
  })
}

app.on("open-url", (event, url) => {
  event.preventDefault()
  handleDeepLink(url)
})

function registerBundledAppProtocol() {
  protocol.handle("ceaser-app", (request) => {
    const url = new URL(request.url)
    const resourceRoot = path.join(process.resourcesPath || "", "frontend", "out")
    const pathname = decodeURIComponent(url.pathname || "/")
    const normalized = pathname === "/" ? "/index.html" : pathname
    const candidate = path.join(resourceRoot, normalized)
    const filePath = fs.existsSync(candidate) && fs.statSync(candidate).isFile()
      ? candidate
      : path.join(resourceRoot, normalized, "index.html")
    const fallback = fs.existsSync(filePath) ? filePath : path.join(resourceRoot, "index.html")
    return new Response(fs.createReadStream(fallback))
  })
}

function createMainWindow() {
  if (mainWindow) return mainWindow

  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1100,
    minHeight: 760,
    show: false,
    frame: false,
    titleBarStyle: "hidden",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  })

  mainWindow.once("ready-to-show", () => {
    mainWindow.show()
    mainWindow.focus()
  })
  mainWindow.on("closed", () => {
    mainWindow = null
  })

  const appUrl = resolveAppUrl({ getEnv })
  if (appUrl.startsWith("http://") || appUrl.startsWith("https://")) {
    mainWindow.loadURL(appUrl)
  } else {
    mainWindow.loadURL(appUrl)
  }

  if (process.env.NODE_ENV === "development") {
    mainWindow.webContents.openDevTools()
  }

  return mainWindow
}

function createOverlay() {
  const bounds = compactBounds()
  overlayWindow = new BrowserWindow({
    x: bounds.x,
    y: bounds.y,
    width: bounds.width,
    height: bounds.height,
    minWidth: 1,
    minHeight: 1,
    frame: false,
    transparent: true,
    resizable: false,
    thickFrame: false,
    hasShadow: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    backgroundColor: "#00000000",
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  })
  overlayWindow.once("ready-to-show", () => {
    restoreOverlayWindow({ reason: "ready_to_show", resize: "compact" })
  })
  overlayWindow.webContents.once("did-finish-load", () => {
    overlayReady = true
    overlayWindow?.setIgnoreMouseEvents(true, { forward: true })
  })
  overlayWindow.webContents.on("console-message", (_event, level, message, line, sourceId) => {
    const prefix = level >= 2 ? "ERROR" : level === 1 ? "WARN" : "LOG"
    console.log(`[CEASER renderer ${prefix}] ${message} (${sourceId}:${line})`)
  })
  overlayWindow.on("closed", () => {
    overlayWindow = null
    overlayReady = false
  })
  overlayWindow.loadFile(path.join(__dirname, "../renderer/index.html"))
}

app.whenReady().then(() => {
  startupLog("when_ready_started")
  startupPhase("electron_ready")
  Menu.setApplicationMenu(null)
  configureLoginStartup()
  registerBundledAppProtocol()
  startupLog("bundled_protocol_registered")
  
  // Set up media permissions before creating windows
  session.defaultSession.setPermissionRequestHandler((_webContents, permission, callback) => {
    if (permission === "media" || permission === "microphone" || permission === "audioCapture") {
      callback(true)
    } else {
      callback(false)
    }
  })
  session.defaultSession.setPermissionCheckHandler((_webContents, permission) => {
    return permission === "media" || permission === "microphone" || permission === "audioCapture"
  })
  
  createOverlay()
  startupLog("overlay_created")
  startupPhase("renderer_created")
  createTray()
  startupLog("tray_created")
  registerVoiceHotkey()
  startupLog("hotkey_registered")
  startupLog("legacy_hold_key_watcher_disabled")
  refreshSecureSessionOnStartup().then(async (result) => {
    startupLog(`secure_session_startup=${JSON.stringify(result)}`)
    const auth = result?.linked ? result : await validateDesktopSession()
    if (!auth?.linked && overlayWindow && !overlayWindow.isDestroyed()) {
      overlayWindow.setIgnoreMouseEvents(false)
      restoreOverlayWindow({ reason: "auth_required", resize: "expanded" })
      startupLog("account_connection_overlay_shown")
    }
  })
  const forwardPowerState = (state) => {
    overlayWindow?.webContents.send("ceaser:system-power", { state })
    pythonVoiceCommand({ type: "power_event", state }).catch((error) => startupLog("python_power_event_failed", error))
    if (state === "resume" || state === "unlock-screen") deviceGateway?.restart()
  }
  powerMonitor.on("suspend", () => forwardPowerState("suspend"))
  powerMonitor.on("resume", () => forwardPowerState("resume"))
  powerMonitor.on("lock-screen", () => forwardPowerState("lock-screen"))
  powerMonitor.on("unlock-screen", () => forwardPowerState("unlock-screen"))
  const startupDeepLink = findDeepLinkArg()
  if (startupDeepLink) handleDeepLink(startupDeepLink)
  setTimeout(() => {
    try {
      ensurePythonVoiceProcess()
      startupLog("python_warmup_started")
      startupPhase("python_spawned")
    } catch (error) {
      startupLog("python_warmup_failed", error)
      console.warn("[CEASER] Python companion warmup skipped:", error.message || error)
    }
  }, 350).unref?.()
  if (applicationIndexNeedsRefresh()) {
    setTimeout(() => {
      refreshApplicationIndex("startup-background-stale-cache").catch((error) => startupLog("app_discovery_refresh_failed", error))
    }, 20000).unref?.()
  } else {
    startupLog("app_discovery_cache_fresh_refresh_skipped")
  }
})
app.whenReady().then(() => {
  session.defaultSession.setPermissionRequestHandler((_webContents, permission, callback) => {
    callback(permission === "media" || permission === "microphone" || permission === "audioCapture")
  })
  session.defaultSession.setPermissionCheckHandler((_webContents, permission) => permission === "media" || permission === "microphone" || permission === "audioCapture")
})
app.on("window-all-closed", () => {
  // CEASER is a resident companion. Closing windows should keep the tray/hotkey alive.
})
app.on("before-quit", () => {
  appIsQuitting = true
  deviceGateway?.stop()
  if (deviceRegistrationRetryTimer) clearTimeout(deviceRegistrationRetryTimer)
  if (pythonVoiceRestartTimer) clearTimeout(pythonVoiceRestartTimer)
  if (holdWatcherRestartTimer) clearTimeout(holdWatcherRestartTimer)
  if (holdKeyWatcher) holdKeyWatcher.kill()
  if (pythonVoiceProcess && !pythonVoiceProcess.killed) {
    try {
      pythonVoiceProcess.stdin.write("__quit__\n")
    } catch (_error) {
      // Best-effort shutdown.
    }
    pythonVoiceProcess.kill()
  }
  globalShortcut.unregisterAll()
})

ipcMain.handle("ceaser:classify", async () => ({
  status: "error",
  error_code: "legacy_command_path_disabled",
  message: "Legacy command routing is disabled. Use the CEASER command service.",
}))
ipcMain.handle("ceaser:execute", async () => ({
  status: "error",
  error_code: "legacy_command_path_disabled",
  message: "Legacy command routing is disabled. Use the CEASER command service.",
}))
ipcMain.handle("ceaser:run-agent", async (_event, payload) => runAgent(payload))
ipcMain.handle("ceaser:pick-media", async () => {
  const result = await dialog.showOpenDialog({ properties: ["openFile"], filters: [{ name: "Images and videos", extensions: ["jpg", "jpeg", "png", "webp", "gif", "mp4", "mov", "webm", "m4v"] }] })
  if (result.canceled || !result.filePaths[0]) return { status: "cancelled" }
  if (!fileContextResolver) fileContextResolver = new FileContextResolver({ deviceId: getDesktopDevice().device_id })
  const context = fileContextResolver.register({ local_path: result.filePaths[0], source: "file_picker" })
  return context ? { status: "selected", desktop_file_context: context } : { status: "blocked", error_code: "invalid_file_context" }
})
ipcMain.handle("ceaser:register-file-context", async (_event, payload = {}) => {
  if (!fileContextResolver) fileContextResolver = new FileContextResolver({ deviceId: getDesktopDevice().device_id })
  const context = fileContextResolver.register({ local_path: payload.path, source: "file_picker" })
  return context ? { status: "selected", desktop_file_context: context } : { status: "blocked", error_code: "invalid_file_context" }
})
ipcMain.handle("ceaser:create-document", async (_event, payload) => createDocument(payload))
ipcMain.handle("ceaser:answer-question", async (_event, payload) => answerQuestion(payload))
ipcMain.handle("ceaser:identity", async (_event, payload) => identityService.generate(payload))
ipcMain.handle("ceaser:cancel-task", async (_event, payload) => cancelTask(payload?.task_id))
ipcMain.handle("ceaser:python-voice-command", async (_event, payload) => pythonVoiceCommand(payload))
ipcMain.handle("ceaser:app-action", async (_event, payload = {}) => {
  const action = String(payload.action || "").trim().toLowerCase()
  const requestedApp = String(payload.app || "").trim()
  if (action === "refresh") return refreshApps()
  if (!requestedApp) return { status: "error", message: "App name is required." }
  if (action === "open") {
    return launchApp(requestedApp, {
      forceNew: Boolean(payload.force_new),
      profileName: String(payload.profile_name || "").trim() || undefined,
    })
  }
  if (action === "close") return closeApp(requestedApp)
  return { status: "error", message: "Unsupported application action." }
})
ipcMain.handle("ceaser:media-duck", async (_event, payload) => duckMediaForListening(payload))
ipcMain.handle("ceaser:media-restore", async () => restoreMediaAfterListening())
ipcMain.handle("ceaser:python-voice-status", async () => ({
  ready: pythonVoiceReady,
  running: Boolean(ensurePythonVoiceProcess() && pythonVoiceProcess && !pythonVoiceProcess.killed),
  unavailable: pythonVoiceUnavailable,
}))
ipcMain.handle("ceaser:runtime-logs", async () => ({
  entries: runtimeLogEntries.slice(-250),
  file: runtimeLogPath(),
  python: {
    ready: pythonVoiceReady,
    running: Boolean(pythonVoiceProcess && !pythonVoiceProcess.killed),
    unavailable: pythonVoiceUnavailable,
  },
}))
ipcMain.handle("ceaser:open-logs-folder", async () => {
  const directory = path.dirname(runtimeLogPath())
  const error = await shell.openPath(directory)
  return { status: error ? "error" : "opened", message: error || directory }
})
ipcMain.handle("ceaser:permissions:get", async () => permissions.all())
ipcMain.handle("ceaser:permissions:set", async (_event, payload) => permissions.set(payload.key, payload.value))
ipcMain.handle("ceaser:context", async () => contextService.snapshot())
ipcMain.handle("ceaser:auth-status", async () => validateDesktopSession())
ipcMain.handle("ceaser:open-auth", async () => {
  const appUrl = consoleAppUrl().replace(/\/$/, "")
  warmDesktopBackend()
  pendingPkce = createPkceChallenge()
  const device = getDesktopDevice()
  const params = new URLSearchParams({
    desktop_link: "1",
    response_type: "code",
    code_challenge: pendingPkce.challenge,
    code_challenge_method: "S256",
    state: pendingPkce.state,
    redirect_uri: authRedirectUri(),
    device_id: device.device_id,
    device_name: device.device_name,
    app_version: device.app_version,
  })
  const target = `${appUrl}/auth/desktop?${params.toString()}`
  await shell.openExternal(target)
  return { status: "opened", url: target }
})
ipcMain.handle("ceaser:voice-compose", async (_event, payload) => insertTextAtFocus(payload?.text, payload?.context))
ipcMain.handle("ceaser:open-url", async (_event, url) => {
  const value = String(url || "").trim()
  if (!/^https?:\/\//i.test(value) && !/^mailto:/i.test(value)) return { status: "error", message: "Invalid URL." }
  await shell.openExternal(value)
  return { status: "completed", message: "Opened." }
})
ipcMain.handle("ceaser:copy-text", async (_event, text) => {
  clipboard.writeText(String(text || ""))
  return { status: "completed", message: "Copied." }
})
ipcMain.handle("ceaser:open-full-app", async () => {
  const appUrl = resolveAppUrl({ getEnv })
  if (mainWindow && !mainWindow.isDestroyed()) {
    if (mainWindow.isMinimized()) mainWindow.restore()
    mainWindow.show()
    mainWindow.focus()
    if (appUrl.startsWith("http://") || appUrl.startsWith("https://")) {
      mainWindow.loadURL(appUrl)
    } else {
      mainWindow.loadURL(appUrl)
    }
    return appUrl
  }
  if (appUrl.startsWith("http://") || appUrl.startsWith("https://")) {
    shell.openExternal(appUrl)
  }
  return appUrl
})
ipcMain.handle("ceaser:autostart:get", async () => app.getLoginItemSettings().openAtLogin)
ipcMain.handle("ceaser:autostart:set", async (_event, enabled) => {
  app.setLoginItemSettings({ openAtLogin: Boolean(enabled), openAsHidden: true, path: process.execPath })
  return app.getLoginItemSettings().openAtLogin
})
ipcMain.handle("ceaser:window-minimize", async () => {
  if (mainWindow && !mainWindow.isDestroyed()) mainWindow.minimize()
})
ipcMain.handle("ceaser:window-maximize", async () => {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.isMaximized() ? mainWindow.unmaximize() : mainWindow.maximize()
  }
})
ipcMain.handle("ceaser:window-close", async () => {
  if (mainWindow && !mainWindow.isDestroyed()) mainWindow.close()
})
ipcMain.handle("ceaser:window-is-maximized", async () => {
  return mainWindow && !mainWindow.isDestroyed() ? mainWindow.isMaximized() : false
})

ipcMain.handle("ceaser:hide-overlay", async (_event, options = {}) => {
  const reason = options?.reason || (options?.force ? "explicit_session_end" : "overlay_hidden")
  return hideOverlayWindow({ reason })
})

ipcMain.handle("ceaser:show-overlay", async () => {
  return restoreOverlayWindow({ reason: "renderer_request", resize: "compact" })
})

ipcMain.handle("ceaser:overlay-interactive", async (_event, interactive) => {
  if (!overlayWindow || overlayWindow.isDestroyed()) return false
  overlayWindow.setIgnoreMouseEvents(!Boolean(interactive), { forward: true })
  return true
})

ipcMain.handle("ceaser:set-mode", async (_event, mode) => {
  if (!overlayWindow) return
  const nextMode = mode === "minimal" ? "compact" : mode
  const sizes = { compact: [386, 70], expanded: [458, 360] }
  const [width, height] = sizes[nextMode] || sizes.compact
  lastOverlaySize = { width, height }
  overlayWindow.setSize(width, height)
  if (nextMode === "compact") {
    positionTopCenter(width, height)
  } else {
    const bounds = expandedBounds()
    overlayWindow.setPosition(bounds.x, bounds.y)
  }
})
ipcMain.handle("ceaser:fit-content", async (_event, size) => {
  if (!overlayWindow) return
  const workArea = screen.getPrimaryDisplay().workAreaSize
  const current = overlayWindow.getBounds()
  const expandedLike = Number(size.width) >= 430 || current.width >= 430
  const minWidth = expandedLike ? 458 : 88
  const minHeight = expandedLike ? 314 : 88
  const width = Math.min(Math.max(Number(size.width) || minWidth, minWidth), Math.min(workArea.width - 40, 648))
  const height = Math.min(Math.max(Number(size.height) || minHeight, minHeight), workArea.height - 60)
  const next = { width: Math.ceil(width), height: Math.ceil(height) }
  if (Math.abs(next.width - lastOverlaySize.width) < 2 && Math.abs(next.height - lastOverlaySize.height) < 2) return
  lastOverlaySize = next
  overlayWindow.setSize(next.width, next.height)
  if (next.width <= 420) positionTopCenter(next.width, next.height)
})

function compactBounds() {
  const display = screen.getPrimaryDisplay()
  const area = display.workArea
  const width = 386
  const height = 70
  return {
    width,
    height,
    x: Math.round(area.x + (area.width - width) / 2),
    y: Math.round(area.y + 28),
  }
}

function expandedBounds() {
  const display = screen.getPrimaryDisplay()
  const area = display.workArea
  const width = Math.min(520, Math.max(458, area.width - 80))
  const height = Math.min(440, Math.max(360, area.height - 120))
  return {
    width,
    height,
    x: Math.round(area.x + (area.width - width) / 2),
    y: Math.round(area.y + 28),
  }
}

function sendOverlayVisibility(visible, reason = "unknown") {
  overlayVisibilityState = visible ? "visible" : "hidden"
  if (!overlayWindow || overlayWindow.isDestroyed()) return
  try {
    overlayWindow.webContents.send("ceaser:overlay-visibility", { visible, reason })
  } catch (_error) {
    // Renderer navigation can race visibility changes.
  }
}

function restoreOverlayWindow({ reason = "restore", resize = null } = {}) {
  if (!overlayWindow || overlayWindow.isDestroyed()) return { hidden: false, reason: "overlay_missing" }
  if (resize === "compact") {
    const bounds = compactBounds()
    overlayWindow.setSize(bounds.width, bounds.height)
    overlayWindow.setPosition(bounds.x, bounds.y)
  } else if (resize === "expanded") {
    const bounds = expandedBounds()
    overlayWindow.setSize(bounds.width, bounds.height)
    overlayWindow.setPosition(bounds.x, bounds.y)
  }
  overlayWindow.show()
  overlayWindow.focus()
  overlayWindow.moveTop()
  overlayWindow.webContents.focus()
  sendOverlayVisibility(true, reason)
  return { hidden: false, reason }
}

function hideOverlayWindow({ reason = "overlay_hidden" } = {}) {
  if (!overlayWindow || overlayWindow.isDestroyed()) return { hidden: false, reason: "overlay_missing" }
  overlayWindow.hide()
  sendOverlayVisibility(false, reason)
  return { hidden: true, reason }
}

function createTray() {
  const iconPath = fs.existsSync(path.join(process.resourcesPath || "", "favicon-64.png"))
    ? path.join(process.resourcesPath, "favicon-64.png")
    : path.join(__dirname, "../../../website/console/public/favicon-64.png")
  const icon = nativeImage.createFromPath(iconPath)
  tray = new Tray(icon.isEmpty() ? nativeImage.createEmpty() : icon.resize({ width: 18, height: 18 }))
  tray.setToolTip("CEASER OS")
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: "Open CEASER", click: () => restoreOverlayWindow({ reason: "tray_open" }) },
      { label: "Show Overlay", click: summonListeningOverlay },
      { label: "Connect CEASER Account", click: async () => {
        const appUrl = consoleAppUrl().replace(/\/$/, "")
        warmDesktopBackend()
        pendingPkce = createPkceChallenge()
        const device = getDesktopDevice()
        const params = new URLSearchParams({
          desktop_link: "1",
          response_type: "code",
          code_challenge: pendingPkce.challenge,
          code_challenge_method: "S256",
          state: pendingPkce.state,
          redirect_uri: authRedirectUri(),
          device_id: device.device_id,
          device_name: device.device_name,
          app_version: device.app_version,
        })
        await shell.openExternal(`${appUrl}/auth/desktop?${params.toString()}`)
      } },
      {
        label: "Launch on Startup",
        type: "checkbox",
        checked: app.getLoginItemSettings().openAtLogin,
        click: (item) => app.setLoginItemSettings({ openAtLogin: item.checked, openAsHidden: true, path: process.execPath }),
      },
      { type: "separator" },
      {
        label: "Quit CEASER",
        click: () => {
          app.isQuitting = true
          app.quit()
        },
      },
    ]),
  )
  tray.on("click", () => restoreOverlayWindow({ reason: "tray_click" }))
}

function positionTopCenter(width = 292, height = 164) {
  if (!overlayWindow) return
  const area = screen.getPrimaryDisplay().workArea
  overlayWindow.setPosition(Math.round(area.x + (area.width - width) / 2), Math.round(area.y + 28))
}

function summonListeningOverlay() {
  if (!overlayWindow) return
  console.log("[CEASER] Wake session hotkey triggered")
  restoreOverlayWindow({ reason: "wake_session", resize: "compact" })
  const payload = { mode: "wake_session" }
  if (overlayReady) overlayWindow.webContents.send("ceaser:start-listening", payload)
  else overlayWindow.webContents.once("did-finish-load", () => overlayWindow?.webContents.send("ceaser:start-listening", payload))
}

function registerVoiceHotkey() {
  const candidates = [...new Set([VOICE_HOTKEY, ...VOICE_HOTKEY_FALLBACKS])]
  for (const hotkey of candidates) {
    const registered = globalShortcut.register(hotkey, summonListeningOverlay)
    if (registered) {
      activeVoiceHotkey = hotkey
      if (hotkey !== VOICE_HOTKEY) {
        console.warn(`[CEASER] Preferred voice hotkey unavailable: ${VOICE_HOTKEY}; using ${hotkey}`)
      }
      console.log(`[CEASER] Voice hotkey registered: ${hotkey}`)
      return
    }
  }
  console.warn(`[CEASER] Could not register any voice hotkey: ${candidates.join(", ")}`)
}

async function startHoldVoiceOverlay() {
  if (!overlayWindow || holdSessionActive) return
  holdSessionActive = true
  holdSessionId += 1
  holdVoiceContext = await contextService.snapshot()
  const bounds = compactBounds()
  overlayWindow.setSize(bounds.width, bounds.height)
  overlayWindow.setPosition(bounds.x, bounds.y)
  overlayWindow.show()
  overlayWindow.focus()
  overlayWindow.moveTop()
  overlayWindow.webContents.focus()
  const payload = {
    mode: "hold",
    sessionId: holdSessionId,
    context: holdVoiceContext,
  }
  if (overlayReady) overlayWindow.webContents.send("ceaser:start-listening", payload)
  else overlayWindow.webContents.once("did-finish-load", () => overlayWindow?.webContents.send("ceaser:start-listening", payload))
}

function stopHoldVoiceOverlay() {
  if (!overlayWindow || !holdSessionActive) return
  overlayWindow.webContents.send("ceaser:stop-listening", {
    mode: "hold",
    sessionId: holdSessionId,
    context: holdVoiceContext,
  })
  holdSessionActive = false
}

function startHoldKeyWatcher() {
  if (process.platform !== "win32" || holdKeyWatcher) return
  const script = `
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class KeyState {
  [DllImport("user32.dll")] public static extern short GetAsyncKeyState(int vKey);
}
"@
$wasDown = $false
while ($true) {
  $ctrl = (([KeyState]::GetAsyncKeyState(0x11) -band 0x8000) -ne 0) -or (([KeyState]::GetAsyncKeyState(0xA2) -band 0x8000) -ne 0) -or (([KeyState]::GetAsyncKeyState(0xA3) -band 0x8000) -ne 0)
  $shift = (([KeyState]::GetAsyncKeyState(0x10) -band 0x8000) -ne 0) -or (([KeyState]::GetAsyncKeyState(0xA0) -band 0x8000) -ne 0) -or (([KeyState]::GetAsyncKeyState(0xA1) -band 0x8000) -ne 0)
  $space = ([KeyState]::GetAsyncKeyState(0x20) -band 0x8000) -ne 0
  $isDown = $ctrl -and $shift -and $space
  if ($isDown) {
    if (-not $wasDown) { Write-Output "WAKE_HOTKEY"; [Console]::Out.Flush() }
    $wasDown = $true
  } else {
    $wasDown = $false
  }
  Start-Sleep -Milliseconds 35
}
`
  holdKeyWatcher = spawn("powershell.exe", ["-NoProfile", "-Command", script], { windowsHide: true })
  holdKeyWatcher.stdout.on("data", (chunk) => {
    for (const line of String(chunk).split(/\r?\n/)) {
      if (line.trim() === "WAKE_HOTKEY") summonListeningOverlay()
    }
  })
  holdKeyWatcher.stderr.on("data", (chunk) => {
    const message = String(chunk || "").trim()
    if (message) console.warn("[CEASER] Wake hotkey watcher:", message)
  })
  holdKeyWatcher.on("exit", () => {
    holdKeyWatcher = null
    holdSessionActive = false
    if (!app.isQuitting) {
      clearTimeout(holdWatcherRestartTimer)
      holdWatcherRestartTimer = setTimeout(startHoldKeyWatcher, 750)
    }
  })
}

function createTaskController(taskId) {
  if (!taskId) return null
  const controller = new AbortController()
  activeTasks.set(taskId, controller)
  return controller
}

function finishTask(taskId, controller) {
  if (taskId && activeTasks.get(taskId) === controller) activeTasks.delete(taskId)
}

function cancelTask(taskId) {
  const controller = activeTasks.get(taskId)
  if (!controller) return { status: "idle", message: "No active task to cancel." }
  controller.abort()
  activeTasks.delete(taskId)
  return { status: "cancelled", message: "Stopped the current task." }
}

async function answerQuestion(payload = {}) {
  const question = String(payload.question || "").trim()
  if (!question) return { status: "error", answer: "I did not receive a question." }
  const key = getEnv("GEMINI_API_KEY")
  const model = getEnv("GEMINI_MODEL", "gemini-2.5-flash")
  if (!key) return { status: "error", answer: "Gemini API key is not configured." }
  const taskId = payload.task_id
  const controller = createTaskController(taskId)
  try {
    let response = await geminiRequest(key, model, answerPrompt(question), 520, controller?.signal)
    if (!response.ok) return { status: "error", answer: "I could not get an answer from Gemini." }
    let data = await response.json()
    let answer = extractGeminiText(data)
    if (looksIncomplete(answer)) {
      response = await geminiRequest(key, model, completionPrompt(question, answer), 520, controller?.signal)
      if (response.ok) {
        data = await response.json()
        answer = extractGeminiText(data) || answer
      }
    }
    return { status: answer ? "completed" : "error", answer: answer || "I could not find a clear answer." }
  } catch (error) {
    if (error?.name === "AbortError") return { status: "cancelled", answer: "Stopped." }
    return { status: "error", answer: "Gemini is unavailable right now." }
  } finally {
    finishTask(taskId, controller)
  }
}

function answerPrompt(question) {
  return `Answer the user clearly and completely in 3-5 sentences.
Use plain language. Do not include markdown headings.
Never stop mid-sentence. If a topic needs more detail, give the useful core answer first.
If it is a current-events question and you are unsure, say it may need live verification.

Question: ${question}`
}

function completionPrompt(question, partialAnswer) {
  return `The previous answer was incomplete.
Question: ${question}
Partial answer: ${partialAnswer}

Now provide a complete corrected answer in 3-5 sentences. Do not stop mid-sentence.`
}

function looksIncomplete(answer) {
  const text = String(answer || "").trim()
  if (!text) return true
  if (text.split(/\s+/).length < 8) return true
  return !/[.!?)]$/.test(text)
}

async function geminiRequest(key, model, prompt, maxOutputTokens, signal) {
  return fetchWithTimeout(
    `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-goog-api-key": key,
      },
      body: JSON.stringify({
        contents: [
          {
            role: "user",
            parts: [{ text: prompt }],
          },
        ],
        generationConfig: {
          temperature: 0.25,
          maxOutputTokens,
          thinkingConfig: { thinkingBudget: 0 },
        },
      }),
    },
    signal,
    9000,
  )
}

async function fetchWithTimeout(url, options = {}, externalSignal, timeoutMs = 10000) {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), timeoutMs)
  const abortFromExternal = () => controller.abort()
  if (externalSignal) {
    if (externalSignal.aborted) controller.abort()
    else externalSignal.addEventListener("abort", abortFromExternal, { once: true })
  }
  try {
    return await fetch(url, { ...options, signal: controller.signal })
  } finally {
    clearTimeout(timeout)
    externalSignal?.removeEventListener?.("abort", abortFromExternal)
  }
}

function extractGeminiText(data) {
  return data?.candidates?.[0]?.content?.parts?.map((part) => part.text || "").join(" ").replace(/\s+/g, " ").trim() || ""
}

async function runAgent(payload = {}) {
  const intent = payload.intent || {}
  const message = String(payload.message || intent.parameters?.message || "").trim()
  const agent = String(intent.active_agent || "CEASER")
  if (!message) return { status: "error", message: "I did not receive an agent request." }
  const taskId = payload.task_id
  const controller = createTaskController(taskId)

  try {
    const backend = await runBackendAgent(message, controller?.signal, payload.desktop_file_context)
    if (backend.status === "completed") return backend

    return await runGeminiAgent(message, agent, controller?.signal)
  } catch (error) {
    if (error?.name === "AbortError") return { status: "cancelled", message: "Stopped." }
    return { status: "error", message: `${agent} is unavailable right now.` }
  } finally {
    finishTask(taskId, controller)
  }
}

async function createDocument(payload = {}) {
  const intent = payload.intent || {}
  const parameters = intent.parameters || {}
  const prompt = String(parameters.prompt || parameters.message || payload.message || "").trim()
  const kind = String(parameters.kind || "docx").toLowerCase()
  const agentId = String(parameters.agent_id || "bolt").toLowerCase()
  const token = getEnv("CEASER_ACCESS_TOKEN")
  const apiUrl = getEnv("CEASER_API_URL", "https://ceaser-backend-production-ur04.onrender.com")
  const appUrl = consoleAppUrl()

  if (!prompt) return { status: "error", message: "I did not receive a document request." }
  if (!token) {
    await shell.openExternal(`${appUrl}/?view=files`)
    return {
      status: "error",
      message: "Open CEASER and sign in first. The desktop companion needs your CEASER session before it can save generated documents.",
    }
  }

  const taskId = payload.task_id
  const controller = createTaskController(taskId)
  try {
    const response = await fetch(`${apiUrl}/documents`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ prompt, kind, agent_id: agentId }),
      signal: controller?.signal,
    })
    if (!response.ok) {
      let detail = "Document generation failed."
      try {
        const payload = await response.json()
        detail = typeof payload?.detail === "string" ? payload.detail : detail
      } catch {
        // keep friendly message
      }
      return { status: "error", message: detail }
    }
    const data = await response.json()
    await shell.openExternal(`${appUrl}/?view=files`)
    return {
      status: "completed",
      message: `Created ${data?.document?.file_name || kind.toUpperCase()} and opened CEASER Files.`,
      document: data?.document,
      file: data?.file,
      preview: data?.preview,
    }
  } catch (error) {
    if (error?.name === "AbortError") return { status: "cancelled", message: "Stopped." }
    return { status: "error", message: "Document generation is unavailable right now." }
  } finally {
    finishTask(taskId, controller)
  }
}

async function runBackendAgent(message, signal, desktopFileContext = null) {
  const token = getEnv("CEASER_ACCESS_TOKEN")
  const apiUrl = getEnv("CEASER_API_URL", "https://ceaser-backend-production-ur04.onrender.com")
  if (!token) return { status: "skipped", message: "Backend token not configured." }
  try {
    const response = await fetch(`${apiUrl}/ceaser/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ message, device_id: getDesktopDevice().device_id, desktop_file_context: desktopFileContext }),
      signal,
    })
    if (!response.ok) return { status: "error", message: "Backend agent request failed." }
    const data = await response.json()
    return {
      status: "completed",
      message: cleanAgentResponse(data.response || data.contribution_summary || "Agent work completed."),
      data,
    }
  } catch (error) {
    if (error?.name === "AbortError") throw error
    return { status: "error", message: "Backend agent request unavailable." }
  }
}

async function runGeminiAgent(message, agent, signal) {
  const key = getEnv("GEMINI_API_KEY")
  const model = getEnv("GEMINI_MODEL", "gemini-2.5-flash")
  if (!key) return { status: "error", message: "Gemini API key is not configured." }
  try {
    const response = await fetchWithTimeout(
      `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-goog-api-key": key,
        },
        body: JSON.stringify({
          contents: [
            {
              role: "user",
              parts: [
                {
                  text: agentPrompt(agent, message),
                },
              ],
            },
          ],
          generationConfig: {
            temperature: 0.35,
            maxOutputTokens: 700,
            thinkingConfig: { thinkingBudget: 0 },
          },
        }),
      },
      signal,
      10000,
    )
    if (!response.ok) return { status: "error", message: `${agent} could not complete the request.` }
    const data = await response.json()
    const answer = data?.candidates?.[0]?.content?.parts?.map((part) => part.text || "").join(" ").trim()
    return {
      status: answer ? "completed" : "error",
      message: cleanAgentResponse(answer || `${agent} could not produce a clear response.`),
      data,
    }
  } catch (error) {
    if (error?.name === "AbortError") throw error
    return { status: "error", message: `${agent} is unavailable right now.` }
  }
}

function agentPrompt(agent, message) {
  const roles = {
    Nova: "You are Nova, CEASER's research intelligence agent. Produce concise research, key findings, recommendations, and mention that live source retrieval may require opening CEASER if sources are needed.",
    Zeus: "You are Zeus, CEASER's business strategy agent. Produce clear strategy, business implications, and next steps.",
    Atlas: "You are Atlas, CEASER's software architecture agent. Produce technical architecture, risks, and implementation steps.",
    Friday: "You are Friday, CEASER's content agent. Produce content strategy, draft ideas, and publishing next steps.",
    Alex: "You are Alex, CEASER's personal learning agent. Produce a practical study or personal plan with next steps.",
    Bolt: "You are Bolt, CEASER's execution agent. Produce an action plan with priorities and deadlines.",
  }
  return `${roles[agent] || "You are CEASER's AI workforce agent."}

Answer the user directly. No internal orchestration logs. No markdown tables. Keep it useful for the desktop overlay.

User request: ${message}`
}

function cleanAgentResponse(value) {
  return String(value || "")
    .replace(/^#+\s*/gm, "")
    .replace(/\*\*/g, "")
    .trim()
}
