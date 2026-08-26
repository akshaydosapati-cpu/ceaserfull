const { appAliases, blockedIntent, ceaserRoutes, exposePatternCount, folders, isDangerousCommand, websiteAliases } = require("./actionRegistry")
const { permissionFor } = require("./actionPermissions")
const { requiresConfirmation } = require("./actionConfirmations")
const { INTENT_TYPES, RISK } = require("./actionSchemas")

class ActionRouter {
  route(command) {
    const raw = String(command || "").trim()
    const normalized = raw.toLowerCase().replace(/\s+/g, " ")
    if (!raw) return this.chat(raw)
    if (isDangerousCommand(raw)) return blockedIntent(raw)
    const demoSafe = this.demoSafeIntent(raw, normalized)
    if (demoSafe) return demoSafe
    const identity = this.identityIntent(raw, normalized)
    if (identity) return identity

    const live = this.liveIntent(raw, normalized)
    if (live) return live
    const music = this.musicIntent(raw, normalized)
    if (music) return music
    const context = this.contextIntent(raw, normalized)
    if (context) return context
    const url = this.urlIntent(raw, normalized)
    if (url) return url
    const ceaser = this.ceaserIntent(normalized)
    if (ceaser) return ceaser
    const system = this.systemIntent(normalized)
    if (system) return system
    const search = this.searchIntent(raw, normalized)
    if (search) return search
    const clipboard = this.clipboardIntent(raw, normalized)
    if (clipboard) return clipboard
    const vision = this.visionIntent(raw, normalized)
    if (vision) return vision
    const screenshot = this.desktop("take_screenshot", { save: true }, ["Checking screenshot permission", "Capturing screen", "Saving screenshot"], "Screenshot", "Save a screenshot.", RISK.MEDIUM)
    if (/\b(screenshot|screen shot)\b/.test(normalized)) return screenshot
    const folder = this.folderIntent(raw, normalized)
    if (folder) return folder
    const file = this.fileIntent(raw, normalized)
    if (file) return file
    const documentCreation = this.documentCreationIntent(raw, normalized)
    if (documentCreation) return documentCreation
    const app = this.appIntent(raw, normalized)
    if (app) return app
    const agent = this.agentIntent(raw, normalized)
    if (agent) return agent
    return this.chat(raw)
  }

  liveIntent(raw, normalized) {
    const weatherMatch = normalized.match(/\b(?:weather|temperature|rain|raining|forecast)\b(?:\s+(?:in|at|for)\s+(.+))?/)
    if (weatherMatch) {
      const location = cleanLocation(weatherMatch[1]) || "Hyderabad, IN"
      return this.desktop("get_weather", { location }, ["Checking weather", "Preparing forecast"], "Weather", location, RISK.LOW, "expanded")
    }
    if (/\b(news|headlines|latest updates|top stories)\b/.test(normalized)) {
      return this.desktop("get_news", { query: raw }, ["Reading headlines", "Preparing briefing"], "News Brief", raw, RISK.LOW, "expanded")
    }
    const timerMatch = normalized.match(/\b(?:set|start)\s+(?:a\s+)?timer\s+(?:for\s+)?(\d+)\s*(minute|minutes|min|second|seconds|sec|hour|hours)?/)
    if (timerMatch) {
      return this.desktop("set_timer", { amount: Number(timerMatch[1]), unit: timerMatch[2] || "minutes" }, ["Setting timer", "Starting countdown"], "Timer", raw, RISK.LOW, "expanded")
    }
    if (/\b(stock|share price|market price)\b/.test(normalized)) {
      return this.desktop("stock_price", { query: raw }, ["Checking market data", "Preparing snapshot"], "Stocks", raw, RISK.LOW, "expanded")
    }
    if (/\b(my tasks|show tasks|show my tasks|to do|todo|to-do)\b/.test(normalized)) {
      return this.desktop("get_tasks", {}, ["Reading task context", "Preparing task list"], "Tasks", raw, RISK.LOW, "expanded")
    }
    return null
  }

