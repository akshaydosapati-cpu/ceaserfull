const { shell } = require("electron")
const { spawn } = require("child_process")
const fs = require("fs")
const os = require("os")
const path = require("path")

const INDEX_REFRESH_MS = 3 * 60 * 60 * 1000
const MAX_DIRECTORY_APPS = 3500
const CACHE_FILE = path.join(process.env.APPDATA || path.join(os.homedir(), "AppData", "Roaming"), "CEASER", "cache", "installed-apps.json")
const appIndex = {
  apps: [],
  refreshedAt: 0,
  refreshing: null,
}

const commonAliases = {
  "google chrome": ["chrome"],
  chrome: ["google chrome"],
  "visual studio code": ["vs code", "vscode", "code"],
  "vs code": ["visual studio code", "vscode", "code"],
  word: ["microsoft word", "winword"],
  excel: ["microsoft excel"],
  powerpoint: ["microsoft powerpoint", "power point", "ppt"],
  outlook: ["microsoft outlook"],
  edge: ["microsoft edge", "ms edge"],
}

const systemApps = [
  app("Settings", "uri", "ms-settings:", ["windows settings", "system settings", "pc settings"]),
  app("Calculator", "exe", "calc.exe", ["calc"]),
  app("Paint", "exe", "mspaint.exe", ["ms paint"]),
  app("Notepad", "exe", "notepad.exe", ["notes"]),
  app("File Explorer", "exe", "explorer.exe", ["explorer", "files", "windows explorer"]),
  app("Task Manager", "exe", "taskmgr.exe", ["taskmgr"]),
  app("Device Manager", "exe", "devmgmt.msc", ["devices"]),
  app("Control Panel", "exe", "control.exe", ["control"]),
  app("Registry Editor", "exe", "regedit.exe", ["registry", "regedit"]),
  app("Services", "exe", "services.msc", ["windows services"]),
  app("PowerShell", "exe", "powershell.exe", ["power shell", "windows powershell"]),
  app("Command Prompt", "exe", "cmd.exe", ["cmd", "terminal command"]),
  app("Windows Terminal", "exe", "wt.exe", ["terminal", "wt"]),
  app("Snipping Tool", "exe", "snippingtool.exe", ["snip", "screen snip"]),
  app("Photos", "uwp-name", "photos", ["microsoft photos"]),
  app("Camera", "uwp-name", "camera", ["windows camera"]),
]

loadCachedApplicationIndex()
setInterval(() => refreshApplicationIndex("periodic"), INDEX_REFRESH_MS).unref?.()

async function launchApp(requestedApp, options = {}) {
  const requested = cleanRequest(requestedApp)
  if (!requested) return { status: "error", message: "App name is required." }
  if (options.profileName && /^(?:google\s+)?chrome$/i.test(requested)) {
    return launchChromeProfile(options.profileName, Boolean(options.forceNew))
  }
  const match = await findBestApp(requested)
  if (match.status === "ambiguous") {
    return {
      status: "needs_clarification",
      message: `I found multiple apps. Did you mean ${match.matches.map((item) => item.name).join(" or ")}?`,
      matches: match.matches,
    }
  }
  if (!match.app) return { status: "error", message: `I could not find ${requestedApp}. Say "refresh apps" and try again.` }

  if (!options.forceNew) {
    const focused = await focusApp(requested)
    if (focused.status === "completed") {
      return { status: "completed", message: `Switched to ${match.app.name}.`, app: publicApp(match.app), confidence: match.score, focused: true }
    }
  }
  const started = await launchResolvedApp(match.app)
  console.log(`[CEASER AppLauncher] launch ${started ? "success" : "failure"} name="${match.app.name}" confidence=${match.score}`)
  if (started) return { status: "completed", message: `${match.app.name} opened.`, app: publicApp(match.app), confidence: match.score }
  return { status: "error", message: `I found ${match.app.name}, but Windows could not open it.` }
}

