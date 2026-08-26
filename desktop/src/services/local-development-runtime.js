const fs = require("fs")
const path = require("path")
const os = require("os")
const crypto = require("crypto")
const { execFile, spawn } = require("child_process")

const SECRET_NAMES = /(^|\/)(\.env(?:\..*)?|credentials?|.*(?:private|secret)[-_]?key.*|id_rsa|id_ed25519)(\/|$)/i
const IGNORED = new Set(["node_modules", ".git", "dist", "build", ".next", "__pycache__", ".venv", "venv"])
const ALLOWED_TOOLS = new Set(["node", "npm", "npx", "python", "python3", "py", "pip", "pip3", "git"])
const LOCAL_DEVELOPMENT_CAPABILITIES = [
  "project.create", "project.open", "project.inspect", "project.list", "project.exists", "project.metadata",
  "project.list_files", "project.read_file", "project.write_file", "project.patch_file", "project.create_directory",
  "project.rename", "project.copy", "project.delete", "project.stat", "project.build", "project.test", "project.export_files",
  "terminal.run_scoped", "toolchain.discover", "git.init", "git.status", "git.diff", "git.add", "git.commit",
  "git.log", "git.set_remote", "vscode.open_project", "bolt.execute_plan",
]

function slug(value) {
  return String(value || "project").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 80) || "project"
}

function now() { return new Date().toISOString() }

class RuntimeError extends Error {
  constructor(code, message) { super(message); this.code = code }
}

class LocalDevelopmentRuntime {
  constructor({ dataDir, projectsRoot, execFileImpl = execFile } = {}) {
    this.dataDir = path.resolve(dataDir || path.join(process.env.APPDATA || os.homedir(), "CEASER"))
    this.projectsRoot = path.resolve(projectsRoot || process.env.CEASER_PROJECTS_ROOT || path.join(os.homedir(), "CEASER Projects"))
    this.indexPath = path.join(this.dataDir, "local-projects.json")
    this.execFileImpl = execFileImpl
    this.running = new Map()
    fs.mkdirSync(this.dataDir, { recursive: true })
    fs.mkdirSync(this.projectsRoot, { recursive: true })
  }

  capabilities() {
    return LOCAL_DEVELOPMENT_CAPABILITIES.slice()
  }

  loadIndex() {
    try { return JSON.parse(fs.readFileSync(this.indexPath, "utf8")) } catch (_error) { return { projects: [] } }
  }

  saveIndex(index) {
    const temp = `${this.indexPath}.${process.pid}.tmp`
    fs.writeFileSync(temp, JSON.stringify(index, null, 2), "utf8")
    fs.renameSync(temp, this.indexPath)
  }

