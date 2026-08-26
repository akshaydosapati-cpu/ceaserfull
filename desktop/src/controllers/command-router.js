const { ActionRouter } = require("../actions/actionRouter")
const { executeAction } = require("../actions/actionExecutor")
const { permissionFor } = require("../actions/actionPermissions")
const { getEnv } = require("../services/env")
const { logEvent } = require("../services/local-log")

const API_URL = getEnv("CEASER_API_URL", "https://ceaser-backend-production-ur04.onrender.com")

class CommandRouter {
  constructor({ permissions }) {
    this.permissions = permissions
    this.actionRouter = new ActionRouter()
  }

  async classify(payload = {}) {
    const command = String(payload.command || "").trim()
    if (!command) return this.actionRouter.route("chat")

    const local = this.actionRouter.route(command)
    if (local.intent === "identity_action") return local
    if (local.intent === "desktop_action" || local.intent === "blocked_action") return local

    const backend = await this.classifyWithBackend(command, payload)
    if (backend) return normalizeIntent(backend)

    return local
  }

  async execute(intent = {}) {
    const permission = intent.required_permission || permissionFor(intent.action)
    if (permission && !this.permissions.allowed(permission)) {
      return {
        status: "permission_required",
        permission,
        message: "CEASER needs permission before doing this.",
      }
    }

    if (intent.requires_confirmation && !intent.confirmed) {
      return {
        status: "confirmation_required",
        message: "Confirm this action before CEASER continues.",
      }
    }

    logEvent("desktop_action_execute", { action: intent.action, risk_level: intent.risk_level })
    return executeAction(intent)
  }

  async classifyWithBackend(command, payload) {
    const token = getEnv("CEASER_ACCESS_TOKEN")
    if (!token || !global.fetch) return null
    try {
      const response = await fetch(`${API_URL}/desktop/intent`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ command }),
      })
      if (!response.ok) return null
      return response.json()
    } catch (_error) {
      return null
    }
  }
}

function normalizeIntent(intent) {
  if (!intent.intent && intent.intent_type) intent.intent = intent.intent_type
  if (!intent.intent_type && intent.intent) intent.intent_type = intent.intent
  if (!("requires_permission" in intent)) intent.requires_permission = Boolean(permissionFor(intent.action))
  if (!("required_permission" in intent)) intent.required_permission = permissionFor(intent.action)
  if (!("risk_level" in intent)) intent.risk_level = "low"
  return intent
}

module.exports = { CommandRouter }
