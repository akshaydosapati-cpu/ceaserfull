import { mkdir, rm } from "node:fs/promises"
import path from "node:path"
import { spawnSync } from "node:child_process"
import { fileURLToPath } from "node:url"

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const desktopDir = path.resolve(scriptDir, "..")
const buildDir = path.join(desktopDir, "build")
const distDir = path.join(buildDir, "python-runtime")
const workDir = path.join(buildDir, "pyinstaller-work")
const entry = path.join(desktopDir, "python_companion", "desktop_voice_server.py")
const python = process.env.CEASER_BUILD_PYTHON || process.env.PYTHON || "python"
const excludedModules = [
  "torch", "torchvision", "torchaudio", "transformers", "tokenizers",
  "sentence_transformers", "safetensors", "face_recognition",
  "face_recognition_models", "dlib", "cv2", "onnxruntime", "PyQt5", "PyQt6",
  "pyarrow", "pandas", "scipy", "numba", "llvmlite", "sklearn",
  "matplotlib", "googleapiclient", "chromadb", "posthog", "tensorflow", "keras",
]

await rm(distDir, { recursive: true, force: true })
await rm(workDir, { recursive: true, force: true })
await rm(path.join(buildDir, "ceaser_voice_runtime.spec"), { force: true })
await mkdir(buildDir, { recursive: true })

const args = [
  "-m", "PyInstaller",
  "--noconfirm",
  "--onedir",
  "--name", "ceaser_voice_runtime",
  "--distpath", distDir,
  "--workpath", workDir,
  "--specpath", buildDir,
  "--paths", path.join(desktopDir, "python_companion"),
  "--hidden-import", "requests",
  "--hidden-import", "urllib3",
  "--collect-all", "pvporcupine",
  entry,
]
for (const moduleName of excludedModules) args.splice(args.length - 1, 0, "--exclude-module", moduleName)

const result = spawnSync(python, args, {
  cwd: desktopDir,
  env: { ...process.env, PYTHONUTF8: "1" },
  encoding: "utf8",
  stdio: "inherit",
})

if (result.error) throw result.error
if (result.status !== 0) throw new Error(`Python runtime packaging failed with exit code ${result.status}`)

// SpeechRecognition bundles PocketSphinx's offline acoustic model even though
// CEASER V1 uses Google Cloud/Google Web/Deepgram. Keep the active STT library
// while omitting this unused 37 MB model dataset.
await rm(path.join(distDir, "ceaser_voice_runtime", "_internal", "speech_recognition", "pocketsphinx-data"), {
  recursive: true,
  force: true,
})

const runtimeExecutable = path.join(distDir, "ceaser_voice_runtime", "ceaser_voice_runtime.exe")
const validation = spawnSync(runtimeExecutable, [], {
  cwd: path.dirname(runtimeExecutable),
  env: { ...process.env, PYTHONUTF8: "1", CEASER_PROACTIVE_ENABLED: "false" },
  input: "__quit__\n",
  encoding: "utf8",
  timeout: 120_000,
})
if (validation.error) throw validation.error
const runtimeReady = validation.stdout
  .split(/\r?\n/)
  .some((line) => {
    const payload = line.startsWith("CEASER_JSON:") ? line.slice("CEASER_JSON:".length) : line
    try {
      const event = JSON.parse(payload)
      return event?.id === "ready" && event?.status === "ready"
    } catch {
      return false
    }
  })
if (validation.status !== 0 || !runtimeReady) {
  const detail = (validation.stderr || validation.stdout || "no runtime output").trim().slice(0, 500)
  throw new Error(`Packaged Python runtime failed its startup check: ${detail}`)
}

console.log("Prepared self-contained CEASER Python runtime.")
