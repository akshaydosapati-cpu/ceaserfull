const fs = require("node:fs")
const path = require("node:path")

function resolveAppUrl(options = {}) {
  const getEnv = options.getEnv || require("../services/env").getEnv
  const fileExists = options.fileExists || ((candidate) => fs.existsSync(candidate))

  const configuredUrl = String(getEnv("CEASER_APP_URL", "")).trim()
  const candidatePaths = [
    path.join(process.resourcesPath || "", "frontend", "out", "index.html"),
    path.join(process.resourcesPath || "", "app", "index.html"),
    path.join(__dirname, "..", "..", "..", "frontend", "out", "index.html"),
    path.join(__dirname, "..", "..", "..", "frontend", "build", "index.html"),
    path.join(__dirname, "..", "..", "..", "frontend", "public", "index.html"),
  ]

  const localApp = candidatePaths.find((candidate) => fileExists(candidate))
  const isLocalhost = /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?/i.test(configuredUrl)

  if (configuredUrl && !/app\.ceaser\.ai/i.test(configuredUrl)) return configuredUrl
  if (process.env.NODE_ENV === "development" && localApp) return "ceaser-app://bundle/"

  return process.env.NODE_ENV === "development" ? "http://localhost:3000" : "https://heyceaser.in/console"
}

module.exports = { resolveAppUrl }
