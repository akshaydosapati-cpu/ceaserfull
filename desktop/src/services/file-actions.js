const { app, clipboard, shell } = require("electron")
const fs = require("fs")
const path = require("path")

const bases = {
  desktop: () => app.getPath("desktop"),
  documents: () => app.getPath("documents"),
  downloads: () => app.getPath("downloads"),
  music: () => app.getPath("music"),
  pictures: () => app.getPath("pictures"),
  videos: () => app.getPath("videos"),
}

async function openFolder(folder) {
  const base = resolveBase(folder)
  if (!base) return { status: "error", message: "Folder is not supported." }
  const error = await shell.openPath(base)
  if (error) return { status: "error", message: "Could not open folder." }
  return { status: "completed", message: `${title(folder)} opened.`, path: base }
}

function createFolder(baseName, name) {
  const base = resolveBase(baseName)
  if (!base) return { status: "error", message: "Folder location is not supported." }
  const safeName = sanitizeName(name || "CEASER Folder")
  const target = path.join(base, safeName)
  fs.mkdirSync(target, { recursive: true })
  return { status: "completed", message: `Folder created: ${path.basename(target)}`, path: target }
}

async function openFile(query) {
  const found = isLatestQuery(query) ? findLatestFile(query) : findFirstFile(query)
  if (!found) return { status: "error", message: `Could not find file: ${query}` }
  const error = await shell.openPath(found)
  if (error) return { status: "error", message: `Could not open ${path.basename(found)}.` }
  return { status: "completed", message: `Opened ${path.basename(found)}.`, path: found }
}

function findFile(query) {
  const found = isLatestQuery(query) ? findLatestFile(query) : findFirstFile(query)
  if (!found) return { status: "error", message: `No file found for "${query}".` }
  return { status: "completed", message: `Found ${path.basename(found)}.`, path: found }
}

function getFileDetails(query) {
  const found = findFirstFile(query)
  if (!found) return { status: "error", message: `No file found for "${query}".` }
  const stats = fs.statSync(found)
  return {
    status: "completed",
    message: `${path.basename(found)} - ${Math.round(stats.size / 1024)} KB - modified ${stats.mtime.toLocaleString()}`,
    path: found,
  }
}

function copyPath(value) {
  const target = resolveBase(value) || value
  if (!target) return { status: "error", message: "No path available to copy." }
  clipboard.writeText(target)
  return { status: "completed", message: "Path copied to clipboard.", path: target }
}

function showInExplorer(target) {
  if (!target || !fs.existsSync(target)) return { status: "error", message: "Path not found." }
  shell.showItemInFolder(target)
  return { status: "completed", message: "Shown in Explorer.", path: target }
}

function findFirstFile(query) {
  const terms = smartTerms(normalize(query))
  if (!terms.length) return null
  const roots = [resolveBase("downloads"), resolveBase("documents"), resolveBase("desktop")].filter(Boolean)
  for (const root of roots) {
    const found = searchRoot(root, terms)
    if (found) return found
  }
  return null
}

function findLatestFile(query = "") {
  const type = fileTypeFromQuery(normalize(query))
  return findRecentFiles({ limit: 1, type })[0]?.path || null
}

function findRecentFiles({ limit = 10, type = null, since = null, maxPerRoot = 1200 } = {}) {
  const roots = [resolveBase("downloads"), resolveBase("documents"), resolveBase("desktop")].filter(Boolean)
  const files = []
  for (const root of roots) collectFiles(root, files, maxPerRoot)
  return files
    .filter((file) => !type || extensionType(file.path) === type)
    .filter((file) => !since || file.mtime >= since)
    .sort((a, b) => b.mtime - a.mtime)
    .slice(0, limit)
    .map((file) => ({
      name: path.basename(file.path),
      path: file.path,
      modified: new Date(file.mtime).toISOString(),
      type: extensionType(file.path),
    }))
}

function searchRoot(root, terms) {
  const stack = [root]
  let scanned = 0
  while (stack.length && scanned < 5000) {
    const current = stack.pop()
    scanned += 1
    let entries = []
    try {
      entries = fs.readdirSync(current, { withFileTypes: true })
    } catch (_error) {
      continue
    }
    for (const entry of entries) {
      const fullPath = path.join(current, entry.name)
      if (entry.isDirectory()) stack.push(fullPath)
      else if (terms.every((term) => normalize(entry.name).includes(term))) return fullPath
    }
  }
  return null
}

function collectFiles(root, output, max) {
  const stack = [root]
  let scanned = 0
  while (stack.length && scanned < max) {
    const current = stack.pop()
    scanned += 1
    let entries = []
    try {
      entries = fs.readdirSync(current, { withFileTypes: true })
    } catch (_error) {
      continue
    }
    for (const entry of entries) {
      const fullPath = path.join(current, entry.name)
      if (entry.isDirectory()) stack.push(fullPath)
      else {
        try {
          const stats = fs.statSync(fullPath)
          output.push({ path: fullPath, mtime: stats.mtimeMs })
        } catch (_error) {
          // Skip inaccessible files.
        }
      }
    }
  }
}

function resolveBase(name) {
  return bases[String(name || "").toLowerCase()]?.()
}

function sanitizeName(value) {
  return String(value).replace(/[<>:"/\\|?*]/g, "").trim() || "CEASER Folder"
}

function smartTerms(query) {
  const stop = new Set(["find", "file", "about", "the", "my", "latest", "recent", "yesterday", "today", "open"])
  return query
    .split(" ")
    .map((term) => term.trim())
    .filter((term) => term && !stop.has(term))
}

function isLatestQuery(query) {
  return /\b(latest|recent|most recent)\b/i.test(String(query || ""))
}

function fileTypeFromQuery(query) {
  if (/\b(pdf|report)\b/.test(query)) return "pdf"
  if (/\b(presentation|deck|ppt|pptx)\b/.test(query)) return "presentation"
  if (/\b(document|doc|docx|word)\b/.test(query)) return "document"
  if (/\b(image|photo|png|jpg|jpeg)\b/.test(query)) return "image"
  if (/\b(sheet|excel|xlsx|xls)\b/.test(query)) return "spreadsheet"
  if (/\b(text|txt|note)\b/.test(query)) return "text"
  return null
}

function extensionType(filePath) {
  const ext = path.extname(filePath).toLowerCase()
  if (ext === ".pdf") return "pdf"
  if ([".ppt", ".pptx"].includes(ext)) return "presentation"
  if ([".doc", ".docx"].includes(ext)) return "document"
  if ([".xls", ".xlsx"].includes(ext)) return "spreadsheet"
  if ([".png", ".jpg", ".jpeg", ".gif", ".webp"].includes(ext)) return "image"
  if ([".txt", ".md"].includes(ext)) return "text"
  return "file"
}

function normalize(value) {
  return String(value || "").toLowerCase().replace(/\s+/g, " ").trim()
}

function title(value) {
  return String(value || "").replace(/\b\w/g, (letter) => letter.toUpperCase())
}

module.exports = { copyPath, createFolder, findFile, findRecentFiles, getFileDetails, openFile, openFolder, showInExplorer }
