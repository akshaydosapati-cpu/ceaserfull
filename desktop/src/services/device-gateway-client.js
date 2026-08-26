const WebSocket = require("ws")

const BASE_DEVICE_CAPABILITIES = [
  "desktop.open_application",
  "desktop.close_application",
  "desktop.open_folder",
  "desktop.open_file",
  "desktop.open_url",
  "desktop.take_screenshot",
  "desktop.set_volume",
  "desktop.get_battery",
  "desktop.media_play_pause",
  "ai.answer",
  "ai.news",
  "github.list_repositories",
  "github.resolve_repository",
  "github.get_readme",
  "github.list_commits",
  "github.list_issues",
  "github.list_pull_requests",
  "github.summarize_repository",
  "notion.search_pages",
  "notion.get_page",
  "notion.list_tasks",
  "cloud.list",
  "cloud.search",
  "cloud.latest",
  "cloud.read",
  "cloud.download",
  "study.generate_viva_questions",
  "study.generate_revision_notes",
  "study.generate_quiz",
  "ai.summarize_activity",
  "workflow.plan",
]

function gatewayUrl(apiUrl) {
  const url = new URL(apiUrl)
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:"
  url.pathname = `${url.pathname.replace(/\/$/, "")}/desktop/gateway`
  url.search = ""
  return url.toString()
}

class DeviceGatewayClient {
  constructor({ apiUrl, getSession, getDevice, execute, capabilities = BASE_DEVICE_CAPABILITIES, onUnauthorized, onRevoked, log = console.log }) {
    this.apiUrl = apiUrl
    this.getSession = getSession
    this.getDevice = getDevice
    this.execute = execute
    this.capabilities = [...new Set(capabilities)]
    this.onUnauthorized = onUnauthorized
    this.onRevoked = onRevoked
    this.log = log
    this.socket = null
    this.stopped = true
    this.reconnectAttempt = 0
    this.reconnectTimer = null
    this.heartbeatTimer = null
    this.activeRequests = new Map()
    this.completedRequests = new Map()
  }

  start() {
    this.stopped = false
    this.connect()
  }

  stop() {
    this.stopped = true
    clearTimeout(this.reconnectTimer)
    clearInterval(this.heartbeatTimer)
    this.reconnectTimer = null
    this.heartbeatTimer = null
    const socket = this.socket
    this.socket = null
    if (socket && socket.readyState < WebSocket.CLOSING) socket.close(1000, "shutdown")
  }

  restart() {
    this.stop()
    this.start()
  }

  connect() {
    if (this.stopped || this.socket) return
    const session = this.getSession() || {}
    const device = this.getDevice() || {}
    if (!session.access_token || !device.device_id) {
      this.log("device_gateway_waiting_for_session")
      this.scheduleReconnect()
      return
    }
    const socket = new WebSocket(gatewayUrl(this.apiUrl), {
      headers: { Authorization: `Bearer ${session.access_token}` },
      handshakeTimeout: 10000,
    })
    this.socket = socket
    socket.on("open", () => {
      this.reconnectAttempt = 0
      this.send({ type: "device.hello", capabilities: this.capabilities })
      this.heartbeatTimer = setInterval(() => this.send({ type: "device.heartbeat" }), 15000)
      this.log(`device_gateway_connected device_id=${device.device_id}`)
    })
    socket.on("message", (data) => this.onMessage(data))
    socket.on("error", (error) => this.log(`device_gateway_error type=${error?.name || "Error"}`))
    socket.on("close", (code) => {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
      if (this.socket === socket) this.socket = null
      this.log(`device_gateway_closed code=${code}`)
      if (code === 4401) {
        Promise.resolve(this.onUnauthorized?.()).finally(() => this.scheduleReconnect())
        return
      }
      if (code === 4403) {
        this.stopped = true
        this.onRevoked?.(code)
        return
      }
      this.scheduleReconnect()
    })
  }

  scheduleReconnect() {
    if (this.stopped || this.reconnectTimer) return
    const delay = Math.min(30000, 1000 * (2 ** Math.min(this.reconnectAttempt, 5)))
    this.reconnectAttempt += 1
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      this.connect()
    }, delay)
  }

  send(payload) {
    if (this.socket?.readyState === WebSocket.OPEN) this.socket.send(JSON.stringify(payload))
  }

  async onMessage(data) {
    let message
    try {
      message = JSON.parse(String(data))
    } catch (_error) {
      return
    }
    if (message.type !== "device.capability.request") return
    const request = message.payload || {}
    if (!request.request_id) return
    const cached = this.completedRequests.get(request.request_id)
    if (cached) {
      this.send({ type: "device.capability.result", payload: cached })
      return
    }
    if (this.activeRequests.has(request.request_id)) return
    const task = this.execute(request)
      .then((result) => this.resultPayload(request, result))
      .catch((error) => this.errorPayload(request, error))
      .then((payload) => {
        this.completedRequests.set(request.request_id, payload)
        if (this.completedRequests.size > 200) this.completedRequests.delete(this.completedRequests.keys().next().value)
        this.send({ type: "device.capability.result", payload })
      })
      .finally(() => this.activeRequests.delete(request.request_id))
    this.activeRequests.set(request.request_id, task)
  }

  resultPayload(request, result = {}) {
    const status = ["completed", "failed", "timeout", "cancelled"].includes(result.status)
      ? result.status
      : result.status === "error" ? "failed" : "completed"
    return {
      request_id: request.request_id,
      status,
      output: result,
      error: status === "failed" ? { code: result.error_code || "device_execution_failed", message: result.message || "Device action failed." } : null,
      verification: { verified: result.verified !== false, device_id: request.device_id },
      metadata: { capability: request.capability, task_id: request.task_id, agent_id: request.agent_id },
    }
  }

  errorPayload(request, error) {
    return {
      request_id: request.request_id,
      status: "failed",
      output: {},
      error: { code: "device_execution_error", message: String(error?.message || "Device action failed.").slice(0, 300) },
      verification: { verified: false, device_id: request.device_id },
      metadata: { capability: request.capability, task_id: request.task_id, agent_id: request.agent_id },
    }
  }
}

module.exports = { DEVICE_CAPABILITIES: BASE_DEVICE_CAPABILITIES, BASE_DEVICE_CAPABILITIES, DeviceGatewayClient, gatewayUrl }
