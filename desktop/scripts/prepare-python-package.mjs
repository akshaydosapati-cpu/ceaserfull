import { cp, mkdir, rm } from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const desktopDir = path.resolve(scriptDir, "..")
const sourceDir = path.join(desktopDir, "python_companion")
const targetDir = path.join(desktopDir, "build", "python_companion-package")
const excludedNames = new Set([
  "__pycache__", "tests", "chroma_db", "amazon_shopping.db", "language_learning.db",
  "memory.db", "memory.db-shm", "memory.db-wal", "multimodal.db", "multiuser.db",
  "proactive.db", "reminders_local.db", "vault.db", "vision.db", "web_automation.db",
])

await rm(targetDir, { recursive: true, force: true })
await mkdir(path.dirname(targetDir), { recursive: true })
await cp(sourceDir, targetDir, {
  recursive: true,
  filter(source) {
    const name = path.basename(source)
    return !name.startsWith(".") && !excludedNames.has(name) && !name.endsWith(".pyc") && !name.endsWith(".pyo")
  },
})

console.log("Prepared cache-free Python companion package resources.")
