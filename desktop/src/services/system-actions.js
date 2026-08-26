const { powerMonitor, shell } = require("electron")
const { spawn } = require("child_process")
const os = require("os")

async function getSystemInfo(type) {
  if (type === "time") return { status: "completed", message: new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) }
  if (type === "date") {
    const now = new Date()
    return {
      status: "completed",
      message: `Today is ${now.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" })}.`,
    }
  }
  if (type === "battery") {
    const battery = await powerMonitor.getSystemIdleState?.(1)
    return { status: "completed", message: `Battery/system power info is available from Windows settings. Current idle state: ${battery || "unknown"}.` }
  }
  if (type === "network") return { status: "completed", message: os.networkInterfaces() ? "Network adapters detected." : "No network adapters detected." }
  if (type === "disk") return runPowerShell("Get-PSDrive -PSProvider FileSystem | Select-Object Name,Free,Used | ConvertTo-Json -Compress", "Disk information ready.")
  return { status: "completed", message: `${os.type()} ${os.release()} · ${os.cpus().length} CPU threads.` }
}

async function openSettings(page) {
  const pages = {
    bluetooth: "ms-settings:bluetooth",
    display: "ms-settings:display",
    sound: "ms-settings:sound",
    wifi: "ms-settings:network-wifi",
  }
  const error = await shell.openExternal(pages[page] || "ms-settings:")
  return error ? { status: "error", message: "Could not open settings." } : { status: "completed", message: "Settings opened." }
}

function lockComputer() {
  const child = spawn("rundll32.exe", ["user32.dll,LockWorkStation"], { windowsHide: true })
  child.unref()
  return { status: "completed", message: "Computer lock requested." }
}

function shutdownComputer() {
  const child = spawn("shutdown.exe", ["/s", "/t", "3"], { windowsHide: true })
  child.unref()
  return { status: "completed", message: "Shutdown requested." }
}

function restartComputer() {
  const child = spawn("shutdown.exe", ["/r", "/t", "3"], { windowsHide: true })
  child.unref()
  return { status: "completed", message: "Restart requested." }
}

function sleepComputer() {
  const child = spawn("rundll32.exe", ["powrprof.dll,SetSuspendState", "0,1,0"], { windowsHide: true })
  child.unref()
  return { status: "completed", message: "Sleep requested." }
}

function mediaKey(key) {
  const virtualKeys = {
    mute: 0xAD,
    volume_down: 0xAE,
    volume_up: 0xAF,
  }
  const code = virtualKeys[key]
  if (!code) return { status: "error", message: "Unsupported volume command." }
  const script = `$code=${code}; Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class K {
  [DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, int dwFlags, int dwExtraInfo);
}
"@; [K]::keybd_event($code,0,0,0); [K]::keybd_event($code,0,2,0)`
  const child = spawn("powershell.exe", ["-NoProfile", "-Command", script], { windowsHide: true })
  child.unref()
  return { status: "completed", message: key === "mute" ? "Volume mute toggled." : key === "volume_up" ? "Volume increased." : "Volume decreased." }
}

function adjustVolume(direction, steps = 3) {
  const key = direction === "down" ? "volume_down" : direction === "mute" ? "mute" : "volume_up"
  for (let i = 0; i < Math.max(1, Number(steps) || 1); i += 1) mediaKey(key)
  return { status: "completed", message: key === "mute" ? "Volume mute toggled." : key === "volume_down" ? "Volume decreased." : "Volume increased." }
}

function setVolume(level) {
  const safeLevel = Math.max(0, Math.min(100, Number(level) || 0))
  const script = `$level=${safeLevel}; try {
  Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class Audio {
  [DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, int dwFlags, int dwExtraInfo);
}
"@
  for($i=0;$i -lt 50;$i++){ [Audio]::keybd_event(0xAE,0,0,0); [Audio]::keybd_event(0xAE,0,2,0) }
  $steps=[Math]::Round($level/2)
  for($i=0;$i -lt $steps;$i++){ [Audio]::keybd_event(0xAF,0,0,0); [Audio]::keybd_event(0xAF,0,2,0) }
  exit 0
} catch { exit 1 }`
  return runPowerShell(script, `Volume set near ${safeLevel}%.`)
}

function runPowerShell(command, success) {
  return new Promise((resolve) => {
    const child = spawn("powershell.exe", ["-NoProfile", "-Command", command], { windowsHide: true })
    let output = ""
    child.stdout.on("data", (chunk) => {
      output += String(chunk)
    })
    child.on("close", (code) => resolve({ status: code === 0 ? "completed" : "error", message: code === 0 ? success : "System command failed.", output: output.slice(0, 1000) }))
    child.on("error", () => resolve({ status: "error", message: "System command failed." }))
  })
}

module.exports = { adjustVolume, getSystemInfo, lockComputer, openSettings, restartComputer, setVolume, shutdownComputer, sleepComputer }
