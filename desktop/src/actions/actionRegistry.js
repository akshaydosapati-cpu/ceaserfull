const { INTENT_TYPES, RISK } = require("./actionSchemas")

const dangerousTerms = [
  "delete",
  "remove file",
  "remove folder",
  "format",
  "factory reset",
  "uninstall",
  "registry",
  "payment",
  "buy ",
  "send email",
]

const dangerousPatterns = dangerousTerms.map((term) => {
  const escaped = term.trim().replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
  return new RegExp(`\\b${escaped}\\b`, "i")
})

const folders = {
  downloads: ["downloads", "download folder"],
  documents: ["documents", "document folder"],
  desktop: ["desktop"],
  pictures: ["pictures", "photos folder"],
  videos: ["videos"],
  music: ["music"],
}

const appAliases = {
  chrome: ["chrome", "google chrome"],
  edge: ["edge", "microsoft edge"],
  firefox: ["firefox", "mozilla firefox"],
  brave: ["brave", "brave browser"],
  vscode: ["vs code", "vscode", "visual studio code", "code"],
  notepad: ["notepad"],
  calculator: ["calculator", "calc"],
  explorer: ["file explorer", "explorer"],
  word: ["word", "microsoft word"],
  excel: ["excel", "microsoft excel"],
  powerpoint: ["powerpoint", "power point", "microsoft powerpoint"],
  outlook: ["outlook"],
  teams: ["teams", "microsoft teams"],
  zoom: ["zoom"],
  spotify: ["spotify"],
  discord: ["discord"],
  whatsapp: ["whatsapp", "whats app"],
  telegram: ["telegram"],
  photos: ["photos", "microsoft photos"],
  paint: ["paint", "mspaint"],
  settings: ["settings", "windows settings"],
  taskmgr: ["task manager", "taskmgr"],
  terminal: ["terminal", "windows terminal"],
  powershell: ["powershell", "power shell"],
}

const websiteAliases = {
  google: "https://www.google.com",
  youtube: "https://www.youtube.com",
  github: "https://github.com",
  linkedin: "https://www.linkedin.com",
  wikipedia: "https://www.wikipedia.org",
  gmail: "https://mail.google.com",
  drive: "https://drive.google.com",
  calendar: "https://calendar.google.com",
  chatgpt: "https://chatgpt.com",
  gemini: "https://gemini.google.com",
  supabase: "https://supabase.com/dashboard",
  vercel: "https://vercel.com/dashboard",
  spotify: "https://open.spotify.com",
}

const ceaserRoutes = {
  app: "/",
  chat: "/",
  agents: "/?view=agents",
  files: "/?view=files",
  memory: "/?view=memory",
  projects: "/?view=projects",
  settings: "/?view=settings",
  voice: "/?view=voice",
}

function blockedIntent(command) {
  return {
    intent: INTENT_TYPES.BLOCKED,
    action: "blocked",
    parameters: { command },
    requires_confirmation: false,
    required_permission: null,
    risk_level: RISK.BLOCKED,
    overlay_mode: "expanded",
    overlay_state: "error",
    active_agent: "CEASER",
    progress_steps: [{ label: "Blocked by CEASER safety rules", status: "done" }],
    result_preview: {
      title: "Action blocked",
      summary: "CEASER does not perform destructive, admin, payment, or unsafe automation actions in V1.",
    },
  }
}

function isDangerousCommand(command) {
  return dangerousPatterns.some((pattern) => pattern.test(command))
}

function exposePatternCount() {
  return (
    Object.keys(appAliases).length * 8 +
    Object.keys(folders).length * 10 +
    Object.keys(websiteAliases).length * 10 +
    Object.keys(ceaserRoutes).length * 6 +
    14 * 12 +
    6 * 24
  )
}

module.exports = {
  appAliases,
  blockedIntent,
  ceaserRoutes,
  dangerousTerms,
  exposePatternCount,
  folders,
  isDangerousCommand,
  websiteAliases,
}
