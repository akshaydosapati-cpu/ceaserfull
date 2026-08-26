const { app, desktopCapturer, screen } = require("electron")
const { spawn } = require("child_process")
const fs = require("fs")
const path = require("path")

async function captureScreen() {
  const display = screen.getPrimaryDisplay()
  const size = display.size || { width: 1920, height: 1080 }
  const sources = await desktopCapturer.getSources({
    types: ["screen"],
    thumbnailSize: { width: Math.max(size.width, 1280), height: Math.max(size.height, 720) },
  })
  const source = sources[0]
  if (!source) return { status: "error", message: "No screen source available." }
  const directory = path.join(app.getPath("pictures"), "CEASER Vision")
  fs.mkdirSync(directory, { recursive: true })
  const file = path.join(directory, `screen-${Date.now()}.png`)
  fs.writeFileSync(file, source.thumbnail.toPNG())
  return { status: "completed", path: file }
}

async function readScreenText() {
  const shot = await captureScreen()
  if (shot.status !== "completed") return shot
  const text = await runTesseract(shot.path)
  if (!text.trim()) {
    return { status: "completed", message: "I captured the screen, but I could not find readable text.", path: shot.path, text: "" }
  }
  return {
    status: "completed",
    message: `I read the screen text:\n${text.trim().slice(0, 1200)}`,
    path: shot.path,
    text: text.trim(),
  }
}

async function analyzeScreen() {
  const shot = await captureScreen()
  if (shot.status !== "completed") return shot
  const text = await runTesseract(shot.path)
  const display = screen.getPrimaryDisplay()
  const parts = [
    `Screen captured at ${display.size.width}x${display.size.height}.`,
    text.trim() ? `Readable text found:\n${text.trim().slice(0, 1000)}` : "No readable text was detected.",
    `Screenshot saved to ${shot.path}`,
  ]
  return { status: "completed", message: parts.join("\n"), path: shot.path, text: text.trim() }
}

function screenInfo() {
  const displays = screen.getAllDisplays()
  const cursor = screen.getCursorScreenPoint()
  return {
    status: "completed",
    message: `Detected ${displays.length} display(s). Cursor is at ${cursor.x}, ${cursor.y}. Primary screen is ${screen.getPrimaryDisplay().size.width}x${screen.getPrimaryDisplay().size.height}.`,
    displays: displays.map((display) => ({ id: display.id, bounds: display.bounds, scaleFactor: display.scaleFactor })),
  }
}

function runTesseract(imagePath) {
  return new Promise((resolve) => {
    const candidates = [
      process.env.TESSERACT_EXE,
      "C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
      "C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe",
      "tesseract",
    ].filter(Boolean)
    let index = 0
    const tryNext = () => {
      const exe = candidates[index++]
      if (!exe) return resolve("")
      const child = spawn(exe, [imagePath, "stdout", "--psm", "6"], { windowsHide: true })
      let output = ""
      child.stdout.on("data", (chunk) => { output += String(chunk) })
      child.on("close", (code) => {
        if (code === 0) resolve(output)
        else tryNext()
      })
      child.on("error", tryNext)
    }
    tryNext()
  })
}

module.exports = { analyzeScreen, captureScreen, readScreenText, screenInfo }
