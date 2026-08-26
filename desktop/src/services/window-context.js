const { spawn } = require("child_process")

async function getActiveWindow() {
  const script = `
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class WinApi {
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
}
"@
$hwnd = [WinApi]::GetForegroundWindow()
$buffer = New-Object System.Text.StringBuilder 512
[void][WinApi]::GetWindowText($hwnd, $buffer, $buffer.Capacity)
$pidValue = 0
[void][WinApi]::GetWindowThreadProcessId($hwnd, [ref]$pidValue)
$process = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
[PSCustomObject]@{ title = $buffer.ToString(); process = $process.ProcessName; pid = $pidValue } | ConvertTo-Json -Compress
`
  const result = await runPowerShell(script)
  if (!result.ok) return { title: "Unknown", process: "unknown", pid: null }
  try {
    return JSON.parse(result.output)
  } catch (_error) {
    return { title: "Unknown", process: "unknown", pid: null }
  }
}

async function listOpenWindows() {
  const script = `
Get-Process | Where-Object {$_.MainWindowTitle} | Select-Object ProcessName,MainWindowTitle,Id | ConvertTo-Json -Compress
`
  const result = await runPowerShell(script)
  if (!result.ok) return []
  try {
    const parsed = JSON.parse(result.output)
    return (Array.isArray(parsed) ? parsed : [parsed]).map((item) => ({
      process: item.ProcessName,
      title: item.MainWindowTitle,
      pid: item.Id,
    }))
  } catch (_error) {
    return []
  }
}

async function windowAction(action, target) {
  const showWindow = { minimize: 6, maximize: 3, restore: 9 }[action]
  if (!showWindow && action !== "focus" && action !== "close") return { status: "error", message: "Window action is not supported." }
  const script = target
    ? `
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WinApi {
  [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
}
"@
$query='${escapePowerShell(target || "")}'
$processes = Get-Process | Where-Object {$_.MainWindowHandle -ne 0 -and ($query -eq '' -or $_.ProcessName -like "*$query*" -or $_.MainWindowTitle -like "*$query*")} | Select-Object -First 1
if ($processes) {
  ${windowActionScript(action, "$processes.MainWindowHandle", showWindow)}
  "ok"
} else { "missing" }
`
    : `
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WinApi {
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
}
"@
$hwnd = [WinApi]::GetForegroundWindow()
if ($hwnd -ne [IntPtr]::Zero) {
  ${windowActionScript(action, "$hwnd", showWindow)}
  "ok"
} else { "missing" }
`
  const result = await runPowerShell(script)
  return result.output.includes("ok")
    ? { status: "completed", message: `${capitalize(action)} window request completed.` }
    : { status: "error", message: "Could not find a matching window." }
}

function windowActionScript(action, handleExpression, showWindow) {
  if (action === "focus") return `[void][WinApi]::SetForegroundWindow(${handleExpression})`
  if (action === "close") return `[void][WinApi]::PostMessage(${handleExpression}, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero)`
  return `[void][WinApi]::ShowWindowAsync(${handleExpression}, ${showWindow})`
}

function runPowerShell(command) {
  return new Promise((resolve) => {
    const child = spawn("powershell.exe", ["-NoProfile", "-Command", command], { windowsHide: true })
    let settled = false
    const finish = (value) => {
      if (settled) return
      settled = true
      clearTimeout(timeout)
      resolve(value)
    }
    const timeout = setTimeout(() => {
      child.kill()
      finish({ ok: false, output: "", error: "PowerShell command timed out." })
    }, 2500)
    let output = ""
    let error = ""
    child.stdout.on("data", (chunk) => {
      output += String(chunk)
    })
    child.stderr.on("data", (chunk) => {
      error += String(chunk)
    })
    child.on("close", (code) => {
      finish({ ok: code === 0, output: output.trim(), error })
    })
    child.on("error", (err) => {
      finish({ ok: false, output: "", error: String(err) })
    })
  })
}

function escapePowerShell(value) {
  return String(value || "").replace(/'/g, "''")
}

function capitalize(value) {
  return String(value || "").replace(/^\w/, (letter) => letter.toUpperCase())
}

module.exports = { getActiveWindow, listOpenWindows, windowAction }
