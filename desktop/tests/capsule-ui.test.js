const assert = require("node:assert/strict")
const fs = require("node:fs")
const path = require("node:path")
const test = require("node:test")

const root = path.resolve(__dirname, "..")
const read = (file) => fs.readFileSync(path.join(root, file), "utf8")

test("capsule UI is state-driven, accessible, and bounded", () => {
  const html = read("src/renderer/index.html")
  const css = read("src/renderer/styles.css")
  const renderer = read("src/renderer/app.js")
  const main = read("src/main/main.js")

  assert.match(html, /id="surfaceStateLabel"/)
  assert.match(html, /class="capsule-status-dot"/)
  assert.match(html, /aria-label="Collapse overlay"/)
  assert.match(renderer, /function capsuleStateLabel\(state\)/)
  for (const state of ["listening", "thinking", "executing", "speaking", "completed", "clarifying", "offline", "error"]) {
    assert.match(renderer, new RegExp(`${state}:`))
  }
  assert.match(css, /--capsule-morph:/)
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)/)
  assert.match(css, /@media \(prefers-color-scheme: light\)/)
  assert.match(css, /max-height: var\(--dynamic-max-height/)
  assert.match(main, /compact: \[360, 68\]/)
})
