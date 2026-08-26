import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")
const outputPath = path.join(root, ".env.runtime")

function parseEnv(content) {
  return Object.fromEntries(
    content
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line && !line.startsWith("#") && line.includes("="))
      .map((line) => {
        const separator = line.indexOf("=")
        return [line.slice(0, separator).trim(), line.slice(separator + 1).trim()]
      }),
  )
}

const source = [".env.production", ".env.runtime", ".env"]
  .map((name) => path.join(root, name))
  .filter((candidate) => fs.existsSync(candidate))
  .map((candidate) => parseEnv(fs.readFileSync(candidate, "utf8")))
  .reduce((merged, values) => ({ ...merged, ...values }), {})

function value(name, fallback = "") {
  return process.env[name] || source[name] || fallback
}

const requiredPublicConfig = {
  CEASER_APP_URL: value("CEASER_APP_URL"),
  CEASER_API_URL: value("CEASER_API_URL"),
}
const missing = Object.entries(requiredPublicConfig)
  .filter(([, configured]) => !configured)
  .map(([name]) => name)
if (missing.length) {
  throw new Error(`Missing packaged desktop configuration: ${missing.join(", ")}`)
}

// The installer contains provider selection only. Credentials are supplied at
// runtime and are never persisted into this generated file.
const runtimeConfig = {
  CEASER_ENV: "production",
  ...requiredPublicConfig,
  CEASER_STT_PROVIDER: value("CEASER_STT_PROVIDER", "google"),
  CEASER_STT_LANGUAGE: value("CEASER_STT_LANGUAGE", "en"),
  CEASER_STT_GOOGLE_FALLBACK: value("CEASER_STT_GOOGLE_FALLBACK", "true"),
  CEASER_STT_DEEPGRAM_FALLBACK: "false",
  CEASER_DEEPGRAM_STT_MODE: value("CEASER_DEEPGRAM_STT_MODE", "live"),
  CEASER_END_SILENCE_MS: value("CEASER_END_SILENCE_MS", "1500"),
  CEASER_MAX_COMMAND_SECONDS: value("CEASER_MAX_COMMAND_SECONDS", "20"),
  GOOGLE_CLOUD_PROJECT: value("GOOGLE_CLOUD_PROJECT"),
  CEASER_GOOGLE_STT_PRIMARY_LANGUAGE: value("CEASER_GOOGLE_STT_PRIMARY_LANGUAGE", "en-IN"),
  CEASER_GOOGLE_STT_ALTERNATIVE_LANGUAGES: value("CEASER_GOOGLE_STT_ALTERNATIVE_LANGUAGES", "te-IN,hi-IN,ta-IN,kn-IN"),
  CEASER_TRANSLATION_PROVIDER: "",
  CEASER_TRANSLATION_TARGET_LANGUAGE: value("CEASER_TRANSLATION_TARGET_LANGUAGE", "en"),
  CEASER_TTS_PROVIDER: value("CEASER_TTS_PROVIDER", "system"),
  CEASER_TTS_LANGUAGE: value("CEASER_TTS_LANGUAGE", "auto"),
  CEASER_TTS_STREAMING: value("CEASER_TTS_STREAMING", "true"),
  ELEVENLABS_BASE_URL: value("ELEVENLABS_BASE_URL", "https://api.elevenlabs.io"),
  ELEVENLABS_STT_MODEL: value("ELEVENLABS_STT_MODEL", "scribe_v2"),
  ELEVENLABS_TTS_MODEL: value("ELEVENLABS_TTS_MODEL", "eleven_flash_v2_5"),
  ELEVENLABS_TIMEOUT_SECONDS: value("ELEVENLABS_TIMEOUT_SECONDS", "18"),
  CEASER_BROWSER_MAX_STEPS: value("CEASER_BROWSER_MAX_STEPS", "25"),
  CEASER_BROWSER_ACTION_TIMEOUT_SECONDS: value("CEASER_BROWSER_ACTION_TIMEOUT_SECONDS", "15"),
  CEASER_BROWSER_NAVIGATION_TIMEOUT_SECONDS: value("CEASER_BROWSER_NAVIGATION_TIMEOUT_SECONDS", "30"),
}

fs.writeFileSync(
  outputPath,
  `${Object.entries(runtimeConfig).map(([key, configured]) => `${key}=${configured}`).join("\n")}\n`,
  "utf8",
)

console.log("Prepared secret-free packaged desktop runtime configuration.")
