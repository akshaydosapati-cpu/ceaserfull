import { existsSync, readFileSync } from "node:fs"
import { spawnSync } from "node:child_process"

const required = [
  "src/main/main.js",
  "src/main/preload.js",
  "src/renderer/index.html",
  "src/renderer/styles.css",
  "src/renderer/app.js",
  "src/controllers/command-router.js",
  "src/services/app-launcher.js",
  "src/services/file-actions.js",
  "src/services/permissions.js",
  "src/services/screenshot.js",
  "src/services/clipboard.js",
  "src/services/system-actions.js",
  "src/services/session-memory.js",
  "src/services/window-context.js",
  "src/services/context-service.js",
  "src/services/device-gateway-client.js",
  "src/services/local-development-runtime.js",
  "src/services/browser-automation-runtime.js",
  "src/services/file-context-resolver.js",
  "src/actions/actionRegistry.js",
  "src/actions/actionRouter.js",
  "src/actions/actionPermissions.js",
  "src/actions/actionConfirmations.js",
  "src/actions/actionExecutor.js",
  "src/actions/actionSchemas.js",
  "scripts/start-electron.mjs",
  "python_companion/desktop_voice_server.py",
  "python_companion/Hey-Ceaser_en_windows_v3_0_0.ppn",
  "python_companion/voice/metrics.py",
  "python_companion/voice/diagnostics.py",
]

const missing = required.filter((file) => !existsSync(new URL(`../${file}`, import.meta.url)))
if (missing.length) {
  console.error(`Missing desktop files:\n${missing.join("\n")}`)
  process.exit(1)
}
const secretLikeFiles = [".env", ".env.runtime"].filter((file) => existsSync(new URL(`../${file}`, import.meta.url)))
if (secretLikeFiles.includes(".env")) {
  console.error("Desktop package must not include development .env. Use .env.runtime only.")
  process.exit(1)
}
const mainSource = readFileSync(new URL("../src/main/main.js", import.meta.url), "utf8")
for (const needle of ["setAsDefaultProtocolClient(\"ceaser\"", "safeStorage.encryptString", "/auth/desktop/exchange", "/auth/desktop/refresh", "/desktop/devices", "ensureDeviceGateway"]) {
  if (!mainSource.includes(needle)) {
    console.error(`Desktop Stage 18 packaging check failed: missing ${needle}`)
    process.exit(1)
  }
}
const pythonCheck = spawnSync("python", ["-c", "import aifc, speech_recognition; print('standard-aifc-compatible')"], {
  encoding: "utf8",
  windowsHide: true,
})
if (pythonCheck.status !== 0) {
  const pyCheck = spawnSync("py", ["-3", "-c", "import aifc, speech_recognition; print('standard-aifc-compatible')"], {
    encoding: "utf8",
    windowsHide: true,
  })
  if (pyCheck.status !== 0) {
    console.warn("CEASER warning: Python speech_recognition standard-aifc compatibility could not be verified on this machine.")
  }
}
console.log("CEASER desktop companion validation passed.")
