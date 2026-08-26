const assert = require("node:assert/strict")
const test = require("node:test")

const { DeviceGatewayClient, gatewayUrl } = require("../src/services/device-gateway-client")

function client(execute = async () => ({ status: "completed", verified: true, message: "Opened Chrome" })) {
  const sent = []
  const instance = new DeviceGatewayClient({
    apiUrl: "https://api.example.com",
    getSession: () => ({ access_token: "not-logged" }),
    getDevice: () => ({ device_id: "device-1" }),
    execute,
    log: () => {},
  })
  instance.send = (payload) => sent.push(payload)
  return { instance, sent }
}

test("gateway URL preserves authenticated websocket route", () => {
  assert.equal(gatewayUrl("https://api.example.com"), "wss://api.example.com/desktop/gateway")
  assert.equal(gatewayUrl("http://127.0.0.1:8000/api"), "ws://127.0.0.1:8000/api/desktop/gateway")
})

test("device result preserves request correlation and verification", async () => {
  const { instance, sent } = client()
  await instance.onMessage(JSON.stringify({
    type: "device.capability.request",
    payload: { request_id: "req-1", task_id: "task-1", agent_id: "bolt", device_id: "device-1", capability: "desktop.open_application" },
  }))
  await instance.activeRequests.get("req-1")
  assert.equal(sent[0].payload.request_id, "req-1")
  assert.equal(sent[0].payload.status, "completed")
  assert.equal(sent[0].payload.verification.device_id, "device-1")
})

test("duplicate delivery reuses the correlated result without re-execution", async () => {
  let executions = 0
  const { instance, sent } = client(async () => { executions += 1; return { status: "completed", verified: true } })
  const message = JSON.stringify({ type: "device.capability.request", payload: {
    request_id: "req-2", task_id: "task-2", agent_id: "bolt", device_id: "device-1", capability: "desktop.take_screenshot",
  } })
  await instance.onMessage(message)
  await instance.activeRequests.get("req-2")
  await instance.onMessage(message)
  assert.equal(executions, 1)
  assert.equal(sent.length, 2)
})
