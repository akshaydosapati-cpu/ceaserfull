const fs = require("fs")
const path = require("path")
const crypto = require("crypto")

const CAPS = ["browser.start", "browser.navigate", "browser.current_page", "browser.inspect", "browser.find", "browser.click", "browser.type", "browser.select", "browser.check", "browser.uncheck", "browser.scroll", "browser.hover", "browser.wait", "browser.upload", "browser.download", "browser.back", "browser.forward", "browser.reload", "browser.tabs", "browser.open_tab", "browser.close_tab", "browser.switch_tab", "browser.screenshot", "browser.extract", "browser.verify", "browser.cancel"]
const PROTECTED = new Set(["publish", "post", "send", "submit", "purchase", "checkout", "delete", "subscribe", "account_change", "security_change"])
const SENSITIVE = /password|passcode|credit.?card|card.?number|cvv|cvc|security.?code|otp|one.?time|secret|token/i
const INJECTION = /ignore (?:all |previous |ceaser )?instructions|upload (?:your |the )?\.env|send (?:me |the )?(?:api|secret|private) key|reveal (?:password|token|cookie)/i

class BrowserRuntimeError extends Error { constructor(code, message) { super(message); this.code = code } }

class BrowserAutomationRuntime {
  constructor({ BrowserWindow, session, dataDir, downloadsDir, maxSteps = 25, actionTimeout = 15, navigationTimeout = 30 } = {}) {
    this.BrowserWindow = BrowserWindow
    this.session = session
    this.dataDir = path.resolve(dataDir)
    this.downloadsDir = path.resolve(downloadsDir)
    this.maxSteps = Number(maxSteps) || 25
    this.actionTimeout = (Number(actionTimeout) || 15) * 1000
    this.navigationTimeout = (Number(navigationTimeout) || 30) * 1000
    this.windows = new Map(); this.activeSession = null; this.cancelled = new Set(); this.completedWrites = new Map()
    fs.mkdirSync(this.dataDir, { recursive: true }); fs.mkdirSync(this.downloadsDir, { recursive: true })
  }

  available() { return Boolean(this.BrowserWindow && this.session) }
  capabilities() { return this.available() ? CAPS.slice() : [] }
  events(result) { return result?.events || [] }

