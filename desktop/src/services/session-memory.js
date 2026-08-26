const fs = require("fs")
const os = require("os")
const path = require("path")

class SessionMemory {
  constructor() {
    this.file = path.join(os.homedir(), ".ceaser", "desktop-session.json")
    fs.mkdirSync(path.dirname(this.file), { recursive: true })
  }

  add(event) {
    const data = this.read()
    const record = {
      id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      at: new Date().toISOString(),
      ...event,
    }
    data.events.unshift(record)
    data.events = data.events.slice(0, 500)
    fs.writeFileSync(this.file, JSON.stringify(data, null, 2))
    return record
  }

  read() {
    if (!fs.existsSync(this.file)) return { events: [] }
    try {
      const data = JSON.parse(fs.readFileSync(this.file, "utf8"))
      return { events: Array.isArray(data.events) ? data.events : [] }
    } catch (_error) {
      return { events: [] }
    }
  }

  recent(limit = 8) {
    return this.read().events.slice(0, limit)
  }

  today() {
    const start = new Date()
    start.setHours(0, 0, 0, 0)
    return this.read().events.filter((event) => new Date(event.at) >= start)
  }

  summary() {
    const events = this.today()
    const apps = unique(events.map((event) => event.app || event.parameters?.app_name || event.parameters?.app).filter(Boolean))
    const actions = events.slice(0, 6).map((event) => event.label || event.action).filter(Boolean)
    return {
      count: events.length,
      apps,
      actions,
      message: events.length
        ? `Today CEASER tracked ${events.length} desktop events. Apps: ${apps.slice(0, 4).join(", ") || "none yet"}.`
        : "No desktop activity has been tracked today yet.",
    }
  }
}

function unique(values) {
  return [...new Set(values)]
}

module.exports = { SessionMemory }
