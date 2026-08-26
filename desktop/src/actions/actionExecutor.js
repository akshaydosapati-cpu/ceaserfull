const { shell } = require("electron")
const { launchApp, closeApp, focusApp, isAppRunning, refreshApps } = require("../services/app-launcher")
const { clearClipboard, copyTextToClipboard, readClipboard } = require("../services/clipboard")
const { copyPath, createFolder, findFile, getFileDetails, openFile, openFolder, showInExplorer } = require("../services/file-actions")
const { takeScreenshot } = require("../services/screenshot")
const { analyzeScreen, readScreenText, screenInfo } = require("../services/vision-actions")
const { BehaviorMemory } = require("../services/behavior-memory")
const { adjustVolume, getSystemInfo, lockComputer, openSettings, restartComputer, setVolume, shutdownComputer, sleepComputer } = require("../services/system-actions")
const { SessionMemory } = require("../services/session-memory")
const { getActiveWindow, listOpenWindows, windowAction } = require("../services/window-context")
const { playYouTube, sendMediaKey } = require("../services/media-actions")
const { summarizeActivePdf } = require("../services/active-document")
const { getNews, getWeather } = require("../services/live-actions")
const { getEnv } = require("../services/env")

const sessionMemory = new SessionMemory()
const behaviorMemory = new BehaviorMemory()
const API_URL = getEnv("CEASER_API_URL", "https://ceaser-backend-production-ur04.onrender.com")

async function executeAction(intent) {
  const action = intent.action
  const parameters = intent.parameters || {}
  let result

  if (action === "open_app") result = await launchApp(parameters.app_name || parameters.app, { forceNew: Boolean(parameters.force_new), profileName: parameters.profile_name })
  else if (action === "refresh_apps") result = await refreshApps()
  else if (action === "close_app") result = await closeApp(parameters.app_name || parameters.app)
  else if (action === "restart_app") {
    await closeApp(parameters.app_name || parameters.app)
    result = await launchApp(parameters.app_name || parameters.app)
  }
  else if (action === "focus_app" || action === "switch_app") result = await focusApp(parameters.app_name || parameters.app)
  else if (action === "check_app_running") result = await isAppRunning(parameters.app_name || parameters.app)

  else if (action === "open_folder") result = await openFolder(parameters.folder)
  else if (action === "create_folder") result = createFolder(parameters.base, parameters.name)
  else if (action === "copy_folder_path") result = copyPath(parameters.folder)
  else if (action === "show_in_explorer") result = showInExplorer(parameters.path)

  else if (action === "search_file") result = findFile(parameters.query)
  else if (action === "open_file") result = await openFile(parameters.query)
  else if (action === "copy_file_path") result = copyPath(parameters.path)
  else if (action === "get_file_details") result = getFileDetails(parameters.query)

  else if (action === "read_clipboard") result = readClipboard()
  else if (action === "copy_text_to_clipboard") result = copyTextToClipboard(parameters.text)
  else if (action === "clear_clipboard") result = clearClipboard()

  else if (action === "take_screenshot") result = await takeScreenshot()
  else if (action === "read_screen_text") result = await readScreenText()
  else if (action === "analyze_screen") result = await analyzeScreen()
  else if (action === "screen_info") result = screenInfo()

  else if (action === "open_url") result = await openUrl(parameters.url)
  else if (action === "play_youtube") result = await playYouTube(parameters.url || parameters.query, { newTab: Boolean(parameters.new_tab) })
  else if (action === "media_key") result = await sendMediaKey(parameters.key)
  else if (action === "now_playing") result = { status: "completed", message: "Playback controls are ready. Use play, pause, next, previous, rewind, or forward." }
  else if (action === "summarize_active_pdf") result = await summarizeActivePdf()
  else if (action === "web_search") result = await openUrl(searchUrl(parameters.provider, parameters.query, parameters.play))
  else if (action === "get_weather") result = await getWeather(parameters.location)
  else if (action === "get_news") result = await getNews(parameters.query)
  else if (action === "get_calendar_events") result = await getCalendarEvents(parameters.range)
  else if (action === "set_timer") result = setTimerResult(parameters.amount, parameters.unit)
  else if (action === "stock_price") result = stockPriceResult(parameters.query)
  else if (action === "get_tasks") result = taskOverviewResult()
  else if (action === "open_ceaser") result = await openUrl(`${consoleAppUrl()}${parameters.route || ""}`)

  else if (action === "system_info") result = await getSystemInfo(parameters.type)
  else if (action === "open_settings") result = await openSettings(parameters.page)
  else if (action === "lock_computer") result = lockComputer()
  else if (action === "shutdown_computer") result = shutdownComputer()
  else if (action === "restart_computer") result = restartComputer()
  else if (action === "sleep_computer") result = sleepComputer()
  else if (action === "adjust_volume") result = adjustVolume(parameters.direction, parameters.steps)
  else if (action === "set_volume") result = await setVolume(parameters.level)

  else if (action === "get_active_window") result = await activeWindowResult()
  else if (action === "list_open_windows") result = await openWindowsResult()
  else if (action === "session_summary") result = sessionSummaryResult()
  else if (action === "recent_activity") result = recentActivityResult()
  else if (action === "behavior_summary") result = behaviorSummaryResult()
  else if (action === "daily_brief") result = dailyBriefResult()
  else if (action === "open_morning_workspace") result = await openMorningWorkspace()
  else if (["minimize_window", "maximize_window", "restore_window", "focus_window", "close_window"].includes(action)) {
    result = await windowAction(action.replace("_window", ""), parameters.target)
  }

  else if (action === "blocked") result = { status: "error", message: intent.result_preview?.summary || "Action blocked." }
  else result = { status: "routed", message: "This request belongs to the CEASER agent pipeline." }

  recordActivity(intent, result)
  return result
}

