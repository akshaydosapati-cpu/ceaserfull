const fs = require("fs")
const path = require("path")
const os = require("os")

class LocalLog {
  constructor() {
    this.file = path.join(os.homedir(), ".ceaser", "desktop.log")
    fs.mkdirSync(path.dirname(this.file), { recursive: true })
  }

  write(action, metadata = {}) {
    const safe = { ...metadata }
    delete safe.content
    delete safe.fileContent
    fs.appendFileSync(this.file, `${JSON.stringify({ at: new Date().toISOString(), action, metadata: safe })}\n`)
  }
}

const logger = new LocalLog()

function logEvent(action, metadata = {}) {
  logger.write(action, metadata)
}

module.exports = { LocalLog, logEvent }