function chromeProfiles() {
  const userData = path.join(process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local"), "Google", "Chrome", "User Data")
  const localState = path.join(userData, "Local State")
  try {
    const state = JSON.parse(fs.readFileSync(localState, "utf8"))
    const cache = state?.profile?.info_cache || {}
    return Object.entries(cache).map(([directory, profile]) => ({
      directory,
      name: String(profile?.name || directory),
      email: String(profile?.user_name || ""),
      userData,
    }))
  } catch {
    return []
  }
}

async function launchChromeProfile(requestedProfile, forceNew = false) {
  const query = normalize(requestedProfile)
  const matches = chromeProfiles().filter((profile) => {
    const values = [profile.name, profile.email, profile.directory].map(normalize)
    return values.some((value) => value === query || value.includes(query) || query.includes(value))
  })
  if (!matches.length) {
    const available = chromeProfiles().map((profile) => profile.name)
    return { status: "error", message: available.length ? `I could not find that Chrome profile. Available profiles are ${available.join(", ")}.` : "I could not read Chrome profiles on this computer." }
  }
  if (matches.length > 1) {
    return { status: "needs_clarification", message: `Which Chrome profile did you mean: ${matches.map((profile) => profile.name).join(" or ")}?` }
  }
  const profile = matches[0]
  const candidates = [
    path.join(process.env.ProgramFiles || "C:\\Program Files", "Google", "Chrome", "Application", "chrome.exe"),
    path.join(process.env["ProgramFiles(x86)"] || "C:\\Program Files (x86)", "Google", "Chrome", "Application", "chrome.exe"),
    path.join(process.env.LOCALAPPDATA || "", "Google", "Chrome", "Application", "chrome.exe"),
  ]
  const executable = candidates.find((candidate) => candidate && fs.existsSync(candidate)) || "chrome.exe"
  return new Promise((resolve) => {
    const args = [`--profile-directory=${profile.directory}`]
    if (forceNew) args.push("--new-window")
    const child = spawn(executable, args, { detached: true, windowsHide: true, stdio: "ignore" })
    child.once("spawn", () => { child.unref(); resolve({ status: "completed", message: `Opened the ${profile.name} Chrome profile.`, profile: profile.name }) })
    child.once("error", () => resolve({ status: "error", message: `I found the ${profile.name} profile, but Chrome could not open it.` }))
  })
}

async function refreshApps() {
  await refreshApplicationIndex("manual")
  return {
    status: "completed",
    message: `Application index refreshed. I found ${appIndex.apps.length} apps.`,
    count: appIndex.apps.length,
    refreshed_at: appIndex.refreshedAt,
  }
}

async function closeApp(requestedApp) {
  const running = await findRunningAppMatches(requestedApp)
  if (running.length) {
    const closed = await closeRunningAppMatches(running)
    if (closed) return { status: "completed", message: `${toTitle(cleanRequest(requestedApp))} closed.`, closed_processes: running.map((item) => item.process) }
  }
  const match = await findBestApp(requestedApp)
  const name = executableName(match.app?.target || match.app?.name || requestedApp)
  if (!name) return { status: "error", message: "App name is required." }
  const label = match.app?.name || toTitle(requestedApp)
  const graceful = await taskKill(name, false)
  if (graceful) return { status: "completed", message: `${label} closed.` }
  const forced = await taskKill(name, true)
  if (forced) return { status: "completed", message: `${label} closed.` }
  const windowClose = await closeWindowByTitle(label)
  if (windowClose) return { status: "completed", message: `${label} closed.` }
  return { status: "error", message: `Could not close ${label}. It may not be running or Windows blocked it.` }
}

async function focusApp(requestedApp) {
  const match = await findBestApp(requestedApp)
  const label = match.app?.name || requestedApp
  const target = match.app?.target ? path.basename(String(match.app.target), ".exe") : ""
  const script = `
$ws=New-Object -ComObject WScript.Shell
if($ws.AppActivate('${escapePowerShell(label)}')){ exit 0 }
if('${escapePowerShell(target)}' -and $ws.AppActivate('${escapePowerShell(target)}')){ exit 0 }
exit 1
`
  const child = spawn("powershell.exe", ["-NoProfile", "-Command", script], { windowsHide: true })
  return waitForExit(child, `Focused ${label}.`, `Could not focus ${label}.`)
}

async function isAppRunning(requestedApp) {
  const match = await findBestApp(requestedApp)
  const name = executableName(match.app?.target || match.app?.name || requestedApp)
  if (!name) return { status: "error", message: "App name is required." }
  const child = spawn("tasklist", ["/FI", `IMAGENAME eq ${name}.exe`], { windowsHide: true })
  let output = ""
  child.stdout.on("data", (chunk) => { output += String(chunk) })
  await wait(child)
  const running = output.toLowerCase().includes(`${name}.exe`.toLowerCase())
  return { status: "completed", message: running ? `${match.app?.name || requestedApp} is running.` : `${match.app?.name || requestedApp} is not running.` }
}

async function findBestApp(query) {
  if (!appIndex.apps.length) await refreshApplicationIndex("lazy")
  const normalized = normalize(query)
  const candidates = appIndex.apps
    .map((entry) => ({ app: entry, score: scoreApp(normalized, entry) }))
    .filter((item) => item.score >= 52)
    .sort((a, b) => b.score - a.score)

  const top = candidates[0]
  if (!top) return { app: null, score: 0 }
  const close = candidates.filter((item) => item.score >= top.score - 4 && item.app.name !== top.app.name).slice(0, 4)
  if (close.length && top.score < 92) return { status: "ambiguous", matches: [top, ...close].map((item) => publicApp(item.app)) }
  console.log(`[CEASER AppLauncher] match query="${query}" app="${top.app.name}" confidence=${top.score}`)
  return top
}

async function refreshApplicationIndex(reason = "manual") {
  if (appIndex.refreshing) return appIndex.refreshing
  const started = Date.now()
  appIndex.refreshing = (async () => {
    const discovered = []
    const seen = new Set()
    for (const entry of systemApps) addApp(discovered, seen, entry)
    for (const entry of await discoverShortcuts()) addApp(discovered, seen, entry)
    for (const entry of await discoverRegistryApps()) addApp(discovered, seen, entry)
    for (const entry of await discoverUwpApps()) addApp(discovered, seen, entry)
    for (const entry of await discoverCommonInstallApps()) addApp(discovered, seen, entry)
    appIndex.apps = discovered
    appIndex.refreshedAt = Date.now()
    saveCachedApplicationIndex()
    console.log(`[CEASER AppLauncher] discovered=${discovered.length} reason=${reason} time_ms=${Date.now() - started}`)
  })().finally(() => { appIndex.refreshing = null })
  return appIndex.refreshing
}

function loadCachedApplicationIndex() {
  const discovered = []
  const seen = new Set()
  for (const entry of systemApps) addApp(discovered, seen, entry)
  try {
    const cached = JSON.parse(fs.readFileSync(CACHE_FILE, "utf8"))
    for (const entry of Array.isArray(cached?.apps) ? cached.apps : []) addApp(discovered, seen, entry)
    appIndex.refreshedAt = Number(cached?.refreshedAt || 0)
  } catch {
    // First launch starts with system apps and refreshes the full index later.
  }
  appIndex.apps = discovered
  console.log(`[CEASER AppLauncher] cache_loaded=${discovered.length} age_ms=${appIndex.refreshedAt ? Date.now() - appIndex.refreshedAt : -1}`)
}

function saveCachedApplicationIndex() {
  try {
    fs.mkdirSync(path.dirname(CACHE_FILE), { recursive: true })
    fs.writeFileSync(CACHE_FILE, JSON.stringify({ refreshedAt: appIndex.refreshedAt, apps: appIndex.apps }), "utf8")
  } catch {
    // Cache writes are optional and must never affect application commands.
  }
}

function applicationIndexNeedsRefresh(now = Date.now()) {
  return !appIndex.refreshedAt || now - appIndex.refreshedAt >= INDEX_REFRESH_MS
}

async function findRunningAppMatches(requestedApp) {
  const query = cleanRequest(requestedApp)
  if (!query) return []
  const rows = await powershellJson("Get-Process | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object Id,ProcessName,MainWindowTitle | ConvertTo-Json -Compress")
  const items = Array.isArray(rows) ? rows : rows ? [rows] : []
  const resolved = await findBestApp(query)
  const resolvedProcess = executableName(resolved?.app?.target || "")
  return items.filter((item) => {
    const processName = normalize(item.ProcessName)
    const title = normalize(item.MainWindowTitle)
    return processName === normalize(query).replace(/\s+/g, "") ||
      Boolean(resolvedProcess && processName === normalize(resolvedProcess)) ||
      title.includes(normalize(query))
  }).map((item) => ({ pid: Number(item.Id), process: String(item.ProcessName || ""), title: String(item.MainWindowTitle || "") }))
}

async function closeRunningAppMatches(matches) {
  const pids = [...new Set(matches.map((item) => Number(item.pid)).filter(Number.isFinite))]
  if (!pids.length) return false
  const pidList = pids.join(",")
  const script = `$ids=@(${pidList}); $closed=0; foreach($id in $ids){ $p=Get-Process -Id $id -ErrorAction SilentlyContinue; if($p){ if($p.CloseMainWindow()){ $closed++ } } }; Start-Sleep -Milliseconds 350; foreach($id in $ids){ $p=Get-Process -Id $id -ErrorAction SilentlyContinue; if($p -and $p.ProcessName -notin @('explorer','ApplicationFrameHost')){ Stop-Process -Id $id -Force -ErrorAction SilentlyContinue; $closed++ } }; if($closed -gt 0){ exit 0 }; exit 1`
  const child = spawn("powershell.exe", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], { windowsHide: true })
  return wait(child).then((code) => code === 0)
}