async function openMorningWorkspace() {
  const app = behaviorMemory.profile().preferred_morning_app
  if (!app) return { status: "error", message: "I have not learned a morning workspace yet." }
  const result = await launchApp(app)
  return { ...result, message: result.status === "completed" ? `Opened your morning workspace: ${app}.` : result.message }
}

async function openUrl(url) {
  const error = await shell.openExternal(url)
  if (error) return { status: "error", message: `Could not open ${url}.` }
  return { status: "completed", message: `Opened ${url}.` }
}

function consoleAppUrl() {
  const configured = String(getEnv("CEASER_APP_URL", "")).trim().replace(/\/$/, "")
  if (configured && !/app\.ceaser\.ai/i.test(configured)) return configured
  return "https://heyceaser.in/console"
}

function setTimerResult(amount = 25, unit = "minutes") {
  const safeAmount = Number.isFinite(Number(amount)) ? Number(amount) : 25
  return {
    status: "completed",
    message: `Timer set for ${safeAmount} ${unit}.`,
    timer: { amount: safeAmount, unit },
  }
}

function stockPriceResult(query) {
  return {
    status: "completed",
    message: "I prepared the market request. Live market quotes are handled from the CEASER web console.",
    stock: { query },
  }
}

function taskOverviewResult() {
  return {
    status: "completed",
    message: "Task overview is ready. Open the CEASER web console to review synced tasks.",
    tasks: [],
  }
}

async function getCalendarEvents(range = "upcoming") {
  const token = getEnv("CEASER_ACCESS_TOKEN")
  if (!token || !global.fetch) {
    return { status: "error", message: "The desktop companion is not linked to your CEASER session yet. Use Calendar from the CEASER app, or add CEASER_ACCESS_TOKEN to backend .env for desktop testing." }
  }
  try {
    const response = await fetch(`${API_URL}/integrations/google-calendar/metadata`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok) return { status: "error", message: "I could not read Google Calendar. Check that Calendar is connected in CEASER Integrations." }
    const metadata = await response.json()
    const items = Array.isArray(metadata.items) ? metadata.items : []
    const filtered = filterCalendarItems(items, range)
    const label = range === "tomorrow" ? "tomorrow" : range === "today" ? "today" : "upcoming"
    if (!filtered.length) return { status: "completed", message: `No calendar events found for ${label}.`, events: [], range }
    return {
      status: "completed",
      message: filtered.map((event) => `${formatEventTime(event.start)} - ${event.title}`).join("\n"),
      events: filtered,
      range,
    }
  } catch (_error) {
    return { status: "error", message: "Calendar service is unavailable right now." }
  }
}

