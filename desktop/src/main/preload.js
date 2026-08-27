const { contextBridge, ipcRenderer, webUtils } = require("electron")

contextBridge.exposeInMainWorld("ceaserDesktop", {
  classify: (payload) => ipcRenderer.invoke("ceaser:classify", payload),
  execute: (payload) => ipcRenderer.invoke("ceaser:execute", payload),
  runAgent: (payload) => ipcRenderer.invoke("ceaser:run-agent", payload),
  pickMedia: () => ipcRenderer.invoke("ceaser:pick-media"),
  registerFileContext: (path) => ipcRenderer.invoke("ceaser:register-file-context", { path }),
  createDocument: (payload) => ipcRenderer.invoke("ceaser:create-document", payload),
  answerQuestion: (payload) => ipcRenderer.invoke("ceaser:answer-question", payload),
  identity: (payload) => ipcRenderer.invoke("ceaser:identity", payload),
  cancelTask: (payload) => ipcRenderer.invoke("ceaser:cancel-task", payload),
  getPermissions: () => ipcRenderer.invoke("ceaser:permissions:get"),
  setPermission: (key, value) => ipcRenderer.invoke("ceaser:permissions:set", { key, value }),
  getContext: () => ipcRenderer.invoke("ceaser:context"),
  getAuthStatus: () => ipcRenderer.invoke("ceaser:auth-status"),
  openAuth: () => ipcRenderer.invoke("ceaser:open-auth"),
  voiceCompose: (payload) => ipcRenderer.invoke("ceaser:voice-compose", payload),
  openUrl: (url) => ipcRenderer.invoke("ceaser:open-url", url),
  copyText: (text) => ipcRenderer.invoke("ceaser:copy-text", text),
  pythonVoiceCommand: (payload) => ipcRenderer.invoke("ceaser:python-voice-command", payload),
  appAction: (payload) => ipcRenderer.invoke("ceaser:app-action", payload),
  pythonVoiceStatus: () => ipcRenderer.invoke("ceaser:python-voice-status"),
  getRuntimeLogs: () => ipcRenderer.invoke("ceaser:runtime-logs"),
  openLogsFolder: () => ipcRenderer.invoke("ceaser:open-logs-folder"),
  filePath: (file) => webUtils.getPathForFile(file),
  duckMedia: (payload) => ipcRenderer.invoke("ceaser:media-duck", payload),
  restoreMedia: () => ipcRenderer.invoke("ceaser:media-restore"),
  openFullApp: () => ipcRenderer.invoke("ceaser:open-full-app"),
  hideOverlay: (options) => ipcRenderer.invoke("ceaser:hide-overlay", options),
  showOverlay: (options) => ipcRenderer.invoke("ceaser:show-overlay", options),
  setMode: (mode) => ipcRenderer.invoke("ceaser:set-mode", mode),
  fitContent: (size) => ipcRenderer.invoke("ceaser:fit-content", size),
  setOverlayInteractive: (interactive) => ipcRenderer.invoke("ceaser:overlay-interactive", Boolean(interactive)),
  onStartListening: (callback) => {
    const handler = (_event, payload) => callback(payload)
    ipcRenderer.on("ceaser:start-listening", handler)
    return () => ipcRenderer.removeListener("ceaser:start-listening", handler)
  },
  onStopListening: (callback) => {
    const handler = (_event, payload) => callback(payload)
    ipcRenderer.on("ceaser:stop-listening", handler)
    return () => ipcRenderer.removeListener("ceaser:stop-listening", handler)
  },
  onPythonVoiceStatus: (callback) => {
    const handler = (_event, payload) => callback(payload)
    ipcRenderer.on("ceaser:python-voice-status", handler)
    return () => ipcRenderer.removeListener("ceaser:python-voice-status", handler)
  },
  onPythonReady: (callback) => {
    const handler = (_event, payload) => callback(payload)
    ipcRenderer.on("ceaser:python-ready", handler)
    return () => ipcRenderer.removeListener("ceaser:python-ready", handler)
  },
  onPythonEvent: (callback) => {
    const handler = (_event, payload) => callback(payload)
    ipcRenderer.on("ceaser:python-event", handler)
    return () => ipcRenderer.removeListener("ceaser:python-event", handler)
  },
  onAuthLinked: (callback) => {
    const handler = (_event, payload) => callback(payload)
    ipcRenderer.on("ceaser:auth-linked", handler)
    return () => ipcRenderer.removeListener("ceaser:auth-linked", handler)
  },
  onSystemPower: (callback) => {
    const handler = (_event, payload) => callback(payload)
    ipcRenderer.on("ceaser:system-power", handler)
    return () => ipcRenderer.removeListener("ceaser:system-power", handler)
  },
  onOverlayVisibility: (callback) => {
    const handler = (_event, payload) => callback(payload)
    ipcRenderer.on("ceaser:overlay-visibility", handler)
    return () => ipcRenderer.removeListener("ceaser:overlay-visibility", handler)
  },
  onRuntimeLog: (callback) => {
    const handler = (_event, payload) => callback(payload)
    ipcRenderer.on("ceaser:runtime-log", handler)
    return () => ipcRenderer.removeListener("ceaser:runtime-log", handler)
  },
  windowMinimize: () => ipcRenderer.invoke("ceaser:window-minimize"),
  windowMaximize: () => ipcRenderer.invoke("ceaser:window-maximize"),
  windowClose: () => ipcRenderer.invoke("ceaser:window-close"),
  windowIsMaximized: () => ipcRenderer.invoke("ceaser:window-is-maximized"),
})

