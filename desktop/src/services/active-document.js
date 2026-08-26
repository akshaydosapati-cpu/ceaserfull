const fs = require("fs")
const path = require("path")
const { getActiveWindow } = require("./window-context")
const { getEnv } = require("./env")
const { findRecentFiles } = require("./file-actions")

async function summarizeActivePdf() {
  const activePdf = await findActivePdf()
  if (!activePdf) {
    return {
      status: "error",
      message: "I could not identify the PDF you are viewing. Open the PDF file directly or upload it to CEASER Files.",
    }
  }

  const uploaded = await uploadAndSummarize(activePdf.path)
  if (uploaded.status === "completed") return uploaded

  return {
    status: "completed",
    message: `I found the active PDF: ${activePdf.name}. Upload it to CEASER Files to summarize it with the document engine.`,
    path: activePdf.path,
  }
}

async function findActivePdf() {
  const active = await getActiveWindow()
  const title = String(active.title || "")
  const directName = title.match(/([^\\/:*?"<>|\r\n]+\.pdf)\b/i)?.[1]
  const recentPdfs = findRecentFiles({ type: "pdf", limit: 60, maxPerRoot: 2500 })
  if (directName) {
    const exact = recentPdfs.find((file) => normalize(file.name) === normalize(directName))
    if (exact) return exact
  }

  const scored = recentPdfs
    .map((file) => ({ file, score: scorePdfTitle(title, file.name) }))
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score)
  return scored[0]?.file || null
}

async function uploadAndSummarize(filePath) {
  const token = getEnv("CEASER_ACCESS_TOKEN")
  const apiUrl = getEnv("CEASER_API_URL", "https://ceaser-backend-production-ur04.onrender.com")
  if (!token || typeof fetch !== "function" || typeof FormData === "undefined" || typeof Blob === "undefined") {
    return { status: "skipped", message: "CEASER desktop upload is not configured." }
  }
  try {
    const content = fs.readFileSync(filePath)
    const form = new FormData()
    form.append("upload", new Blob([content], { type: "application/pdf" }), path.basename(filePath))
    const upload = await fetch(`${apiUrl}/files/upload`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: form,
    })
    if (!upload.ok) return { status: "error", message: "Could not upload the active PDF to CEASER." }
    const file = await upload.json()
    const analysis = await fetch(`${apiUrl}/files/${file.id}/analyze`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ action: "summarize" }),
    })
    if (!analysis.ok) return { status: "error", message: "The PDF uploaded, but summarization failed." }
    const data = await analysis.json()
    return {
      status: "completed",
      message: cleanSummary(data.response || `Summarized ${file.name}.`),
      path: filePath,
      file_id: file.id,
    }
  } catch (_error) {
    return { status: "error", message: "Could not read the active PDF file." }
  }
}

function scorePdfTitle(title, fileName) {
  const normalizedTitle = normalize(title)
  const base = normalize(path.basename(fileName, path.extname(fileName)))
  if (!normalizedTitle || !base) return 0
  if (normalizedTitle.includes(normalize(fileName))) return 100
  if (normalizedTitle.includes(base)) return 90
  const words = base.split(" ").filter((word) => word.length > 2)
  const matches = words.filter((word) => normalizedTitle.includes(word)).length
  return matches >= Math.min(3, words.length) ? matches * 10 : 0
}

function cleanSummary(value) {
  return String(value || "")
    .replace(/^#+\s*/gm, "")
    .replace(/\*\*/g, "")
    .replace(/\s+\n/g, "\n")
    .trim()
}

function normalize(value) {
  return String(value || "").toLowerCase().replace(/[_-]+/g, " ").replace(/[^\w\s.]/g, "").replace(/\s+/g, " ").trim()
}

module.exports = { findActivePdf, summarizeActivePdf }