  safeUrl(value, args = {}) {
    let raw = String(value || "").trim()
    if (!/^[a-z][a-z0-9+.-]*:/i.test(raw)) raw = `https://${raw}`
    let url; try { url = new URL(raw) } catch { throw new BrowserRuntimeError("unsafe_action", "The URL is invalid.") }
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) throw new BrowserRuntimeError("unsafe_action", "Only credential-free HTTP and HTTPS URLs are allowed.")
    if (["localhost", "127.0.0.1", "::1"].includes(url.hostname) && !args.authorized_local_preview) throw new BrowserRuntimeError("unsafe_action", "Local preview access was not authorized for this task.")
    return url.toString()
  }

  async start(request) {
    if (!this.available()) throw new BrowserRuntimeError("browser_not_available", "The managed Chromium runtime is unavailable.")
    const sessionId = String(request.arguments?.browser_session_id || request.task_id || crypto.randomUUID())
    if (this.windows.has(sessionId) && !this.windows.get(sessionId).isDestroyed()) { this.activeSession = sessionId; return this.windows.get(sessionId) }
    const partition = "persist:ceaser-browser"
    const win = new this.BrowserWindow({ show: Boolean(request.arguments?.show), width: 1280, height: 850, webPreferences: { partition, contextIsolation: true, sandbox: true, nodeIntegration: false } })
    this.windows.set(sessionId, win); this.activeSession = sessionId
    win.on("closed", () => this.windows.delete(sessionId))
    return win
  }

  window(args = {}) {
    const id = String(args.browser_session_id || this.activeSession || "")
    const win = this.windows.get(id)
    if (!win || win.isDestroyed()) throw new BrowserRuntimeError("browser_session_failed", "No active browser session exists.")
    return { id, win }
  }

  targetScript(target = {}) {
    const safe = JSON.stringify({ role: target.role, name: target.name, label: target.label, placeholder: target.placeholder, text: target.text, test_id: target.test_id, css: target.css })
    return `(() => { const t=${safe}; const visible=e=>!!(e.offsetWidth||e.offsetHeight||e.getClientRects().length); const all=[...document.querySelectorAll('button,a,input,textarea,select,[role],[data-testid]')].filter(visible); const norm=v=>String(v||'').trim().toLowerCase(); const role=e=>e.getAttribute('role')||(e.tagName==='BUTTON'?'button':e.tagName==='A'?'link':['INPUT','TEXTAREA','SELECT'].includes(e.tagName)?'textbox':''); const name=e=>e.getAttribute('aria-label')||e.labels?.[0]?.innerText||e.placeholder||e.innerText||e.value||''; let m=all.filter(e=>(!t.role||norm(role(e))===norm(t.role))&&(!t.name||norm(name(e)).includes(norm(t.name)))&&(!t.label||norm(name(e)).includes(norm(t.label)))&&(!t.placeholder||norm(e.placeholder).includes(norm(t.placeholder)))&&(!t.text||norm(e.innerText).includes(norm(t.text)))&&(!t.test_id||e.dataset.testid===t.test_id)); if(!m.length&&t.css){try{m=[...document.querySelectorAll(t.css)].filter(visible)}catch{}} return m.length===1?m[0]:{__ceaser_error:m.length?'element_ambiguous':'element_not_found',count:m.length}; })()`
  }

  async locate(win, target) {
    const result = await win.webContents.executeJavaScript(this.targetScript(target), true)
    if (result?.__ceaser_error) throw new BrowserRuntimeError(result.__ceaser_error, result.__ceaser_error === "element_ambiguous" ? "More than one element matched." : "The page element was not found.")
    return result
  }

  async inspect(win) {
    const data = await win.webContents.executeJavaScript(`(() => { const compact=s=>String(s||'').replace(/\s+/g,' ').trim(); const clean=s=>compact(s).slice(0,300); const visible=e=>!!(e.offsetWidth||e.offsetHeight||e.getClientRects().length); const pick=(sel,n)=>[...document.querySelectorAll(sel)].filter(visible).slice(0,n).map(e=>({tag:e.tagName.toLowerCase(),role:e.getAttribute('role'),name:clean(e.getAttribute('aria-label')||e.labels?.[0]?.innerText||e.placeholder||e.innerText),type:e.type||null})); return {url:location.href,title:clean(document.title),headings:pick('h1,h2,h3',30),links:pick('a',50),buttons:pick('button,[role=button]',50),fields:pick('input,textarea,select',50),text:compact(document.body?.innerText).slice(0,12000)} })()`, true)
    if (INJECTION.test(data.text || "")) data.security_warning = "prompt_injection_detected"
    return data
  }

  protectedAction(args) { return PROTECTED.has(String(args.action_type || "").toLowerCase()) || Boolean(args.external_write) }
  identity(request, args) { return `${request.task_id}|${args.action_type || request.capability}|${new URL(args.url || args.current_url || "https://local.invalid").hostname}|${args.target?.name || args.target?.text || ""}|${args.asset_fingerprint || ""}` }
  async navigate(win, url) {
    let timer
    try {
      return await Promise.race([
        win.loadURL(url),
        new Promise((_, reject) => { timer = setTimeout(() => reject(new BrowserRuntimeError("navigation_timeout", "The page did not load before the navigation timeout.")), this.navigationTimeout) }),
      ])
    } finally { clearTimeout(timer) }
  }

  async execute(request) {
    const args = request.arguments || {}; const events = []; const emit=(type, extra={})=>events.push({ type, task_id: request.task_id, session_id: args.browser_session_id || this.activeSession, status: extra.status, domain: extra.domain, action: extra.action, duration: extra.duration, category: extra.category })
    try {
      if (this.cancelled.has(request.task_id)) throw new BrowserRuntimeError("cancelled", "Browser task was cancelled.")
      if (request.capability === "browser.cancel") { this.cancelled.add(request.task_id); emit("browser.cancelled", {status:"cancelled"}); return { status:"cancelled", verified:true, events } }
      const win = await this.start(request); const sessionId = this.activeSession; if (!args.browser_session_id) args.browser_session_id = sessionId
      if (!args.step || Number(args.step) === 1) emit("browser.session_started", {status:"completed"})
      if (Number(args.step || 1) > this.maxSteps) throw new BrowserRuntimeError("verification_failed", "Browser task exceeded its safe step limit.")
      if (this.protectedAction(args) && request.confirmation_requirement !== "already_confirmed") { emit("browser.waiting_for_confirmation", {status:"waiting"}); return { status:"failed", verified:true, error_code:"confirmation_required", message:"Confirm the protected browser action before it runs.", browser_session_id:sessionId, events } }
      const key = this.protectedAction(args) ? this.identity(request,args) : null
      if (key && this.completedWrites.has(key)) return { ...this.completedWrites.get(key), duplicate_prevented:true, events:[...events, {type:"browser.completed",status:"completed"}] }
      let output = {}
      if (request.capability === "browser.start") output={browser_session_id:sessionId}
      else if (["browser.navigate","browser.open_tab"].includes(request.capability)) { const url=this.safeUrl(args.url,args); emit("browser.navigating",{domain:new URL(url).hostname}); if(request.capability==="browser.open_tab") { args.browser_session_id=crypto.randomUUID(); return this.execute({...request,capability:"browser.navigate",arguments:args}) } await this.navigate(win,url); output={url:win.webContents.getURL(),title:win.webContents.getTitle()}; emit("browser.page_loaded",{domain:new URL(output.url).hostname,status:"completed"}) }
      else if (request.capability === "browser.current_page") output={url:win.webContents.getURL(),title:win.webContents.getTitle(),browser_session_id:sessionId}
      else if (["browser.inspect","browser.extract","browser.find"].includes(request.capability)) { emit("browser.inspecting"); output=await this.inspect(win); if(args.query) output.matches=(output.text.match(new RegExp(String(args.query).replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'gi'))||[]).length }
      else if (request.capability === "browser.click") { emit("browser.action_started",{action:"click"}); await this.locate(win,args.target); await win.webContents.executeJavaScript(`${this.targetScript(args.target)}.click()`,true); output={clicked:true}; emit("browser.clicked",{status:"completed"}); if(this.protectedAction(args)){emit("browser.verifying");await new Promise(r=>setTimeout(r,Math.min(Number(args.verification_wait_ms||500),3000)));const page=await this.inspect(win);const rule=args.verification||{};const verified=Boolean((rule.url_contains&&page.url.includes(rule.url_contains))||(rule.text_contains&&page.text.toLowerCase().includes(String(rule.text_contains).toLowerCase())));if(!verified)throw new BrowserRuntimeError("verification_failed","The external browser action could not be verified.");output={...output,verified:true,url:page.url};emit("social.publish_verified",{status:"completed"})} }
      else if (request.capability === "browser.type") { if(SENSITIVE.test(JSON.stringify(args.target||{}))) { emit("browser.waiting_for_user",{status:"waiting"}); throw new BrowserRuntimeError("authentication_required","Complete sensitive authentication manually.") } const value=String(args.value||"").slice(0,10000); await this.locate(win,args.target); await win.webContents.executeJavaScript(`(()=>{const e=${this.targetScript(args.target)};e.focus();e.value=${JSON.stringify(value)};e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));return true})()`,true); output={typed:true,character_count:value.length}; emit("browser.typed",{status:"completed"}) }
      else if (["browser.select","browser.check","browser.uncheck"].includes(request.capability)) { await this.locate(win,args.target); const mode=request.capability; await win.webContents.executeJavaScript(`(()=>{const e=${this.targetScript(args.target)}; if(${JSON.stringify(mode)}==='browser.select')e.value=${JSON.stringify(String(args.value||""))};else e.checked=${mode==='browser.check'};e.dispatchEvent(new Event('change',{bubbles:true}));return true})()`,true); output={changed:true} }
      else if (request.capability === "browser.scroll") { await win.webContents.executeJavaScript(`window.scrollBy({top:${Math.max(-5000,Math.min(5000,Number(args.y||600)))},behavior:'smooth'})`,true); output={scrolled:true} }
      else if (request.capability === "browser.hover") { await this.locate(win,args.target); await win.webContents.executeJavaScript(`(()=>{const e=${this.targetScript(args.target)};e.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));return true})()`,true); output={hovered:true} }
      else if (request.capability === "browser.wait") { await new Promise(r=>setTimeout(r,Math.min(Number(args.milliseconds||1000),this.actionTimeout))); output={waited:true} }
      else if (request.capability === "browser.upload") { const file=path.resolve(String(args.file_path||"")); const roots=(args.authorized_roots||[]).map(p=>path.resolve(String(p))); if(!fs.existsSync(file)||!roots.some(root=>file===root||file.startsWith(`${root}${path.sep}`))) throw new BrowserRuntimeError("upload_failed","The file is outside authorized local context."); if(fs.statSync(file).size>104857600) throw new BrowserRuntimeError("upload_failed","The file exceeds the upload limit."); const selector=String(args.target?.css||""); if(!selector||!/^(?:input)?(?:\[[^\]]+\]|[#.][A-Za-z0-9_-]+)+$/.test(selector)) throw new BrowserRuntimeError("upload_failed","A controlled file-input selector is required."); emit("browser.upload_started",{status:"running"}); win.webContents.debugger.attach("1.3"); try { const root=await win.webContents.debugger.sendCommand("DOM.getDocument",{depth:1}); const found=await win.webContents.debugger.sendCommand("DOM.querySelector",{nodeId:root.root.nodeId,selector}); if(!found.nodeId)throw new BrowserRuntimeError("element_not_found","The file input was not found."); await win.webContents.debugger.sendCommand("DOM.setFileInputFiles",{files:[file],nodeId:found.nodeId}) } finally { try{win.webContents.debugger.detach()}catch{} } output={uploaded:true,filename:path.basename(file),size:fs.statSync(file).size}; emit("browser.upload_completed",{status:"completed"}) }
      else if (request.capability === "browser.screenshot") { const image=await win.webContents.capturePage(); const file=path.join(this.dataDir,`browser-${Date.now()}.png`); fs.writeFileSync(file,image.toPNG()); output={path:file,size:fs.statSync(file).size} }
      else if (request.capability === "browser.back") { if(win.webContents.canGoBack()) win.webContents.goBack(); output={url:win.webContents.getURL()} }
      else if (request.capability === "browser.forward") { if(win.webContents.canGoForward()) win.webContents.goForward(); output={url:win.webContents.getURL()} }
      else if (request.capability === "browser.reload") { win.webContents.reload(); output={reloaded:true} }
      else if (request.capability === "browser.tabs") output={tabs:[...this.windows].filter(([,w])=>!w.isDestroyed()).map(([id,w])=>({id,url:w.webContents.getURL(),title:w.webContents.getTitle(),active:id===this.activeSession}))}
      else if (request.capability === "browser.close_tab") { win.close(); output={closed:true} }
      else if (request.capability === "browser.switch_tab") { const targetId=String(args.tab_id || args.browser_session_id || ""); const target=this.windows.get(targetId); if(!target || target.isDestroyed()) throw this.failure("target_not_found","That browser tab is not available."); this.activeSession=targetId; target.show(); target.focus(); output={id:targetId,url:target.webContents.getURL(),title:target.webContents.getTitle(),active:true} }
      else if (request.capability === "browser.verify") { emit("browser.verifying"); const page=await this.inspect(win); const ok=(!args.url_contains||page.url.includes(args.url_contains))&&(!args.text_contains||page.text.toLowerCase().includes(String(args.text_contains).toLowerCase())); if(!ok) throw new BrowserRuntimeError("verification_failed","The requested browser goal could not be verified."); output={verified:true,url:page.url,title:page.title} }
      else if (request.capability === "browser.download") { const url=this.safeUrl(args.url,args); emit("browser.download_started",{domain:new URL(url).hostname,status:"running"}); output=await new Promise((resolve,reject)=>{ const ses=win.webContents.session; const timer=setTimeout(()=>reject(new BrowserRuntimeError("download_failed","The download timed out.")),this.navigationTimeout); ses.once("will-download",(_event,item)=>{ const safeName=path.basename(item.getFilename()).replace(/[^A-Za-z0-9._ -]/g,"_"); let target=path.join(this.downloadsDir,safeName); if(fs.existsSync(target))target=path.join(this.downloadsDir,`${path.parse(safeName).name}-${Date.now()}${path.extname(safeName)}`); item.setSavePath(target); item.once("done",(_e,state)=>{clearTimeout(timer); if(state!=="completed"||!fs.existsSync(target)||fs.statSync(target).size<=0)return reject(new BrowserRuntimeError("download_failed","The downloaded file could not be verified.")); resolve({filename:path.basename(target),path:target,size:fs.statSync(target).size,source_domain:new URL(url).hostname})}) }); win.webContents.downloadURL(url) }); emit("browser.download_completed",{status:"completed",domain:output.source_domain}) }
      else throw new BrowserRuntimeError("unsafe_action","Unsupported browser capability.")
      const result={status:"completed",verified:true,browser_session_id:sessionId,output,events}; if(key)this.completedWrites.set(key,result); emit("browser.completed",{status:"completed"}); return result
    } catch(error) { const code=error.code||"unknown"; emit(code==="cancelled"?"browser.cancelled":"browser.failed",{status:"failed",category:code}); return {status:code==="cancelled"?"cancelled":"failed",verified:false,error_code:code,message:String(error.message||error).slice(0,300),events} }
  }
}

module.exports={BrowserAutomationRuntime,BrowserRuntimeError,CAPS}