  project(arguments_ = {}, deviceId = "local") {
    const index = this.loadIndex()
    const id = String(arguments_.project_id || "")
    const query = String(arguments_.project_name || arguments_.name || "").toLowerCase()
    const owned = index.projects.filter((item) => !item.device_id || item.device_id === deviceId)
    let matches = id ? index.projects.filter((item) => item.project_id === id) : query ? owned.filter((item) => item.display_name.toLowerCase().includes(query)) : []
    if (!id && !query && arguments_.active_project_id) matches = index.projects.filter((item) => item.project_id === arguments_.active_project_id)
    if (!id && !query && !arguments_.active_project_id && owned.length) matches = [owned.slice().sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at)))[0]]
    if (matches.length !== 1) throw new RuntimeError(matches.length ? "ambiguous_project" : "project_not_found", matches.length ? "More than one local project matched." : "Local project not found.")
    const project = matches[0]
    if (project.device_id && project.device_id !== deviceId) throw new RuntimeError("project_device_mismatch", "Project belongs to another device.")
    return { index, project }
  }

  resolve(project, relative = ".", { allowSecret = false } = {}) {
    const root = fs.realpathSync(project.local_path)
    const requested = String(relative || ".").replace(/\\/g, "/")
    if (path.isAbsolute(requested) || /^[a-z]:/i.test(requested) || requested.startsWith("//")) throw new RuntimeError("path_escape", "Absolute and UNC paths are not allowed.")
    if (!allowSecret && SECRET_NAMES.test(`/${requested}`)) throw new RuntimeError("sensitive_file", "Sensitive files are protected.")
    const candidate = path.resolve(root, requested)
    let existing = fs.existsSync(candidate) ? candidate : path.dirname(candidate)
    while (!fs.existsSync(existing) && existing !== path.dirname(existing)) existing = path.dirname(existing)
    const parent = fs.realpathSync(existing)
    if (candidate !== root && !candidate.startsWith(`${root}${path.sep}`)) throw new RuntimeError("path_escape", "Path escapes the project workspace.")
    if (parent !== root && !parent.startsWith(`${root}${path.sep}`)) throw new RuntimeError("path_escape", "Resolved path escapes the project workspace.")
    return candidate
  }

  create(args, deviceId) {
    const displayName = String(args.display_name || args.name || "Untitled Project").trim().slice(0, 120)
    const projectId = crypto.randomUUID()
    let projectPath = path.join(this.projectsRoot, slug(displayName))
    if (fs.existsSync(projectPath)) projectPath = path.join(this.projectsRoot, `${slug(displayName)}-${projectId.slice(0, 8)}`)
    fs.mkdirSync(projectPath, { recursive: false })
    const stamp = now()
    const project = { project_id: projectId, device_id: deviceId, display_name: displayName, local_path: projectPath,
      framework: args.framework || null, language: args.language || null, created_at: stamp, updated_at: stamp,
      git_enabled: false, git_repository: null, last_revision: null, last_build_status: null,
      last_test_status: null, last_bolt_task: args.task_id || null }
    const index = this.loadIndex(); index.projects.push(project); this.saveIndex(index)
    return { status: "completed", verified: fs.existsSync(projectPath), project }
  }

  importProject(args, deviceId) {
    const localPath = path.resolve(String(args.local_path || ""))
    if (!localPath || !fs.statSync(localPath).isDirectory()) throw new RuntimeError("project_not_found", "Authorized project directory does not exist.")
    const root = fs.realpathSync(localPath)
    const stamp = now(); const index = this.loadIndex()
    const existing = index.projects.find((item) => fs.existsSync(item.local_path) && fs.realpathSync(item.local_path) === root)
    if (existing) return { status: "completed", verified: true, project: existing, existing: true }
    const project = { project_id: crypto.randomUUID(), device_id: deviceId, display_name: args.display_name || path.basename(root), local_path: root,
      framework: null, language: null, created_at: stamp, updated_at: stamp, git_enabled: fs.existsSync(path.join(root, ".git")),
      git_repository: null, last_revision: null, last_build_status: null, last_test_status: null, last_bolt_task: args.task_id || null }
    index.projects.push(project); this.saveIndex(index)
    return { status: "completed", verified: true, project }
  }

  listFiles(project) {
    const files = []
    const walk = (dir) => {
      for (const item of fs.readdirSync(dir, { withFileTypes: true })) {
        if (IGNORED.has(item.name)) continue
        const full = path.join(dir, item.name); const rel = path.relative(project.local_path, full).replace(/\\/g, "/")
        if (SECRET_NAMES.test(`/${rel}`)) continue
        if (item.isSymbolicLink()) continue
        if (item.isDirectory()) walk(full); else files.push(rel)
        if (files.length >= 5000) return
      }
    }
    walk(project.local_path); return files
  }

  async run(args, project, requestId) {
    const argv = Array.isArray(args.argv) ? args.argv.map(String) : []
    if (!argv.length || !ALLOWED_TOOLS.has(path.basename(argv[0]).replace(/\.exe$/i, "").toLowerCase())) throw new RuntimeError("executable_denied", "Executable is not allowed for scoped development.")
    if (argv.some((item) => item.includes("\x00"))) throw new RuntimeError("invalid_argument", "Invalid command argument.")
    const cwd = this.resolve(project, args.cwd || ".")
    const timeoutMs = Math.min(Math.max(Number(args.timeout_seconds || 120), 1), 900) * 1000
    const started = Date.now()
    return await new Promise((resolve) => {
      const child = spawn(argv[0], argv.slice(1), { cwd, shell: false, windowsHide: true,
        env: { PATH: process.env.PATH, SystemRoot: process.env.SystemRoot, TEMP: process.env.TEMP, TMP: process.env.TMP, CI: "1", NO_COLOR: "1" } })
      this.running.set(requestId, child)
      let stdout = "", stderr = "", truncated = false
      const append = (key, chunk) => { const value = String(chunk); if ((key === "out" ? stdout : stderr).length + value.length > 1048576) truncated = true; else if (key === "out") stdout += value; else stderr += value }
      child.stdout?.on("data", (data) => append("out", data)); child.stderr?.on("data", (data) => append("err", data))
      const timer = setTimeout(() => { try { spawn("taskkill", ["/pid", String(child.pid), "/T", "/F"], { windowsHide: true }) } catch (_error) {} }, timeoutMs)
      child.on("error", (error) => { clearTimeout(timer); this.running.delete(requestId); resolve({ status: "failed", verified: false, error_code: error.code === "ENOENT" ? `${path.basename(argv[0])}_missing` : "process_error", message: error.message }) })
      child.on("close", (code, signal) => { clearTimeout(timer); this.running.delete(requestId); resolve({ status: code === 0 ? "completed" : signal ? "cancelled" : "failed", verified: code === 0, exit_code: code, stdout, stderr, truncated, duration_ms: Date.now() - started, argv: argv.slice(0, 8) }) })
    })
  }

  cancel(requestId) {
    const child = this.running.get(requestId); if (!child) return false
    spawn("taskkill", ["/pid", String(child.pid), "/T", "/F"], { windowsHide: true }); return true
  }

  async execute(request) {
    const cap = request.capability; const args = request.arguments || {}; const deviceId = request.device_id || "local"
    try {
      if (cap === "project.create") return this.create({ ...args, task_id: request.task_id }, deviceId)
      if (cap === "bolt.execute_plan") return await this.executePlan(request)
      if (cap === "project.open") return this.importProject({ ...args, task_id: request.task_id }, deviceId)
      if (cap === "project.list") return { status: "completed", verified: true, projects: this.loadIndex().projects.filter((p) => p.device_id === deviceId) }
      if (cap === "toolchain.discover") return this.discoverToolchains()
      if (cap === "development.cancel") return { status: this.cancel(args.request_id || request.request_id) ? "cancelled" : "failed", verified: true }
      const { index, project } = this.project(args, deviceId)
      if (cap === "project.exists") return { status: "completed", verified: fs.existsSync(project.local_path), exists: fs.existsSync(project.local_path) }
      if (cap === "project.metadata") return { status: "completed", verified: true, project }
      if (cap === "project.inspect") return { status: "completed", verified: true, project, files: this.listFiles(project), toolchains: await this.discoverToolchains() }
      if (cap === "project.list_files") return { status: "completed", verified: true, files: this.listFiles(project) }
      if (cap === "project.export_files") {
        const files = []; let total = 0; const listed = this.listFiles(project)
        for (const relative of listed) {
          const target = this.resolve(project, relative); const size = fs.statSync(target).size
          if (size > 524288 || total + size > 5242880) continue
          try { files.push({ path: relative, content: fs.readFileSync(target, "utf8") }); total += size } catch (_error) {}
        }
        return { status: "completed", verified: true, project, files, total_bytes: total, truncated: files.length < listed.length }
      }
      if (cap === "project.read_file") { const target = this.resolve(project, args.path); const stat = fs.statSync(target); if (stat.size > 524288) throw new RuntimeError("file_too_large", "File exceeds the safe read limit."); return { status: "completed", verified: true, path: args.path, content: fs.readFileSync(target, "utf8") } }
      if (["project.write_file", "project.patch_file"].includes(cap)) { const target = this.resolve(project, args.path); fs.mkdirSync(path.dirname(target), { recursive: true }); const before = fs.existsSync(target) ? fs.readFileSync(target, "utf8") : ""; if (cap === "project.patch_file" && args.expected_content != null && before !== String(args.expected_content)) throw new RuntimeError("patch_conflict", "File changed since the patch was prepared."); const content = args.content != null ? String(args.content) : before.replace(String(args.find || ""), String(args.replace || "")); if (content === before && cap === "project.patch_file") throw new RuntimeError("patch_not_applied", "Patch did not change the target file."); fs.writeFileSync(target, content, "utf8"); return { status: "completed", verified: fs.readFileSync(target, "utf8") === content, path: args.path, bytes: Buffer.byteLength(content), changed: before !== content } }
      if (cap === "project.create_directory") { fs.mkdirSync(this.resolve(project, args.path), { recursive: true }); return { status: "completed", verified: true, path: args.path } }
      if (["project.rename", "project.copy"].includes(cap)) { const source = this.resolve(project, args.path); const destination = this.resolve(project, args.destination); fs.mkdirSync(path.dirname(destination), { recursive: true }); cap === "project.rename" ? fs.renameSync(source, destination) : fs.cpSync(source, destination, { recursive: true }); return { status: "completed", verified: fs.existsSync(destination), destination: args.destination } }
      if (cap === "project.delete") { const target = this.resolve(project, args.path); fs.rmSync(target, { recursive: true, force: false }); return { status: "completed", verified: !fs.existsSync(target), path: args.path } }
      if (cap === "project.stat") { const stat = fs.statSync(this.resolve(project, args.path)); return { status: "completed", verified: true, size: stat.size, directory: stat.isDirectory(), modified_at: stat.mtime.toISOString() } }
      if (cap === "terminal.run_scoped") return await this.run(args, project, request.request_id)
      if (cap.startsWith("git.")) return await this.git(cap, args, project, request.request_id, index)
      if (cap === "project.build" || cap === "project.test") return await this.buildOrTest(cap, args, project, request.request_id, index)
      if (cap === "vscode.open_project") return await this.openVSCode(project)
      throw new RuntimeError("capability_unavailable", "Local development capability is not implemented.")
    } catch (error) { return { status: "failed", verified: false, error_code: error.code || "local_development_error", message: String(error.message || error).slice(0, 300) } }
  }

  async executePlan(request) {
    const args = request.arguments || {}; const plan = args.coding_plan || {}; const deviceId = request.device_id || "local"
    let projectResult
    try { projectResult = { project: this.project(args, deviceId).project, existing: true } } catch (error) {
      if (error.code !== "project_not_found") throw error
      projectResult = this.create({ name: args.project_name || plan.project_name || plan.summary || "CEASER Project", framework: args.framework, language: args.language, task_id: request.task_id }, deviceId)
    }
    const project = projectResult.project; const ref = { project_id: project.project_id }; const events = []
    const emit = (type, metadata = {}) => events.push({ type, task_id: request.task_id, project_id: project.project_id, agent_id: "bolt", device_id: deviceId, ...metadata })
    emit("bolt.planning"); emit(projectResult.existing ? "project.resolved" : "project.created"); emit("bolt.plan_ready")
    const evidence = { project_exists: true, files: [], commands: [], repair_attempts: 0, events }
    const apply = async (candidate) => {
      for (const operation of candidate.file_operations || []) {
        const mapping = { write: "project.write_file", patch: "project.patch_file", mkdir: "project.create_directory", rename: "project.rename", copy: "project.copy", delete: "project.delete" }
        const result = await this.execute({ ...request, capability: mapping[operation.operation], arguments: { ...ref, ...operation } })
        if (result.status !== "completed") return result
        evidence.files.push(operation.path); emit(operation.operation === "delete" ? "file.deleted" : operation.operation === "write" ? "file.created" : "file.updated", { path: operation.path })
      }
      for (const command of candidate.setup_commands || []) {
        const result = await this.execute({ ...request, request_id: `${request.request_id}:setup:${evidence.commands.length}`, capability: "terminal.run_scoped", arguments: { ...ref, ...command } })
        emit("dependencies.started"); evidence.commands.push({ category: "dependencies", status: result.status, exit_code: result.exit_code }); emit(result.status === "completed" ? "dependencies.completed" : "dependencies.failed", { status: result.status })
        if (result.status !== "completed") return result
      }
      return { status: "completed", verified: true }
    }
    let result = await apply(plan); if (result.status !== "completed") return { ...result, project, evidence }
    const verify = async (candidate) => {
      emit("build.started"); const build = await this.execute({ ...request, request_id: `${request.request_id}:build`, capability: "project.build", arguments: { ...ref, argv: candidate.build_commands?.[0]?.argv, timeout_seconds: candidate.build_commands?.[0]?.timeout_seconds } }); emit(build.status === "completed" ? "build.completed" : "build.failed", { status: build.status, duration: build.duration_ms })
      evidence.commands.push({ category: "build", status: build.status, exit_code: build.exit_code })
      let tests = { status: "completed", verified: true, test_status: "no_tests_available" }
      if (build.status === "completed") { emit("test.started"); tests = await this.execute({ ...request, request_id: `${request.request_id}:test`, capability: "project.test", arguments: { ...ref, argv: candidate.test_commands?.[0]?.argv, timeout_seconds: candidate.test_commands?.[0]?.timeout_seconds } }); emit(tests.test_status === "no_tests_available" ? "test.unavailable" : tests.status === "completed" ? "test.completed" : "test.failed", { status: tests.status }) }
      evidence.commands.push({ category: "test", status: tests.status, test_status: tests.test_status, exit_code: tests.exit_code })
      return { build, tests }
    }
    let checked = await verify(plan)
    const repairs = args.repair_plans || []; const maximum = Math.min(Math.max(Number(args.max_repair_attempts || 2), 0), 5)
    while ((checked.build.status !== "completed" || checked.tests.status !== "completed") && evidence.repair_attempts < maximum && evidence.repair_attempts < repairs.length) {
      emit("bolt.repair_started", { attempt: evidence.repair_attempts + 1 }); emit("bolt.repair_plan_ready", { attempt: evidence.repair_attempts + 1 }); result = await apply(repairs[evidence.repair_attempts]); evidence.repair_attempts += 1; emit(result.status === "completed" ? "bolt.repair_applied" : "bolt.repair_failed", { attempt: evidence.repair_attempts })
      if (result.status !== "completed") break
      checked = await verify({ ...plan, ...repairs[evidence.repair_attempts - 1] })
    }
    const verified = checked.build.status === "completed" && checked.tests.status === "completed" && fs.existsSync(project.local_path)
    project.last_bolt_task = request.task_id; project.updated_at = now(); const index = this.loadIndex(); const at = index.projects.findIndex((item) => item.project_id === project.project_id); if (at >= 0) index.projects[at] = project; this.saveIndex(index)
    emit(verified ? "bolt.completed" : "bolt.failed", { status: verified ? "completed" : "failed", changed_file_count: evidence.files.length })
    return { status: verified ? "completed" : "failed", verified, project, evidence, verification: { project_exists: true, build_passed: checked.build.status === "completed", tests_passed: checked.tests.status === "completed", tests_status: checked.tests.test_status } }
  }

  async discoverToolchains() {
    const result = {}
    for (const [name, argv] of Object.entries({ node: ["node", ["--version"]], npm: ["npm", ["--version"]], python: ["python", ["--version"]], pip: ["pip", ["--version"]], git: ["git", ["--version"]], vscode: ["code", ["--version"]] })) {
      result[name] = await new Promise((resolve) => this.execFileImpl(argv[0], argv[1], { windowsHide: true, timeout: 3000 }, (error, stdout, stderr) => resolve(error ? { available: false, code: error.code === "ENOENT" ? `${name}_missing` : "unavailable" } : { available: true, version: String(stdout || stderr).split(/\r?\n/)[0].slice(0, 120) })))
    }
    return { status: "completed", verified: true, toolchains: result }
  }

  async buildOrTest(cap, args, project, requestId, index) {
    let argv = args.argv
    if (!argv) {
      const packagePath = path.join(project.local_path, "package.json")
      if (fs.existsSync(packagePath)) { const pkg = JSON.parse(fs.readFileSync(packagePath, "utf8")); const script = cap === "project.build" ? "build" : "test"; if (pkg.scripts?.[script]) argv = ["npm", "run", script]; else if (cap === "project.test") return { status: "completed", verified: true, test_status: "no_tests_available" } }
      else if (cap === "project.test") return { status: "completed", verified: true, test_status: "no_tests_available" }
      else argv = ["python", "-m", "compileall", "."]
    }
    const result = await this.run({ argv, timeout_seconds: args.timeout_seconds || 300 }, project, requestId)
    const key = cap === "project.build" ? "last_build_status" : "last_test_status"; project[key] = result.status; project.updated_at = now(); this.saveIndex(index)
    return { ...result, [cap === "project.build" ? "build_status" : "test_status"]: result.status }
  }

  async git(cap, args, project, requestId, index) {
    if (cap === "git.set_remote") {
      const remote = String(args.remote_url || "")
      if (!/^https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+(?:\.git)?$/i.test(remote) || /@github\.com/i.test(remote)) throw new RuntimeError("remote_conflict", "Only credential-free GitHub HTTPS remotes are allowed.")
      const current = await this.run({ argv: ["git", "remote", "get-url", "origin"] }, project, `${requestId}:read`)
      const argv = current.status === "completed" ? ["git", "remote", "set-url", "origin", remote] : ["git", "remote", "add", "origin", remote]
      const result = await this.run({ argv }, project, requestId); if (result.status === "completed") project.git_repository = remote; project.updated_at = now(); this.saveIndex(index); return result
    }
    const map = { "git.init": ["init"], "git.status": ["status", "--porcelain=v1"], "git.diff": ["diff", "--no-ext-diff"], "git.add": ["add", ...(args.paths || ["-A"])], "git.commit": ["commit", "-m", String(args.message || "CEASER checkpoint")], "git.log": ["log", "-n", String(Math.min(Number(args.limit || 10), 50)), "--oneline"] }
    const result = await this.run({ argv: ["git", ...map[cap]], timeout_seconds: 120 }, project, requestId)
    if (cap === "git.init" && result.status === "completed") project.git_enabled = true
    if (cap === "git.commit" && result.status === "completed") { const rev = await this.run({ argv: ["git", "rev-parse", "HEAD"] }, project, `${requestId}:revision`); project.last_revision = rev.stdout?.trim().slice(0, 64) || null }
    project.updated_at = now(); this.saveIndex(index); return result
  }

  async openVSCode(project) {
    return await new Promise((resolve) => this.execFileImpl("code", [project.local_path], { windowsHide: true, timeout: 10000 }, (error) => resolve(error ? { status: "failed", verified: false, error_code: error.code === "ENOENT" ? "vscode_missing" : "vscode_launch_failed", message: "VS Code could not be opened." } : { status: "completed", verified: true, local_path: project.local_path })))
  }
}

module.exports = { LocalDevelopmentRuntime, RuntimeError, SECRET_NAMES, LOCAL_DEVELOPMENT_CAPABILITIES }
