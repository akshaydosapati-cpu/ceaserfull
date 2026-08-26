import { cp, mkdir, readFile, rm, writeFile } from "node:fs/promises"
import path from "node:path"

const root = process.cwd()
const output = path.join(root, "public")
const launchDate = new Date("2026-08-21T14:15:00+05:30")
const isLaunched = Date.now() >= launchDate.getTime() || process.env.NEXT_PUBLIC_CEASER_LAUNCHED === "true"

await rm(output, { recursive: true, force: true })
await mkdir(path.join(output, "console"), { recursive: true })
const sourceHtml = await readFile(path.join(root, "index.html"), "utf8")
await writeFile(path.join(output, "index.html"), sourceHtml.replaceAll("__CEASER_LAUNCHED__", isLaunched ? "true" : "false"))
for (const file of ["style.css", "animations.js", "privacy.html", "terms.html", "security.html", "launching-soon.html", "favicon.png", "ceaser-wordmark.png", "ceaser-logo-full.png", "sitemap.xml", "robots.txt"]) {
  await cp(path.join(root, file), path.join(output, file))
}
for (const file of ["logo.png", "logo-light.png", "app-icon.png", "app-icon-light.png"]) {
  await cp(path.join(root, "console", "public", file), path.join(output, file))
}
await cp(path.join(root, "assets"), path.join(output, "assets"), {
  recursive: true,
})
const configJs = await readFile(path.join(root, "config.js"), "utf8")
await writeFile(path.join(output, "config.js"), configJs.replaceAll("__CEASER_LAUNCHED__", isLaunched ? "true" : "false"))

await cp(path.join(root, "console", "out"), path.join(output, "console"), {
  recursive: true,
})

if (!isLaunched) {
  const protectedRoutes = [
    "app",
    "dashboard",
    "chat",
    "projects",
    "files",
    "memory",
    "agents",
    "settings",
    "admin",
    "developer",
    "internal",
    "downloads",
  ]
  for (const route of protectedRoutes) {
    await mkdir(path.join(output, route), { recursive: true })
    await writeFile(path.join(output, route, "index.html"), soonPage(route))
  }
}

if (isLaunched) {
  await mkdir(path.join(output, "downloads"), { recursive: true })
  await writeFile(path.join(output, "downloads", "index.html"), downloadPage())
}

console.log(isLaunched ? "Built landing page and CEASER console." : "Built launch landing page with CEASER console enabled.")

function soonPage(label) {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CEASER is launching soon</title><style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#050712;color:#f8fafc;font-family:Inter,system-ui,sans-serif}.card{width:min(560px,calc(100% - 32px));border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.06);border-radius:28px;padding:34px}a{color:#93c5fd}.eyebrow{color:#c4b5fd;text-transform:uppercase;letter-spacing:.18em;font-size:12px;font-weight:800}h1{font-size:42px;margin:12px 0}.muted{color:#a8b3cf;line-height:1.7}.btn{display:inline-flex;margin-top:20px;padding:12px 18px;border-radius:999px;background:#8b5cf6;color:white;text-decoration:none;font-weight:700}</style></head><body><main class="card"><div class="eyebrow">${label} gated</div><h1>CEASER launches on 21 August 2026 at 12:00 PM IST.</h1><p class="muted">This product surface is private until public launch. Join the launch list on the homepage for updates.</p><a class="btn" href="/">Back to homepage</a></main></body></html>`
}

function downloadPage() {
  const installerUrl = "https://media.githubusercontent.com/media/akshaydosapati-cpu/Ceaser_frontend_production/main/assets/desktop/CEASER-Desktop-Setup.exe"
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Download CEASER Desktop</title><style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#050712;color:#f8fafc;font-family:Inter,system-ui,sans-serif}.card{width:min(600px,calc(100% - 32px));border:1px solid rgba(139,92,246,.35);background:rgba(255,255,255,.06);border-radius:28px;padding:34px}.eyebrow{color:#c4b5fd;text-transform:uppercase;letter-spacing:.18em;font-size:12px;font-weight:800}h1{font-size:42px;margin:12px 0}.muted{color:#a8b3cf;line-height:1.7}.btn{display:inline-flex;margin-top:20px;padding:12px 18px;border-radius:999px;background:#8b5cf6;color:white;text-decoration:none;font-weight:700}</style></head><body><main class="card"><div class="eyebrow">CEASER Desktop</div><h1>Download the latest Windows companion</h1><p class="muted">Install CEASER Desktop to use voice commands and local computer controls.</p><a class="btn" href="${installerUrl}" download="CEASER-Desktop-Setup.exe">Download for Windows</a><p class="muted">Version 0.1.1 · Windows 10/11</p></main></body></html>`
}
