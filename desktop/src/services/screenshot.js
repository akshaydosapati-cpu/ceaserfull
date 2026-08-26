const { app, desktopCapturer } = require("electron")
const fs = require("fs")
const path = require("path")

async function takeScreenshot() {
  const sources = await desktopCapturer.getSources({ types: ["screen"], thumbnailSize: { width: 1920, height: 1080 } })
  const screen = sources[0]
  if (!screen) return { status: "error", message: "No screen source available." }
  const directory = path.join(app.getPath("pictures"), "CEASER Screenshots")
  fs.mkdirSync(directory, { recursive: true })
  const file = path.join(directory, `ceaser-${Date.now()}.png`)
  fs.writeFileSync(file, screen.thumbnail.toPNG())
  return { status: "completed", message: "Screenshot saved.", path: file }
}

module.exports = { takeScreenshot }