function filterCalendarItems(items, range) {
  if (range === "upcoming") return items.slice(0, 6)
  const now = new Date()
  const target = new Date(now)
  if (range === "tomorrow") target.setDate(target.getDate() + 1)
  return items.filter((item) => {
    const start = new Date(item.start)
    return start.getFullYear() === target.getFullYear()
      && start.getMonth() === target.getMonth()
      && start.getDate() === target.getDate()
  }).slice(0, 6)
}

function formatEventTime(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "All day"
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
}

function searchUrl(provider = "google", query = "", play = false) {
  const encoded = encodeURIComponent(query)
  const map = {
    google: `https://www.google.com/search?q=${encoded}`,
    youtube: `https://www.youtube.com/results?search_query=${encoded}`,
    github: `https://github.com/search?q=${encoded}`,
    linkedin: `https://www.linkedin.com/search/results/all/?keywords=${encoded}`,
    wikipedia: `https://en.wikipedia.org/wiki/Special:Search?search=${encoded}`,
    spotify: `https://open.spotify.com/search/${encoded}`,
  }
  if (play && provider === "youtube") return map.youtube
  return map[provider] || map.google
}

async function activeWindowResult() {
  const active = await getActiveWindow()
  return { status: "completed", message: `Current app: ${active.process || "unknown"}. Window: ${active.title || "Untitled"}.`, context: active }
}

async function openWindowsResult() {
  const windows = await listOpenWindows()
  const names = windows.slice(0, 8).map((window) => `${window.process}: ${window.title}`).join("\n")
  return { status: "completed", message: names || "No open windows found.", windows }
}

function sessionSummaryResult() {
  const summary = sessionMemory.summary()
  const behavior = behaviorMemory.profile()
  const suggestion = behavior.suggestions[0] ? ` Suggestion: ${behavior.suggestions[0]}` : ""
  return { status: "completed", message: `${summary.message}${suggestion}`, session: summary, behavior }
}

function recentActivityResult() {
  const events = sessionMemory.recent(8)
  return {
    status: "completed",
    message: events.length ? events.map((event) => `${new Date(event.at).toLocaleTimeString()} - ${event.label || event.action}`).join("\n") : "No recent desktop activity yet.",
    events,
  }
}

function behaviorSummaryResult() {
  return { status: "completed", message: behaviorMemory.summary(), behavior: behaviorMemory.profile() }
}

function dailyBriefResult() {
  const session = sessionMemory.summary()
  const behavior = behaviorMemory.profile()
  const suggestions = behavior.suggestions.length ? behavior.suggestions.join(" ") : "No proactive suggestions yet."
  const topics = behavior.interested_topics.length ? behavior.interested_topics.map((item) => item.name).join(", ") : "none learned yet"
  return {
    status: "completed",
    message: `Today: ${session.message} Your current interest topics are ${topics}. ${suggestions}`,
    session,
    behavior,
  }
}

function recordActivity(intent, result) {
  if (!result || result.status !== "completed") return
  sessionMemory.add({
    action: intent.action,
    label: result.message,
    parameters: sanitizeParameters(intent.parameters || {}),
    path: result.path,
    app: intent.parameters?.app_name || intent.parameters?.app,
  })
  behaviorMemory.observe(intent, result)
}

function sanitizeParameters(parameters) {
  const copy = { ...parameters }
  if (copy.text && copy.text.length > 80) copy.text = `${copy.text.slice(0, 80)}...`
  return copy
}

module.exports = { executeAction }
