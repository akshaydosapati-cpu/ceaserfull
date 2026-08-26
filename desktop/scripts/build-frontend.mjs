import { spawnSync } from "node:child_process"
import path from "node:path"
import { fileURLToPath } from "node:url"

const desktopRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")
const frontendRoot = path.resolve(desktopRoot, "..", "frontend")
const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm"

const result = spawnSync(npmCommand, ["run", "build"], {
  cwd: frontendRoot,
  env: {
    ...process.env,
    NEXT_PUBLIC_API_URL: "https://ceaser-backend-production-ur04.onrender.com",
  },
  shell: process.platform === "win32",
  stdio: "inherit",
})

if (result.error) {
  console.error(result.error.message)
}
process.exit(result.status ?? 1)