  musicIntent(raw, normalized) {
    if (/\b(play\s+)?(next|skip)\b.*\b(song|track|music|video)\b/.test(normalized)) {
      return this.desktop("media_key", { key: "next" }, ["Sending media key"], "Playback Control", "Next track")
    }
    if (/\b(play\s+)?(previous|prev|back)\b.*\b(song|track|music|video)\b/.test(normalized)) {
      return this.desktop("media_key", { key: "previous" }, ["Sending media key"], "Playback Control", "Previous track")
    }
    if (/\b(stop)\b.*\b(music|song|video|playback)\b/.test(normalized) || /^stop\s*(music|song|video|playback)?$/.test(normalized)) {
      return this.desktop("media_key", { key: "stop" }, ["Sending media key"], "Playback Control", "Stop")
    }
    if (/\b(pause|resume|continue|toggle)\b.*\b(music|song|video|playback)\b/.test(normalized) || /^(?:pause|resume|continue)\s*$/.test(normalized)) {
      return this.desktop("media_key", { key: "playpause" }, ["Sending media key"], "Playback Control", "Play/pause")
    }
    if (/\b(forward|seek forward)\b/.test(normalized)) {
      return this.desktop("media_key", { key: "forward" }, ["Sending seek key"], "Playback Control", "Forward")
    }
    if (/\b(rewind|seek back|back 10 seconds|go back)\b/.test(normalized)) {
      return this.desktop("media_key", { key: "rewind" }, ["Sending seek key"], "Playback Control", "Rewind")
    }
    const directLink = raw.match(/\bplay\s+(https?:\/\/\S+)/i)
    if (directLink?.[1] && /\b(youtube\.com|youtu\.be)\b/i.test(directLink[1])) {
      return this.desktop("play_youtube", { query: directLink[1].trim(), url: directLink[1].trim() }, ["Opening YouTube", "Starting video"], "Play on YouTube", directLink[1].trim(), RISK.LOW, "expanded")
    }
    const playYoutube = normalized.match(/^(?:please\s+)?play\s+(.+?)(?:\s+(?:song|music|video))?(?:\s+(?:on|in)\s+youtube)?$/)
    if (playYoutube && playYoutube[1] && !/\b(playwright|playbook)\b/.test(playYoutube[1])) {
      return this.desktop("play_youtube", { query: playYoutube[1].trim() }, ["Opening YouTube", "Starting first result"], "Play on YouTube", playYoutube[1].trim(), RISK.LOW, "expanded")
    }
    if (/\b(show|what'?s|what is)\b.*\b(now playing|playing now|current song)\b/.test(normalized)) {
      return this.desktop("now_playing", {}, ["Checking player"], "Now Playing", "Direct now-playing detection needs browser or music-app integration.")
    }
    return null
  }

  visionIntent(raw, normalized) {
    if (/\b(screen info|screen information|display info|display information)\b/.test(normalized)) {
      return this.desktop("screen_info", {}, ["Reading displays", "Checking cursor"], "Screen Info", raw, RISK.LOW, "expanded")
    }
    if (/\b(read|extract|copy|scan)\b.*\b(text|ocr)\b.*\b(screen|screenshot|image|window)\b|\b(read|scan|ocr)\s+(?:my\s+)?screen\b/.test(normalized)) {
      return this.desktop("read_screen_text", {}, ["Capturing screen", "Running OCR", "Preparing text"], "Screen OCR", raw, RISK.MEDIUM, "expanded")
    }
    if (/\b(analyze|analyse|explain|understand|describe)\b.*\b(screen|screenshot|image|window|what is on my screen)\b|\bwhat(?:'s| is)\s+on\s+(?:my\s+)?screen\b/.test(normalized)) {
      return this.desktop("analyze_screen", {}, ["Capturing screen", "Reading visible text", "Preparing analysis"], "Screen Analysis", raw, RISK.MEDIUM, "expanded")
    }
    return null
  }

  contextIntent(raw, normalized) {
    if (/\b(open|start)\s+(?:my\s+)?morning workspace\b/.test(normalized)) {
      return this.desktop("open_morning_workspace", {}, ["Reading habits", "Opening preferred workspace"], "Morning Workspace", "Learned from your usage")
    }
    if (/\b(daily brief|today'?s brief|good morning|morning brief)\b/.test(normalized)) {
      return this.desktop("daily_brief", {}, ["Reading calendar context", "Checking behavior memory", "Preparing brief"], "Daily Brief", "Agenda, patterns, and suggestions", RISK.LOW, "expanded")
    }
    if (/\b(calendar|schedule|meetings|events)\b/.test(normalized)) {
      const range = /\btomorrow\b/.test(normalized) ? "tomorrow" : /\btoday\b/.test(normalized) ? "today" : "upcoming"
      return this.desktop("get_calendar_events", { range }, ["Reading Google Calendar", "Finding events", "Preparing schedule"], "Calendar", raw, RISK.LOW, "expanded")
    }
    if (/\b(gmail|email|inbox)\b/.test(normalized)) {
      return this.agent("Friday", "Checking Inbox", raw, ["Reading connected context", "Finding important items", "Preparing summary"], ["Integration context", "Summary preparing"])
    }
    if (/\b(what did you learn|what have you learned|show suggestions|suggestions|my habits|my patterns|behavior memory)\b/.test(normalized)) {
      return this.desktop("behavior_summary", {}, ["Reading behavior memory", "Preparing suggestions"], "Personal Intelligence", "Habits, preferences, and learned patterns")
    }
    if (/\b(close|quit|exit)\s+(?:the\s+)?(?:current\s+)?window\b/.test(normalized)) return this.desktop("close_window", { target: targetWindow(raw) }, ["Finding window", "Closing window"], "Close Window", targetWindow(raw) || "current window", RISK.MEDIUM)
    if (/\bminimi[sz]e\b/.test(normalized)) return this.desktop("minimize_window", { target: targetWindow(raw) }, ["Finding window", "Minimizing window"], "Minimize Window", targetWindow(raw) || "current window")
    if (/\bmaximi[sz]e\b/.test(normalized)) return this.desktop("maximize_window", { target: targetWindow(raw) }, ["Finding window", "Maximizing window"], "Maximize Window", targetWindow(raw) || "current window")
    if (/\brestore\b.*\bwindow\b/.test(normalized)) return this.desktop("restore_window", { target: targetWindow(raw) }, ["Finding window", "Restoring window"], "Restore Window", targetWindow(raw) || "current window")
    if (/\b(bring|focus|switch to)\b.+\b(front|window)\b/.test(normalized)) return this.desktop("focus_window", { target: targetWindow(raw) }, ["Finding window", "Bringing to front"], "Focus Window", targetWindow(raw) || "matching window")
    if (/\b(what app|current app|active app|what window|current window|active window)\b/.test(normalized)) {
      return this.desktop("get_active_window", {}, ["Reading active window", "Preparing context"], "Current Desktop Context", "Active app and window")
    }
    if (/\b(show|list|what are)\b.*\b(open windows|windows open|running windows)\b/.test(normalized)) {
      return this.desktop("list_open_windows", {}, ["Reading open windows", "Preparing list"], "Open Windows", "Current visible windows")
    }
    if (/\b(what did i work on|worked on today|today activity|desktop session|session summary)\b/.test(normalized)) {
      return this.desktop("session_summary", {}, ["Reading session memory", "Summarizing today"], "Today's Desktop Session", "Recent CEASER-tracked activity")
    }
    if (/\b(recent activity|recent actions|what did ceaser do)\b/.test(normalized)) {
      return this.desktop("recent_activity", {}, ["Reading recent activity", "Preparing timeline"], "Recent Activity", "Latest desktop events")
    }
    return null
  }

  urlIntent(raw, normalized) {
    const match = normalized.match(/\b(?:open|go to|launch|visit)\s+((?:https?:\/\/)?(?:www\.)?[a-z0-9.-]+\.[a-z]{2,}(?:\/\S*)?)/i)
    if (!match) return null
    return this.desktop("open_url", { url: normalizeUrl(match[1]) }, ["Validating URL", "Opening browser"], "Open Website", match[1])
  }

  searchIntent(raw, normalized) {
    const siteMatch = normalized.match(/\b(?:open|go to|visit)\s+([a-z0-9 ]+)$/)
    if (siteMatch) {
      if (/\b(app|application|desktop app)\b/.test(siteMatch[1])) return null
      const key = Object.keys(websiteAliases).find((alias) => siteMatch[1].trim() === alias || siteMatch[1].includes(alias))
      if (key) return this.desktop("open_url", { url: websiteAliases[key] }, ["Resolving website", `Opening ${key}`], `Open ${title(key)}`, websiteAliases[key])
    }
    const direct = normalized.match(/\bsearch\s+(google|youtube|github|linkedin|wikipedia)\s+(?:for\s+)?(.+)/)
    if (direct) return this.desktop("web_search", { provider: direct[1], query: direct[2] }, ["Preparing search", `Opening ${direct[1]}`], `Search ${title(direct[1])}`, direct[2])
    if (/\b(calendar|schedule|meetings|events|gmail|email|inbox)\b/.test(normalized)) return null
    if (/^(who|what|where|when|why|how|do you know|tell me about|explain|define)\b/.test(normalized)) {
      return this.answer(raw)
    }
    const play = normalized.match(/\b(?:play|search|open)\s+(.+?)\s+(?:on|in)\s+(youtube|spotify|google|github|linkedin|wikipedia)\b/)
    if (play) {
      const isMusic = normalized.startsWith("play ") && ["youtube", "spotify"].includes(play[2])
      return this.desktop("web_search", { provider: play[2], query: play[1], play: normalized.startsWith("play "), display: isMusic ? "music" : "search" }, ["Preparing request", `Opening ${play[2]}`], isMusic ? "Now Playing" : `${title(play[2])} Search`, play[1], RISK.LOW, isMusic ? "expanded" : "compact")
    }
    return null
  }

  ceaserIntent(normalized) {
    if (!normalized.includes("ceaser")) return null
    for (const [route, path] of Object.entries(ceaserRoutes)) {
      if (normalized.includes(route) || (route === "app" && /\b(open|launch)\s+ceaser\b/.test(normalized))) {
        return this.desktop("open_ceaser", { route: path }, ["Opening CEASER"], `Open CEASER ${title(route)}`, "CEASER web app")
      }
    }
    return null
  }

  systemIntent(normalized) {
    if (/\b(time|current time)\b/.test(normalized)) return this.desktop("system_info", { type: "time" }, ["Reading system time"], "Current Time", "")
    if (/\b(?:what(?:'s| is)?|tell me|show|check)\b.*\b(?:date|today'?s date)\b/.test(normalized) || /\b(?:date today|current date)\b/.test(normalized)) return this.desktop("system_info", { type: "date" }, ["Reading system date"], "Current Date", "")
    if (normalized.includes("battery")) return this.desktop("system_info", { type: "battery" }, ["Checking battery"], "Battery Status", "")
    if (normalized.includes("disk space")) return this.desktop("system_info", { type: "disk" }, ["Checking disk space"], "Disk Space", "")
    if (normalized.includes("network")) return this.desktop("system_info", { type: "network" }, ["Checking network"], "Network Status", "")
    if (normalized.includes("wifi") || normalized.includes("wi-fi")) return this.desktop("open_settings", { page: "wifi" }, ["Opening Wi-Fi settings"], "Wi-Fi Settings", "")
    if (normalized.includes("bluetooth")) return this.desktop("open_settings", { page: "bluetooth" }, ["Opening Bluetooth settings"], "Bluetooth Settings", "")
    if (normalized.includes("display settings")) return this.desktop("open_settings", { page: "display" }, ["Opening display settings"], "Display Settings", "")
    if (normalized.includes("sound settings")) return this.desktop("open_settings", { page: "sound" }, ["Opening sound settings"], "Sound Settings", "")
    if (/\block (?:my )?(?:computer|pc|system)\b/.test(normalized)) return this.desktop("lock_computer", {}, ["Waiting for confirmation", "Locking computer"], "Lock Computer", "", RISK.MEDIUM)
    if (/\b(shut down|shutdown|turn off)\s+(?:my\s+)?(?:computer|pc|system)?\b/.test(normalized)) return this.desktop("shutdown_computer", {}, ["Waiting for confirmation", "Requesting shutdown"], "Shutdown Computer", "", RISK.HIGH)
    if (/\b(restart|reboot)\s+(?:my\s+)?(?:computer|pc|system)?\b/.test(normalized)) return this.desktop("restart_computer", {}, ["Waiting for confirmation", "Requesting restart"], "Restart Computer", "", RISK.HIGH)
    if (/\b(sleep|sleep mode)\s+(?:my\s+)?(?:computer|pc|system)?\b/.test(normalized)) return this.desktop("sleep_computer", {}, ["Waiting for confirmation", "Putting computer to sleep"], "Sleep Computer", "", RISK.MEDIUM)
    const setVolume = normalized.match(/\b(?:set\s+)?volume\s+(?:to\s+)?(\d{1,3})\s*%?/)
    if (setVolume) return this.desktop("set_volume", { level: Number(setVolume[1]) }, ["Adjusting volume"], "Volume", `${Math.min(100, Number(setVolume[1]))}%`)
    if (/\b(mute|unmute)\b.*\b(volume|sound|audio)?\b/.test(normalized)) return this.desktop("adjust_volume", { direction: "mute", steps: 1 }, ["Sending volume key"], "Volume", "Mute toggle")
    if (/\b(increase|raise|turn up)\b.*\b(volume|sound|audio)\b/.test(normalized)) return this.desktop("adjust_volume", { direction: "up", steps: 4 }, ["Sending volume keys"], "Volume", "Increase volume")
    if (/\b(decrease|lower|turn down)\b.*\b(volume|sound|audio)\b/.test(normalized)) return this.desktop("adjust_volume", { direction: "down", steps: 4 }, ["Sending volume keys"], "Volume", "Decrease volume")
    return null
  }

  clipboardIntent(raw, normalized) {
    if (!normalized.includes("clipboard")) return null
    if (normalized.includes("clear")) return this.desktop("clear_clipboard", {}, ["Waiting for confirmation", "Clearing clipboard"], "Clear Clipboard", "", RISK.MEDIUM)
    const copyMatch = raw.match(/copy\s+(.+?)\s+to clipboard/i)
    if (copyMatch) return this.desktop("copy_text_to_clipboard", { text: copyMatch[1] }, ["Copying text"], "Copy to Clipboard", copyMatch[1])
    return this.desktop("read_clipboard", {}, ["Checking clipboard permission", "Reading clipboard"], "Read Clipboard", "")
  }

  folderIntent(raw, normalized) {
    const createMatch = raw.match(/create (?:a )?folder (?:called|named)?\s*(.+?)(?:\s+(?:in|on)\s+(downloads|documents|desktop|pictures|videos|music))?$/i)
    if (createMatch) return this.desktop("create_folder", { name: createMatch[1].trim(), base: createMatch[2]?.toLowerCase() || "documents" }, ["Checking file write permission", "Waiting for confirmation", "Creating folder"], "Create Folder", createMatch[1], RISK.MEDIUM)
    for (const [key, terms] of Object.entries(folders)) {
      if (terms.some((term) => normalized.includes(term)) && /\b(open|show|launch)\b/.test(normalized)) {
        return this.desktop("open_folder", { folder: key }, ["Checking app launch permission", `Opening ${title(key)}`], `Open ${title(key)}`, key)
      }
    }
    return null
  }

  fileIntent(raw, normalized) {
    if (/\b(summarize|summarise|explain|read)\b/.test(normalized) && /\b(pdf|document|file)\b/.test(normalized) && /\b(viewing|reading|open|current|screen)\b/.test(normalized)) {
      return this.desktop("summarize_active_pdf", {}, ["Identifying active PDF", "Uploading to CEASER", "Summarizing document"], "Summarize Active PDF", "PDF currently open on desktop", RISK.LOW, "expanded")
    }
    if (/\b(summarize|summarise|explain|generate notes|make notes|mcq|flashcards|read)\b/.test(normalized) && /\b(pdf|document|docx|pptx|xlsx|file|report|notes|image)\b/.test(normalized)) {
      return this.agent("Atlas", "Reading Document", raw, ["Finding document", "Extracting content", "Analyzing content", "Preparing answer"], ["Document context", "Answer preparing"])
    }
    const latestMatch = normalized.match(/\b(open|find|show)\s+(?:my\s+)?(?:latest|most recent|recent)\s+(pdf|document|presentation|deck|image|photo|spreadsheet|excel|text|file)\b/)
    if (latestMatch) return this.desktop(latestMatch[1] === "open" ? "open_file" : "search_file", { query: `latest ${latestMatch[2]}` }, ["Checking recent files", "Resolving latest match"], `${title(latestMatch[1])} Latest ${title(latestMatch[2])}`, latestMatch[2])
    const searchMatch = raw.match(/(?:search|find)\s+(?:file\s+)?(.+)/i)
    if (searchMatch && normalized.includes("file")) return this.desktop("search_file", { query: searchMatch[1].trim() }, ["Checking file read permission", "Searching files"], "Search File", searchMatch[1])
    const naturalFileMatch = raw.match(/\b(?:find|open|show)\s+(?:my\s+)?(.+?\s+(?:pdf|document|presentation|deck|image|photo|spreadsheet|excel|text|file))$/i)
    if (naturalFileMatch) return this.desktop(normalized.startsWith("open ") ? "open_file" : "search_file", { query: naturalFileMatch[1].trim() }, ["Checking file read permission", "Searching files"], "Smart File Search", naturalFileMatch[1])
    const openMatch = raw.match(/open\s+(.+\.(pdf|png|jpg|jpeg|txt|docx?|xlsx?|pptx?))/i)
    if (openMatch) return this.desktop("open_file", { query: openMatch[1].trim() }, ["Checking file read permission", "Finding file", "Opening file"], "Open File", openMatch[1])
    return null
  }

  documentCreationIntent(raw, normalized) {
    const wantsCreate = /\b(create|make|generate|prepare|write|draft)\b/.test(normalized)
    const wantsDocument = /\b(pdf|document|doc|docx|report|proposal|business plan|pitch deck|presentation|ppt|pptx|slides|excel|spreadsheet|xlsx)\b/.test(normalized)
    if (!wantsCreate || !wantsDocument) return null

    let kind = "docx"
    if (/\b(pdf)\b/.test(normalized)) kind = "pdf"
    else if (/\b(pitch deck|presentation|ppt|pptx|slides)\b/.test(normalized)) kind = "pptx"
    else if (/\b(excel|spreadsheet|xlsx|sheet)\b/.test(normalized)) kind = "xlsx"

    let agent = "Bolt"
    if (/\b(business|startup|strategy|pitch|revenue|marketing|gtm)\b/.test(normalized)) agent = "Zeus"
    if (/\b(research|market|competitor|sources)\b/.test(normalized)) agent = "Nova"
    if (/\b(content|linkedin|social|campaign|script)\b/.test(normalized)) agent = "Friday"
    if (/\b(study|notes|exam|mcq|flashcard)\b/.test(normalized)) agent = "Alex"
    if (/\b(technical|architecture|software|api|code)\b/.test(normalized)) agent = "Atlas"

    return this.desktop(
      "create_document",
      { prompt: raw, kind, agent_id: agent.toLowerCase() },
      ["Creating document", "Saving to CEASER Files", "Opening generated file"],
      `Create ${kind.toUpperCase()}`,
      raw,
      RISK.LOW,
      "expanded",
    )
  }

  appIntent(raw, normalized) {
    if (/\b(refresh|rebuild|update|rescan|scan)\s+(apps|applications|app list|application list)\b/.test(normalized)) {
      return this.desktop("refresh_apps", {}, ["Scanning Windows apps", "Updating app index"], "Refresh Apps", "Application index", RISK.LOW, "compact")
    }
    const match = normalized.match(/\b(open|launch|start|focus|switch to|check|close|quit|exit|restart)\s+(.+)$/)
    if (!match) return null
    const verb = match[1]
    const chromeProfile = parseChromeProfileRequest(match[2])
    const forceNew = /\bnew\s+(?:window|instance|app|application|chrome|notepad|browser)\b/.test(match[2])
    const appRequest = forceNew
      ? match[2].replace(/^(?:a\s+)?new\s+/i, "").replace(/\s+(?:window|instance)$/i, "")
      : match[2]
    const requested = chromeProfile ? "chrome" : cleanAppName(appRequest)
    const known = findKnownApp(requested)
    const appName = known?.id || requested
    const label = known?.label || title(requested)
    const action = verb === "close" || verb === "quit" || verb === "exit" ? "close_app" : verb === "restart" ? "restart_app" : verb === "focus" || verb === "switch to" ? "focus_app" : verb === "check" ? "check_app_running" : "open_app"
    const risk = action === "close_app" || action === "restart_app" ? RISK.MEDIUM : RISK.LOW
    return this.desktop(action, { app: appName, app_name: requested, label, force_new: forceNew, profile_name: chromeProfile || undefined }, ["Resolving app", `${title(action.replace("_", " "))}: ${label}`], `${title(action.replace("_", " "))}`, label, risk, "expanded")
  }

  agentIntent(raw, normalized) {
    if (/\b(calendar|schedule|meetings|events)\b/.test(normalized)) {
      const range = /\btomorrow\b/.test(normalized) ? "tomorrow" : /\btoday\b/.test(normalized) ? "today" : "upcoming"
      return this.desktop("get_calendar_events", { range }, ["Reading Google Calendar", "Finding events", "Preparing schedule"], "Calendar", raw, RISK.LOW, "expanded")
    }
    if (/\b(gmail|email|inbox)\b/.test(normalized)) {
      return this.agent("Friday", "Checking Inbox", raw, ["Reading connected context", "Finding important items", "Preparing summary"], ["Integration context", "Summary preparing"])
    }
    const rules = [
      ["Nova", "Researching", ["research", "sources", "competitor", "market", "trend", "news", "latest", "headline"], ["Understanding query", "Searching sources", "Reading articles", "Analyzing data", "Building report"]],
      ["Zeus", "Building Strategy", ["strategy", "business", "growth", "revenue", "pitch", "gtm"], ["Understanding business goal", "Checking workspace memory", "Building strategy", "Preparing recommendations"]],
      ["Atlas", "Designing Architecture", ["architecture", "technical", "api", "build", "software"], ["Understanding system goal", "Reviewing technical context", "Designing modules", "Preparing architecture"]],
      ["Friday", "Creating Content", ["content", "campaign", "linkedin", "social", "calendar"], ["Understanding audience", "Building content pillars", "Drafting content", "Preparing calendar"]],
      ["Alex", "Preparing Study Plan", ["study", "exam", "learn", "revision", "personal", "classroom", "assignment", "assignments"], ["Understanding learning goal", "Checking study material", "Building roadmap", "Preparing notes"]],
      ["Bolt", "Planning Execution", ["launch", "execute", "task", "workflow", "plan", "automation", "automations"], ["Understanding objective", "Breaking down milestones", "Assigning priorities", "Preparing execution plan"]],
    ]
    for (const [agent, verb, terms, steps] of rules) {
      if (terms.some((term) => normalized.includes(term))) {
        return this.agent(agent, verb, raw, steps, agent === "Nova" ? ["Sources ready", "Report preparing"] : ["Workspace context ready", "Result preparing"])
      }
    }
    return null
  }

  identityIntent(raw, normalized) {
    const identityPatterns = [
      /\bwho are you\b/,
      /\bwhat are you\b/,
      /\bwhat is ceaser\b/,
      /\btell me about yourself\b/,
      /\bwhat can you do\b/,
      /\bhelp me\b/,
      /\bshow your capabilities\b/,
      /\bwhy should i use ceaser\b/,
      /\bhow are you different\b/,
      /\bexplain yourself\b/,
      /\bintroduce yourself\b/,
      /\bwhat do you do\b/,
      /\bwhat can ceaser do\b/,
      /\bceaser capabilities\b/,
      /\bwho (?:is|are) (?:your|the) founder\b/,
      /\bwho founded ceaser\b/,
      /\bwhat(?:'s| is) your version\b/,
      /\bwhich version\b/,
      /\bwho am i\b/,
      /\bwhat(?:'s| is) my name\b/,
      /\bdo you know me\b/,
      /\bremember[, ]+my name\b/,
      /\bmy name is\b/,
    ]
    if (!identityPatterns.some((pattern) => pattern.test(normalized))) return null
    return {
      intent: INTENT_TYPES.IDENTITY,
      intent_type: INTENT_TYPES.IDENTITY,
      action: "generate_identity",
      parameters: { question: raw },
      requires_confirmation: false,
      requires_permission: false,
      required_permission: null,
      risk_level: RISK.LOW,
      active_agent: "CEASER",
      overlay_mode: "compact",
      overlay_state: "thinking",
      progress_steps: [],
      result_preview: { title: "CEASER Identity", summary: raw },
    }
  }

  demoSafeIntent(raw, normalized) {
    if (/\b(autonomous|control browser|click for me|fill form|buy|purchase)\b/.test(normalized)) {
      return this.demoSafeBlocked(raw, "This action needs manual review before CEASER can continue.")
    }
    return null
  }

  demoSafeBlocked(raw, summary) {
    return {
      intent: INTENT_TYPES.BLOCKED,
      intent_type: INTENT_TYPES.BLOCKED,
      action: "demo_safe_blocked",
      parameters: { command: raw },
      requires_confirmation: false,
      requires_permission: false,
      required_permission: null,
      risk_level: RISK.BLOCKED,
      active_agent: "CEASER",
      overlay_mode: "compact",
      overlay_state: "error",
      progress_steps: [],
      result_preview: { title: "Action needs review", summary },
    }
  }

  agent(agent, verb, raw, steps, stats) {
    return {
      intent: INTENT_TYPES.AGENT,
      intent_type: INTENT_TYPES.AGENT,
      action: "run_agent",
      parameters: { message: raw },
      requires_confirmation: false,
      requires_permission: false,
      required_permission: null,
      risk_level: RISK.LOW,
      active_agent: agent,
      agent_action: verb,
      overlay_mode: "expanded",
      overlay_state: "working",
      progress_steps: steps.map((label, index) => ({ label, status: index < 2 ? "done" : index === 2 ? "active" : "pending" })),
      result_preview: { title: `${agent} ${verb}`, summary: raw, stats },
    }
  }

  desktop(action, parameters, steps, titleText, summary, riskLevel = RISK.LOW, overlayMode = "compact") {
    const requiredPermission = permissionFor(action)
    const confirmation = requiresConfirmation(action)
    return {
      intent: INTENT_TYPES.DESKTOP,
      intent_type: INTENT_TYPES.DESKTOP,
      action,
      parameters,
      requires_confirmation: confirmation,
      requires_permission: Boolean(requiredPermission),
      required_permission: requiredPermission,
      risk_level: riskLevel,
      active_agent: "CEASER",
      overlay_mode: overlayMode,
      overlay_state: confirmation ? "waiting_confirmation" : "working",
      progress_steps: steps.map((label, index) => ({ label, status: index === 0 ? "active" : "pending" })),
      result_preview: { title: titleText, summary, stats: [`Registry: ${exposePatternCount()}+ patterns`] },
    }
  }

  chat(raw) {
    return {
      intent: INTENT_TYPES.CHAT,
      intent_type: INTENT_TYPES.CHAT,
      action: "chat",
      parameters: { message: raw },
      requires_confirmation: false,
      requires_permission: false,
      required_permission: null,
      risk_level: RISK.LOW,
      active_agent: "CEASER",
      overlay_state: "thinking",
      overlay_mode: "compact",
      progress_steps: ["Understanding request", "Checking memory", "Preparing response"].map((label, index) => ({ label, status: index === 0 ? "active" : "pending" })),
      result_preview: { title: "CEASER Thinking", summary: raw },
    }
  }

  answer(raw) {
    return {
      intent: "answer_action",
      intent_type: "answer_action",
      action: "answer_question",
      parameters: { question: raw },
      requires_confirmation: false,
      requires_permission: false,
      required_permission: null,
      risk_level: RISK.LOW,
      active_agent: "CEASER",
      overlay_state: "thinking",
      overlay_mode: "compact",
      progress_steps: [],
      result_preview: { title: "Answering", summary: raw },
    }
  }
}

function cleanAppName(value) {
  return value
    .replace(/\b(app|application|please)\b/g, "")
    .replace(/[.!?,;:]+$/g, "")
    .replace(/[^\w\s.+#-]/g, "")
    .replace(/\s+/g, " ")
    .trim()
}

function parseChromeProfileRequest(value) {
  const text = String(value || "").trim()
  const patterns = [
    /^(?:google\s+)?chrome\s+(?:with\s+|using\s+)?profile\s+(.+?)(?:\s+in\s+(?:a\s+)?new\s+window)?$/i,
    /^(.+?)\s+profile\s+(?:in|on)\s+(?:google\s+)?chrome(?:\s+in\s+(?:a\s+)?new\s+window)?$/i,
    /^(?:google\s+)?chrome\s+(?:with|using)\s+(.+?)\s+profile(?:\s+in\s+(?:a\s+)?new\s+window)?$/i,
  ]
  for (const pattern of patterns) {
    const match = text.match(pattern)
    if (match?.[1]) return match[1].replace(/\bplease\b/gi, "").trim()
  }
  return ""
}

function findKnownApp(value) {
  for (const [id, aliases] of Object.entries(appAliases)) {
    if (aliases.includes(value) || aliases.some((alias) => value.includes(alias))) return { id, label: title(aliases[0]) }
  }
  return null
}

function normalizeUrl(value) {
  return /^https?:\/\//i.test(value) ? value : `https://${value}`
}

function title(value) {
  return String(value || "").replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function targetWindow(raw) {
  const cleaned = String(raw || "")
    .replace(/\b(close|quit|exit|minimize|maximize|restore|bring|focus|switch to|window|current|front|to the|to)\b/gi, "")
    .replace(/\s+/g, " ")
    .trim()
  return cleaned || ""
}

function cleanLocation(value) {
  return String(value || "")
    .replace(/[.!?,;:]+$/g, "")
    .replace(/\b(today|tomorrow|now|please|outside)\b/gi, "")
    .replace(/\s+/g, " ")
    .trim()
}

module.exports = { ActionRouter }