async function discoverShortcuts() {
  const roots = [
    path.join(process.env.ProgramData || "C:\\ProgramData", "Microsoft", "Windows", "Start Menu", "Programs"),
    path.join(os.homedir(), "AppData", "Roaming", "Microsoft", "Windows", "Start Menu", "Programs"),
    path.join(os.homedir(), "Desktop"),
    path.join(process.env.PUBLIC || "C:\\Users\\Public", "Desktop"),
  ]
  const apps = []
  for (const root of roots) {
    for (const file of await walk(root, (name) => name.toLowerCase().endsWith(".lnk"), 9000)) {
      const name = cleanShortcutName(path.basename(file, ".lnk"))
      apps.push(app(name, "shortcut", file, aliasList(name)))
    }
  }
  return apps
}

function discoverRegistryApps() {
  const script = `
$roots=@(
'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',
'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',
'HKLM:\\Software\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',
'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\*',
'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\*'
)
$out=@()
foreach($root in $roots){
  try {
    Get-ItemProperty $root -ErrorAction SilentlyContinue | ForEach-Object {
      $name=$_.DisplayName
      $target=$_.DisplayIcon
      if(-not $target){ $target=$_.InstallLocation }
      if(-not $name){ $name=$_.PSChildName -replace '\\.exe$','' }
      if($name -and $target){ $out += [pscustomobject]@{name=$name; target=$target} }
    }
  } catch {}
}
$out | ConvertTo-Json -Compress
`
  return powershellJson(script).then((rows) => {
    const items = Array.isArray(rows) ? rows : rows ? [rows] : []
    return items.map((row) => {
      const target = normalizeRegistryTarget(row.target)
      return target ? app(row.name, "desktop", target, aliasList(row.name)) : null
    }).filter(Boolean)
  })
}

