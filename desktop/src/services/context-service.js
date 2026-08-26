const { getActiveWindow, listOpenWindows } = require("./window-context")
const { BehaviorMemory } = require("./behavior-memory")
const { SessionMemory } = require("./session-memory")
const { findRecentFiles } = require("./file-actions")

class ContextService {
  constructor() {
    this.memory = new SessionMemory()
    this.behavior = new BehaviorMemory()
    this.fileCache = { at: 0, files: [] }
  }

  async snapshot() {
    const active = await getActiveWindow()
    const windows = await listOpenWindows()
    const recentEvents = this.memory.recent(5)
    const behavior = this.behavior.profile()
    const now = Date.now()
    if (now - this.fileCache.at > 120000) {
      this.fileCache = { at: now, files: findRecentFiles({ limit: 5, maxPerRoot: 350 }) }
    }
    const recentFiles = this.fileCache.files
    return {
      activeWindow: active,
      openWindows: windows.slice(0, 8),
      recentEvents,
      recentFiles,
      session: this.memory.summary(),
      behavior,
    }
  }
}

module.exports = { ContextService }
