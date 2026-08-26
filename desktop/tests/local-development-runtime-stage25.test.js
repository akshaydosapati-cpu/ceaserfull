const assert = require("node:assert/strict")
const test = require("node:test")
const fs = require("fs")
const os = require("os")
const path = require("path")
const { LocalDevelopmentRuntime } = require("../src/services/local-development-runtime")

function fixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "ceaser-stage25-"))
  return new LocalDevelopmentRuntime({ dataDir: path.join(root, "data"), projectsRoot: path.join(root, "projects") })
}
async function create(runtime, device = "device-a") {
  return runtime.execute({ request_id: "create", task_id: "task", device_id: device, capability: "project.create", arguments: { name: "Dental Clinic" } })
}

test("persistent project continuation and device isolation", async () => {
  const runtime = fixture(); const made = await create(runtime)
  assert.ok(fs.existsSync(made.project.local_path))
  const restarted = new LocalDevelopmentRuntime({ dataDir: runtime.dataDir, projectsRoot: runtime.projectsRoot })
  const found = await restarted.execute({ request_id: "meta", device_id: "device-a", capability: "project.metadata", arguments: { project_name: "dental" } })
  assert.equal(found.project.project_id, made.project.project_id)
  const denied = await restarted.execute({ request_id: "other", device_id: "device-b", capability: "project.metadata", arguments: { project_id: made.project.project_id } })
  assert.equal(denied.error_code, "project_device_mismatch")
})

test("safe write patch read and file listing", async () => {
  const runtime = fixture(); const made = await create(runtime); const ref = { project_id: made.project.project_id }
  assert.equal((await runtime.execute({ request_id: "write", device_id: "device-a", capability: "project.write_file", arguments: { ...ref, path: "src/app.js", content: "const value = 1\n" } })).verified, true)
  assert.equal((await runtime.execute({ request_id: "patch", device_id: "device-a", capability: "project.patch_file", arguments: { ...ref, path: "src/app.js", find: "1", replace: "2" } })).changed, true)
  assert.match((await runtime.execute({ request_id: "read", device_id: "device-a", capability: "project.read_file", arguments: { ...ref, path: "src/app.js" } })).content, /2/)
  assert.deepEqual((await runtime.execute({ request_id: "list", device_id: "device-a", capability: "project.list_files", arguments: ref })).files, ["src/app.js"])
})

test("path escape and sensitive files are rejected", async () => {
  const runtime = fixture(); const made = await create(runtime); const ref = { project_id: made.project.project_id }
  for (const target of ["../../outside.txt", "C:/Windows/test.txt", ".env", "keys/id_rsa"]) {
    const result = await runtime.execute({ request_id: target, device_id: "device-a", capability: "project.write_file", arguments: { ...ref, path: target, content: "secret" } })
    assert.equal(result.status, "failed"); assert.ok(["path_escape", "sensitive_file"].includes(result.error_code))
  }
})

test("scoped terminal policy and honest no-tests result", async () => {
  const runtime = fixture(); const made = await create(runtime); const ref = { project_id: made.project.project_id }
  const denied = await runtime.execute({ request_id: "shell", device_id: "device-a", capability: "terminal.run_scoped", arguments: { ...ref, argv: ["powershell", "-Command", "whoami"] } })
  assert.equal(denied.error_code, "executable_denied")
  assert.equal((await runtime.execute({ request_id: "test", device_id: "device-a", capability: "project.test", arguments: ref })).test_status, "no_tests_available")
})

test("Git status works inside the project", async (t) => {
  const runtime = fixture(); const tools = await runtime.discoverToolchains(); if (!tools.toolchains.git.available) return t.skip("Git unavailable")
  const made = await create(runtime); const ref = { project_id: made.project.project_id }
  await runtime.execute({ request_id: "write", device_id: "device-a", capability: "project.write_file", arguments: { ...ref, path: "README.md", content: "# Dental\n" } })
  assert.equal((await runtime.execute({ request_id: "init", device_id: "device-a", capability: "git.init", arguments: ref })).status, "completed")
  assert.match((await runtime.execute({ request_id: "status", device_id: "device-a", capability: "git.status", arguments: ref })).stdout, /README/)
})

test("advertises implemented capabilities but not unimplemented GitHub writes", () => {
  const caps = fixture().capabilities()
  for (const item of ["project.create", "project.patch_file", "terminal.run_scoped", "project.build", "project.test", "git.commit", "vscode.open_project"]) assert.ok(caps.includes(item))
  assert.equal(caps.includes("github.push"), false)
})