function discoverUwpApps() {
  const script = `Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress`
  return powershellJson(script).then((rows) => {
    const items = Array.isArray(rows) ? rows : rows ? [rows] : []
    return items.map((row) => app(row.Name, "uwp", row.AppID, aliasList(row.Name))).filter((item) => item.name && item.target)
  })
}

async function discoverCommonInstallApps() {
  const roots = [
    process.env.ProgramFiles || "C:\\Program Files",
    process.env["ProgramFiles(x86)"] || "C:\\Program Files (x86)",
    path.join(process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local"), "Programs"),
  ]
  const apps = []
  for (const root of roots) {
    for (const file of await walk(root, (name) => name.toLowerCase().endsWith(".exe"), MAX_DIRECTORY_APPS, 4)) {
      const base = path.basename(file, ".exe")
      if (isBadExeName(base)) continue
      apps.push(app(toTitle(base), "desktop", file, aliasList(base)))
    }
  }
  return apps
}

async function launchResolvedApp(entry) {
  if (entry.type === "uri") return openExternal(entry.target)
  if (entry.type === "uwp") return startProcess(`shell:AppsFolder\\${entry.target}`)
  if (entry.type === "uwp-name") return launchUwpByName(entry.target)
  if (entry.type === "shortcut") return openPath(entry.target)
  return startProcess(entry.target)
}

function launchUwpByName(name) {
  const query = normalize(name)
  const script = `$app=Get-StartApps | Where-Object { $_.Name.ToLower().Contains('${escapePowerShell(query)}') } | Select-Object -First 1; if($app){ Start-Process "shell:AppsFolder\\$($app.AppID)"; exit 0 }; exit 1`
  const child = spawn("powershell.exe", ["-NoProfile", "-Command", script], { windowsHide: true })
  return wait(child).then((code) => code === 0)
}

async function openPath(filePath) {
  try {
    const error = await shell.openPath(filePath)
    if (!error) return true
  } catch {}
  return startProcess(filePath)
}

function openExternal(uri) {
  return shell.openExternal(uri).then((error) => !error).catch(() => false)
}

function startProcess(target) {
  return new Promise((resolve) => {
    const script = `Start-Process -FilePath '${escapePowerShell(target)}'`
    const child = spawn("powershell.exe", ["-NoProfile", "-Command", script], { windowsHide: true })
    child.on("close", (code) => resolve(code === 0))
    child.on("error", () => resolve(false))
  })
}

function powershellJson(script) {
  return new Promise((resolve) => {
    const child = spawn("powershell.exe", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], { windowsHide: true })
    let output = ""
    child.stdout.on("data", (chunk) => { output += String(chunk) })
    child.on("close", () => {
      try { resolve(JSON.parse(output || "[]")) } catch { resolve([]) }
    })
    child.on("error", () => resolve([]))
  })
}

