const assert = require("node:assert/strict")
const fs = require("node:fs")
const path = require("node:path")
const test = require("node:test")

const root = path.resolve(__dirname, "..")
const source = (file) => fs.readFileSync(path.join(root, file), "utf8")

test("final blocker closure keeps startup work bounded and lazy", () => {
  const main = source("src/main/main.js")
  const python = source("python_companion/desktop_voice_server.py")

  assert.match(main, /if \(deviceRegistrationPromise\)/)
  assert.match(main, /setTimeout\(\(\) => controller\.abort\(\), 12000\)/)
  assert.match(main, /Math\.min\(60000, 2000 \* \(2 \*\*/)
  assert.match(main, /if \(applicationIndexNeedsRefresh\(\)\)/)
  assert.match(main, /LOCAL_DEVELOPMENT_CAPABILITIES/)
  assert.match(main, /BROWSER_CAPABILITIES/)

  const commandServiceFunction = python.slice(python.indexOf("def get_command_service():"))
  assert.match(commandServiceFunction, /from core\.command_service import CommandService/)
  assert.doesNotMatch(python.slice(0, python.indexOf("def get_command_service():")), /from core\.command_service import CommandService/)
  assert.match(python, /CEASER_PROACTIVE_START_DELAY_SECONDS", "15"/)
})
