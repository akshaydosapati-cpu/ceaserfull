const fs = require("fs")
const path = require("path")
const os = require("os")

const DEFAULTS = {
  allow_app_launch: false,
  allow_file_read: false,
  allow_file_write: false,
  allow_screenshot: false,
  allow_clipboard: false,
}

class PermissionStore {
  constructor() {
    this.file = path.join(os.homedir(), ".ceaser", "permissions.json")
    fs.mkdirSync(path.dirname(this.file), { recursive: true })
  }

  all() {
    if (!fs.existsSync(this.file)) return { ...DEFAULTS }
    return { ...DEFAULTS, ...JSON.parse(fs.readFileSync(this.file, "utf8")) }
  }

  set(key, value) {
    const current = this.all()
    current[key] = Boolean(value)
    fs.writeFileSync(this.file, JSON.stringify(current, null, 2))
    return current
  }

  allowed(key) {
    return Boolean(this.all()[key])
  }
}

module.exports = { PermissionStore }