async function walk(root, filter, limit = 2000, maxDepth = 20) {
  if (!root || !fs.existsSync(root)) return []
  const output = []
  const stack = [{ dir: root, depth: 0 }]
  let scannedDirectories = 0
  while (stack.length && output.length < limit) {
    const { dir, depth } = stack.pop()
    let entries = []
    try { entries = await fs.promises.readdir(dir, { withFileTypes: true }) } catch { continue }
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name)
      if (entry.isDirectory() && depth < maxDepth && !isIgnoredDirectory(entry.name)) stack.push({ dir: fullPath, depth: depth + 1 })
      else if (entry.isFile() && filter(entry.name, fullPath)) output.push(fullPath)
      if (output.length >= limit) break
    }
    scannedDirectories += 1
    if (scannedDirectories % 25 === 0) await new Promise((resolve) => setImmediate(resolve))
  }
  return output
}

function addApp(output, seen, entry) {
  if (!entry?.name || !entry?.target) return
  const key = `${normalize(entry.name)}|${entry.type}|${String(entry.target).toLowerCase()}`
  if (seen.has(key)) return
  seen.add(key)
  output.push({ ...entry, searchable: searchableText(entry) })
}

function app(name, type, target, aliases = []) {
  const cleanName = String(name || "").replace(/\s+/g, " ").trim()
  return { name: cleanName, type, target: String(target || "").trim(), aliases: [...new Set(aliasList(cleanName).concat(aliases).filter(Boolean))] }
}

function scoreApp(query, entry) {
  const terms = [entry.name, ...entry.aliases, entry.target].map(normalize).filter(Boolean)
  let best = 0
  for (const term of terms) {
    if (term === query) best = Math.max(best, 100)
    else if (term.startsWith(query)) best = Math.max(best, 92)
    else if (term.includes(query)) best = Math.max(best, 82)
    else if (query.split(" ").every((part) => term.includes(part))) best = Math.max(best, 74)
    else best = Math.max(best, fuzzyScore(query, term))
  }
  return best
}

