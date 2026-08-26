import { spawn, spawnSync } from "node:child_process"
import electronPath from "electron"

const env = { ...process.env }
delete env.ELECTRON_RUN_AS_NODE
env.NODE_ENV = "development"
env.CEASER_DEV_USER_DATA = "true"
env.CEASER_VOICE_HOTKEY ||= "CommandOrControl+Shift+Space"

console.log(`[CEASER DEV] Requested voice hotkey: ${env.CEASER_VOICE_HOTKEY}`)

if (process.platform === "win32") {
  const stopped = spawnSync("taskkill", ["/F", "/T", "/IM", "CEASER.exe"], {
    windowsHide: true,
    stdio: "ignore",
  })
  if (stopped.status === 0) console.log("[CEASER DEV] Closed installed CEASER instance to release the voice hotkey")
}

const child = spawn(electronPath, ["."], {
  cwd: new URL("..", import.meta.url),
  env,
  stdio: "inherit",
  windowsHide: false,
})

child.on("exit", (code, signal) => {
  if (signal) process.kill(process.pid, signal)
  process.exit(code ?? 0)
})
