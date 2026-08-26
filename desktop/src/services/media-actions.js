const { shell } = require("electron")
const { spawn } = require("child_process")

const MEDIA_KEYS = {
  playpause: 0xb3,
  next: 0xb0,
  previous: 0xb1,
  stop: 0xb2,
}

const SEND_KEYS = {
  forward: "{RIGHT}",
  rewind: "{LEFT}",
  enter: "{ENTER}",
  tab: "{TAB}",
  space: " ",
}

async function playYouTube(query, options = {}) {
  const rawQuery = String(query || "")
  const newTab = Boolean(options.newTab) || /\b(?:in|on)\s+(?:a\s+)?new\s+tab\b/i.test(rawQuery)
  const cleanQuery = rawQuery
    .replace(/\b(?:in|on)\s+(?:a\s+)?new\s+tab\b/gi, "")
    .replace(/\b(on|in)\s+youtube\b/gi, "")
    .trim()
  if (!cleanQuery) return { status: "error", message: "Tell me what to play on YouTube." }
  const directUrl = youtubeUrl(cleanQuery)
  const video = directUrl ? null : await findFirstYouTubeVideo(cleanQuery)
  const url = directUrl
    ? directUrl
    : video?.id
    ? `https://www.youtube.com/watch?v=${video.id}&autoplay=1`
    : `https://www.youtube.com/results?search_query=${encodeURIComponent(cleanQuery)}`
  const opened = await openMediaUrl(url, newTab)
  if (!opened) return { status: "error", message: `Could not open YouTube for ${cleanQuery}.` }

  if (!directUrl && !video?.id) setTimeout(() => sendKeySequence("{TAB}{TAB}{TAB}{ENTER}"), 2600)
  return {
    status: "completed",
    message: directUrl || video?.id ? `Playing ${video?.title || cleanQuery} on YouTube.` : `I opened YouTube results for ${cleanQuery} and tried to start the first result.`,
    music: {
      title: video?.title || cleanQuery,
      source: "YouTube",
      url,
      direct: Boolean(directUrl || video?.id),
      status: directUrl || video?.id ? "Direct YouTube playback" : "Search fallback",
      query: cleanQuery,
      thumbnail: video?.id ? `https://i.ytimg.com/vi/${video.id}/hqdefault.jpg` : "",
    },
  }
}

async function openMediaUrl(url, newTab = false) {
  if (newTab) return !(await shell.openExternal(url))
  const escapedUrl = escapePowerShell(url)
  const reused = await runPowerShell(`
Add-Type -AssemblyName Microsoft.VisualBasic
Add-Type -AssemblyName System.Windows.Forms
$browser = Get-Process | Where-Object { $_.MainWindowTitle -and $_.ProcessName -match 'chrome|msedge|firefox|brave|opera' } | Select-Object -First 1
if (-not $browser) { exit 2 }
[Microsoft.VisualBasic.Interaction]::AppActivate($browser.Id)
Start-Sleep -Milliseconds 120
[System.Windows.Forms.SendKeys]::SendWait('^l')
Start-Sleep -Milliseconds 50
[System.Windows.Forms.Clipboard]::SetText('${escapedUrl}')
[System.Windows.Forms.SendKeys]::SendWait('^v')
[System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
`)
  if (reused) return true
  return !(await shell.openExternal(url))
}

async function sendMediaKey(key) {
  const normalized = String(key || "").toLowerCase()
  if (MEDIA_KEYS[normalized]) {
    const ok = await sendVirtualKey(MEDIA_KEYS[normalized])
    return {
      status: ok ? "completed" : "error",
      message: ok ? mediaMessage(normalized) : "Could not send media control.",
    }
  }
  if (SEND_KEYS[normalized]) {
    const ok = await sendKeySequence(SEND_KEYS[normalized])
    return {
      status: ok ? "completed" : "error",
      message: ok ? mediaMessage(normalized) : "Could not send playback key.",
    }
  }
  return { status: "error", message: "That media control is not supported yet." }
}

function sendVirtualKey(vk) {
  const script = `
$signature='[DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);'
Add-Type -MemberDefinition $signature -Name Keyboard -Namespace Win32
[Win32.Keyboard]::keybd_event(${vk},0,0,[UIntPtr]::Zero)
[Win32.Keyboard]::keybd_event(${vk},0,2,[UIntPtr]::Zero)
`
  return runPowerShell(script)
}

function sendKeySequence(sequence) {
  const script = `
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.SendKeys]::SendWait('${escapePowerShell(sequence)}')
`
  return runPowerShell(script)
}

async function findFirstYouTubeVideo(query) {
  const url = `https://www.youtube.com/results?search_query=${encodeURIComponent(query)}`
  try {
    const response = await fetch(url, {
      headers: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
      },
    })
    if (!response.ok) return null
    const html = await response.text()
    const ids = [...html.matchAll(/"videoId":"([a-zA-Z0-9_-]{11})"/g)].map((match) => match[1])
    const id = ids.find((value, index) => ids.indexOf(value) === index)
    if (!id) return null
    const titleMatch = html.match(new RegExp(`"videoId":"${id}"[\\s\\S]{0,1200}?"title":\\{"runs":\\[\\{"text":"([^"]+)"`))
    return { id, title: decodeHtml(titleMatch?.[1] || query) }
  } catch {
    return null
  }
}

function runPowerShell(script) {
  return new Promise((resolve) => {
    const child = spawn("powershell.exe", ["-NoProfile", "-Command", script], { windowsHide: true })
    child.on("close", (code) => resolve(code === 0))
    child.on("error", () => resolve(false))
  })
}

function mediaMessage(key) {
  return {
    playpause: "Playback toggled.",
    next: "Skipped to the next track.",
    previous: "Went to the previous track.",
    stop: "Playback stopped.",
    forward: "Moved playback forward.",
    rewind: "Moved playback back.",
    space: "Playback toggled.",
  }[key] || "Media control sent."
}

function decodeHtml(value) {
  return String(value || "")
    .replace(/\\u0026/g, "&")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
}

function youtubeUrl(value) {
  const text = String(value || "").trim()
  if (!/^https?:\/\//i.test(text)) return ""
  if (!/\b(youtube\.com|youtu\.be)\b/i.test(text)) return ""
  return text.includes("autoplay=")
    ? text
    : `${text}${text.includes("?") ? "&" : "?"}autoplay=1`
}

function escapePowerShell(value) {
  return String(value || "").replace(/'/g, "''")
}

module.exports = { playYouTube, sendMediaKey }