function fuzzyScore(query, target) {
  if (!query || !target) return 0
  let qi = 0
  for (let ti = 0; ti < target.length && qi < query.length; ti += 1) {
    if (query[qi] === target[ti]) qi += 1
  }
  const coverage = qi / query.length
  const lengthPenalty = Math.min(query.length / Math.max(target.length, 1), 1)
  return Math.round(coverage * 58 + lengthPenalty * 18)
}

function aliasList(name) {
  const normalized = normalize(name)
  const aliases = [normalized]
  if (commonAliases[normalized]) aliases.push(...commonAliases[normalized])
  if (normalized.startsWith("microsoft ")) aliases.push(normalized.replace(/^microsoft\s+/, ""))
  if (normalized.endsWith(" browser")) aliases.push(normalized.replace(/\s+browser$/, ""))
  if (normalized.includes("visual studio code")) aliases.push("vs code", "vscode", "code")
  return [...new Set(aliases)]
}

function cleanRequest(value) {
  return normalize(value).replace(/\b(open|launch|start|run|close|quit|exit|terminate|kill|please|the|app|application)\b/g, "").replace(/\s+/g, " ").trim()
}

function normalize(value) {
  return String(value || "").toLowerCase().replace(/[_-]+/g, " ").replace(/[^\w\s.+#]/g, "").replace(/\s+/g, " ").trim()
}

function cleanShortcutName(value) {
  return String(value || "").replace(/\s*-\s*shortcut$/i, "").replace(/\s+/g, " ").trim()
}

function normalizeRegistryTarget(value) {
  let target = String(value || "").split(",")[0].replace(/^"|"$/g, "").trim()
  if (!target) return ""
  if (target.endsWith("\\")) return ""
  return target
}

function searchableText(entry) {
  return normalize([entry.name, ...entry.aliases, entry.target].join(" "))
}

function publicApp(entry) {
  return { name: entry.name, type: entry.type, target: entry.type === "desktop" ? entry.target : undefined }
}

function executableName(value) {
  const base = path.basename(String(value || ""), ".exe")
  return normalize(base).replace(/\s+/g, "")
}

function isIgnoredDirectory(name) {
  return /^(node_modules|resources|locales|swiftshader|debug|cache|logs)$/i.test(name)
}

function isBadExeName(name) {
  return /^(unins|uninstall|setup|update|crash|helper|notification|elevate|install|maintenancetool)/i.test(name)
}

function toTitle(value) {
  return String(value || "").replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function escapePowerShell(value) {
  return String(value || "").replace(/'/g, "''")
}

function wait(child) {
  return new Promise((resolve) => {
    child.on("close", resolve)
    child.on("error", () => resolve(1))
  })
}

function waitForExit(child, success, failure) {
  return new Promise((resolve) => {
    child.on("close", (code) => resolve({ status: code === 0 ? "completed" : "error", message: code === 0 ? success : failure }))
    child.on("error", () => resolve({ status: "error", message: failure }))
  })
}

function taskKill(name, force) {
  return new Promise((resolve) => {
    const args = ["/IM", `${name}.exe`, "/T"]
    if (force) args.push("/F")
    const child = spawn("taskkill", args, { shell: false, windowsHide: true })
    child.on("close", (code) => resolve(code === 0))
    child.on("error", () => resolve(false))
  })
}

function closeWindowByTitle(title) {
  return new Promise((resolve) => {
    const script = `
$ws=New-Object -ComObject WScript.Shell
if($ws.AppActivate('${escapePowerShell(title)}')){
  Start-Sleep -Milliseconds 120
  Add-Type -AssemblyName System.Windows.Forms
  [System.Windows.Forms.SendKeys]::SendWait('%{F4}')
  exit 0
}
exit 1
`
    const child = spawn("powershell.exe", ["-NoProfile", "-Command", script], { windowsHide: true })
    child.on("close", (code) => resolve(code === 0))
    child.on("error", () => resolve(false))
  })
}

module.exports = { closeApp, focusApp, isAppRunning, launchApp, refreshApps, refreshApplicationIndex, applicationIndexNeedsRefresh }
