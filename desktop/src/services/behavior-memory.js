const fs = require("fs")
const os = require("os")
const path = require("path")

class BehaviorMemory {
  constructor() {
    this.file = path.join(os.homedir(), ".ceaser", "behavior-memory.json")
    fs.mkdirSync(path.dirname(this.file), { recursive: true })
  }

  observe(intent = {}, result = {}) {
    const data = this.read()
    const now = new Date()
    const hour = now.getHours()
    const action = intent.action || "unknown"
    const parameters = intent.parameters || {}
    const command = parameters.message || parameters.question || parameters.query || result.message || action
    increment(data.commands, normalizeCommand(command))
    increment(data.actions, action)
    increment(data.hours, String(hour))

    const app = parameters.app_name || parameters.app || result.app
    if (app) {
      increment(data.apps, normalizeLabel(app))
      if (hour >= 5 && hour < 12) increment(data.morning_apps, normalizeLabel(app))
    }

    const folder = parameters.folder || parameters.base
    if (folder) increment(data.folders, normalizeLabel(folder))

    const topic = extractTopic(command)
    if (topic) increment(data.topics, topic)

    if (isStudyCommand(command)) {
      increment(data.study_hours, String(hour))
    }

    const agent = intent.active_agent && intent.active_agent !== "CEASER" ? intent.active_agent : null
    if (agent) increment(data.agents, agent)

    data.last_updated_at = now.toISOString()
    this.write(data)
    return data
  }

  read() {
    if (!fs.existsSync(this.file)) return emptyMemory()
    try {
      return { ...emptyMemory(), ...JSON.parse(fs.readFileSync(this.file, "utf8")) }
    } catch (_error) {
      return emptyMemory()
    }
  }

  write(data) {
    fs.writeFileSync(this.file, JSON.stringify(data, null, 2))
  }

  profile() {
    const data = this.read()
    return {
      preferred_morning_app: topKey(data.morning_apps),
      most_used_apps: topList(data.apps, 5),
      most_used_commands: topList(data.commands, 5),
      most_used_actions: topList(data.actions, 5),
      most_used_agents: topList(data.agents, 5),
      interested_topics: topList(data.topics, 8),
      preferred_study_hour: topKey(data.study_hours),
      suggestions: this.suggestions(data),
      last_updated_at: data.last_updated_at,
    }
  }

  suggestions(data = this.read()) {
    const suggestions = []
    const morningApp = topKey(data.morning_apps)
    if (morningApp) suggestions.push(`You often open ${title(morningApp)} in the morning. Say "open my morning workspace" to start faster.`)
    const topic = topKey(data.topics)
    if (topic && (data.topics[topic] || 0) >= 3) suggestions.push(`You frequently research ${topic}. Would you like a daily ${topic} brief automation?`)
    const studyHour = topKey(data.study_hours)
    if (studyHour) suggestions.push(`Your study activity often happens around ${formatHour(studyHour)}. I can suggest a study block then.`)
    const app = topKey(data.apps)
    if (app) suggestions.push(`${title(app)} is one of your most-used apps. I can keep it one command away.`)
    return suggestions.slice(0, 4)
  }

  summary() {
    const profile = this.profile()
    const parts = []
    if (profile.most_used_apps.length) parts.push(`Most used apps: ${profile.most_used_apps.map((item) => title(item.name)).join(", ")}.`)
    if (profile.interested_topics.length) parts.push(`Interested topics: ${profile.interested_topics.map((item) => item.name).join(", ")}.`)
    if (profile.preferred_study_hour) parts.push(`Preferred study time appears around ${formatHour(profile.preferred_study_hour)}.`)
    if (profile.suggestions.length) parts.push(`Suggestion: ${profile.suggestions[0]}`)
    return parts.join(" ") || "I am still learning your habits. Use CEASER normally and I will build your personal pattern memory."
  }
}

function emptyMemory() {
  return {
    apps: {},
    folders: {},
    topics: {},
    commands: {},
    actions: {},
    agents: {},
    hours: {},
    morning_apps: {},
    study_hours: {},
    last_updated_at: null,
  }
}

function increment(bucket, key) {
  if (!key) return
  bucket[key] = (bucket[key] || 0) + 1
}

function topKey(bucket = {}) {
  return Object.entries(bucket).sort((a, b) => b[1] - a[1])[0]?.[0] || null
}

function topList(bucket = {}, limit = 5) {
  return Object.entries(bucket)
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([name, count]) => ({ name, count }))
}

function normalizeLabel(value) {
  return String(value || "").toLowerCase().replace(/[.!?,;:]+$/g, "").trim()
}

function normalizeCommand(value) {
  return normalizeLabel(value).replace(/\s+/g, " ").slice(0, 80)
}

function extractTopic(command) {
  const text = normalizeCommand(command)
  const match = text.match(/\b(?:research|find|latest|news about|search)\s+(.+)/)
  if (!match) return null
  return match[1].replace(/\b(on|in|for|about|the|a|an)\b/g, "").replace(/\s+/g, " ").trim().slice(0, 48)
}

function isStudyCommand(command) {
  return /\b(study|exam|revision|notes|mcq|flashcards|class|assignment)\b/i.test(String(command || ""))
}

function title(value) {
  return String(value || "").replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function formatHour(hour) {
  const value = Number(hour)
  if (Number.isNaN(value)) return "your usual time"
  const suffix = value >= 12 ? "PM" : "AM"
  const display = value % 12 || 12
  return `${display}:00 ${suffix}`
}

module.exports = { BehaviorMemory }
