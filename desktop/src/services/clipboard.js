const { clipboard } = require("electron")

function readClipboard() {
  const text = clipboard.readText()
  return {
    status: "completed",
    message: text ? "Clipboard text is ready." : "Clipboard is empty.",
    text: text.slice(0, 500),
  }
}

function copyTextToClipboard(text = "") {
  clipboard.writeText(String(text))
  return { status: "completed", message: "Text copied to clipboard." }
}

function clearClipboard() {
  clipboard.clear()
  return { status: "completed", message: "Clipboard cleared." }
}

module.exports = { clearClipboard, copyTextToClipboard, readClipboard }
