const fs = require("fs")
const os = require("os")
const path = require("path")

function desktopRoot() {
  return path.join(__dirname, "..", "..")
}

function envCandidates() {
  const appPath = process.resourcesPath || process.cwd()
  return [
    path.join(process.cwd(), ".env.runtime"),
    path.join(desktopRoot(), ".env.runtime"),
    path.join(appPath, ".env.runtime"),
    path.join(appPath, ".env"),
    path.join(appPath, "../.env"),
    path.join(process.cwd(), ".env"),
    path.join(desktopRoot(), ".env"),
    path.join(desktopRoot(), "..", "backend", ".env"),
    path.join(os.homedir(), "AppData", "Roaming", "CEASER", ".env"),
  ].filter(Boolean)
}

function readEnvValue(name) {
  if (process.env[name]) return process.env[name]
  for (const file of envCandidates()) {
    if (!file || !fs.existsSync(file)) continue
    try {
      const lines = fs.readFileSync(file, "utf8").split(/\r?\n/)
      const line = lines.find((item) => item.trim().startsWith(`${name}=`))
      if (line) {
        const value = line.slice(name.length + 1).trim().replace(/^["']|["']$/g, "")
        return value
      }
    } catch (err) {
      console.warn(`Failed to read env file: ${file}`, err.message)
    }
  }
  return ""
}

function getEnv(name, fallback = "") {
  const value = readEnvValue(name)
  if (value) return value
  if (process.env[name]) return process.env[name]
  return fallback
}

module.exports = { getEnv, readEnvValue, envCandidates }
