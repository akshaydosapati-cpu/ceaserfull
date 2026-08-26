import { Buffer } from "node:buffer"
import { createRequire } from "node:module"

const require = createRequire(import.meta.url)
const { getEnv, envCandidates } = require("../src/services/env")

const key = getEnv("DEEPGRAM_API_KEY")
const model = getEnv("DEEPGRAM_MODEL", "nova-2")
const language = getEnv("DEEPGRAM_LANGUAGE", "en")

console.log("[CEASER] env candidates:")
for (const item of envCandidates()) console.log(`- ${item}`)
console.log(`[CEASER] Deepgram key present: ${Boolean(key)} length=${key.length}`)
console.log(`[CEASER] Deepgram model=${model} language=${language}`)

if (!key) process.exit(1)

const wav = createSilentWav()
const url = new URL("https://api.deepgram.com/v1/listen")
url.searchParams.set("model", model)
url.searchParams.set("smart_format", "true")
url.searchParams.set("language", language)
url.searchParams.set("punctuate", "true")

const started = Date.now()
const response = await fetch(url, {
  method: "POST",
  headers: {
    Authorization: `Token ${key}`,
    "Content-Type": "audio/wav",
  },
  body: wav,
})
const text = await response.text()
console.log(`[CEASER] Deepgram STT HTTP ${response.status} ${response.statusText} in ${Date.now() - started}ms`)
console.log(text.slice(0, 1000))

function createSilentWav() {
  const sampleRate = 16000
  const seconds = 1
  const dataSize = sampleRate * seconds * 2
  const buffer = Buffer.alloc(44 + dataSize)
  buffer.write("RIFF", 0)
  buffer.writeUInt32LE(36 + dataSize, 4)
  buffer.write("WAVE", 8)
  buffer.write("fmt ", 12)
  buffer.writeUInt32LE(16, 16)
  buffer.writeUInt16LE(1, 20)
  buffer.writeUInt16LE(1, 22)
  buffer.writeUInt32LE(sampleRate, 24)
  buffer.writeUInt32LE(sampleRate * 2, 28)
  buffer.writeUInt16LE(2, 32)
  buffer.writeUInt16LE(16, 34)
  buffer.write("data", 36)
  buffer.writeUInt32LE(dataSize, 40)
  return buffer
}
