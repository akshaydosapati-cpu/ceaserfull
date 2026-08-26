(function () {
  "use strict";

  /* -------- Supabase verification safety redirect -------- */
  (function redirectAuthHashFromLanding() {
    if (!window.location.hash || !/(access_token|refresh_token|type=signup|type=recovery)/.test(window.location.hash)) return;
    var path = window.location.pathname.replace(/\/+$/, "");
    if (path.indexOf("/console/auth/") === 0) return;
    window.location.replace("/console/auth/verified/" + window.location.hash);
  })();

  /* -------- Launch phase swap -------- */
  (function applyLaunchPhase() {
    var cfg = window.CEASER_CONFIG || {};
    var launched = Boolean(cfg.LAUNCHED);
    var pre = document.querySelector("[data-prelaunch-only]");
    var post = document.querySelector("[data-postlaunch-only]");
    document.body.setAttribute("data-launch-phase", launched ? "live" : "prelaunch");
    if (launched) {
      if (pre) pre.remove();
      if (post) post.id = "main";
      document.querySelectorAll(".badge-soon").forEach(function (el) {
        el.innerHTML = '<span class="dot" aria-hidden="true"></span>Live Now';
      });
      document.querySelectorAll(".nav-right").forEach(function (navRight) {
        if (!navRight.querySelector("[data-live-console]")) {
          var link = document.createElement("a");
          link.href = "/console/";
          link.className = "btn btn-primary btn-sm";
          link.setAttribute("data-live-console", "true");
          link.textContent = "Console";
          navRight.appendChild(link);
        }
      });
      document.querySelectorAll(".nav-center, .mobile-menu .container").forEach(function (nav) {
        nav.innerHTML = [
          '<a href="#experience">Try CEASER</a>',
          '<a href="#features">Capabilities</a>',
          '<a href="#use-cases">Use Cases</a>',
          '<a href="#companion">Companion</a>',
          '<a href="#students">Students</a>',
          '<a href="#pricing">Pricing</a>'
        ].join("");
      });
    } else if (post) {
      post.remove();
    }
  })();

  /* -------- Nav scroll state -------- */
  var nav = document.querySelector(".nav");
  function onScroll() {
    if (!nav) return;
    if (window.scrollY > 12) nav.classList.add("scrolled");
    else nav.classList.remove("scrolled");
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  /* -------- Mobile nav toggle -------- */
  var toggle = document.querySelector(".nav-toggle");
  var mobileMenu = document.querySelector(".mobile-menu");
  if (toggle && mobileMenu) {
    toggle.addEventListener("click", function () {
      var open = mobileMenu.classList.toggle("open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
    mobileMenu.querySelectorAll("a").forEach(function (a) {
      a.addEventListener("click", function () {
        mobileMenu.classList.remove("open");
        toggle.setAttribute("aria-expanded", "false");
      });
    });
  }

  /* -------- Download tracking -------- */
  document.querySelectorAll('a[href^="/console/"]').forEach(function (link) {
    link.addEventListener("click", function () {
      if (window.ceaserTrackEvent) window.ceaserTrackEvent("try_ceaser_clicked", { location: "landing", destination: "/console/" });
    });
  });
  var downloadModal = document.getElementById("desktop-download-modal");
  var downloadPanel = downloadModal && downloadModal.querySelector(".download-modal-panel");
  var lastDownloadTrigger = null;
  function openDownloadModal(trigger) {
    if (!downloadModal) return;
    lastDownloadTrigger = trigger || null;
    downloadModal.hidden = false;
    document.body.classList.add("download-modal-open");
    if (window.ceaserTrackEvent) window.ceaserTrackEvent("desktop_download_modal_opened", { platform: "windows" });
    window.requestAnimationFrame(function () { if (downloadPanel) downloadPanel.focus(); });
  }
  function closeDownloadModal() {
    if (!downloadModal) return;
    downloadModal.hidden = true;
    document.body.classList.remove("download-modal-open");
    if (lastDownloadTrigger) lastDownloadTrigger.focus();
  }
  document.querySelectorAll(".js-download-modal").forEach(function (link) {
    link.addEventListener("click", function (event) {
      event.preventDefault();
      openDownloadModal(link);
    });
  });
  if (downloadModal) {
    downloadModal.querySelectorAll("[data-download-close]").forEach(function (button) {
      button.addEventListener("click", closeDownloadModal);
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && !downloadModal.hidden) closeDownloadModal();
    });
  }
  document.querySelectorAll("[data-installer-download]").forEach(function (link) {
    link.addEventListener("click", function () {
      if (window.ceaserTrackEvent) window.ceaserTrackEvent("desktop_download_clicked", { platform: "windows" });
      var apiBase = ((window.CEASER_CONFIG && window.CEASER_CONFIG.API_BASE_URL) || "https://ceaser-backend-production-ur04.onrender.com").replace(/\/$/, "");
      var payload = JSON.stringify({ source: "landing", platform: "windows", version: "v1.0" });
      try {
        if (navigator.sendBeacon) {
          navigator.sendBeacon(apiBase + "/admin/downloads/track", new Blob([payload], { type: "application/json" }));
          return;
        }
        fetch(apiBase + "/admin/downloads/track", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: payload,
          keepalive: true,
        }).catch(function () {});
      } catch (_error) {}
    });
  });

  /* -------- Scroll reveal -------- */
  var revealEls = document.querySelectorAll(".reveal, .reveal-stagger");
  if ("IntersectionObserver" in window && revealEls.length) {
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("in");
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.14, rootMargin: "0px 0px -60px 0px" }
    );
    revealEls.forEach(function (el) { io.observe(el); });
  } else {
    revealEls.forEach(function (el) { el.classList.add("in"); });
  }

  /* -------- Workflow card stagger (hero mockup) -------- */
  document.querySelectorAll(".wf-card").forEach(function (el, i) {
    el.style.animationDelay = 0.15 + i * 0.18 + "s";
  });

  /* -------- Countdown (used on gate page + launch section) -------- */
  function startCountdown(root) {
    var targetStr = (window.CEASER_CONFIG && window.CEASER_CONFIG.LAUNCH_DATE) || null;
    if (!targetStr) return;
    var target = new Date(targetStr).getTime();
    var els = {
      d: root.querySelector('[data-cd="d"]'),
      h: root.querySelector('[data-cd="h"]'),
      m: root.querySelector('[data-cd="m"]'),
      s: root.querySelector('[data-cd="s"]')
    };
    function tick() {
      var diff = Math.max(0, target - Date.now());
      var d = Math.floor(diff / 86400000);
      var h = Math.floor((diff % 86400000) / 3600000);
      var m = Math.floor((diff % 3600000) / 60000);
      var s = Math.floor((diff % 60000) / 1000);
      if (els.d) els.d.textContent = String(d).padStart(2, "0");
      if (els.h) els.h.textContent = String(h).padStart(2, "0");
      if (els.m) els.m.textContent = String(m).padStart(2, "0");
      if (els.s) els.s.textContent = String(s).padStart(2, "0");
    }
    tick();
    setInterval(tick, 1000);
  }
  document.querySelectorAll("[data-countdown]").forEach(startCountdown);

  /* -------- Live command showcase -------- */
  var commandCycle = document.querySelector("[data-command-cycle]");
  if (commandCycle) {
    var commands = ["Open Word", "Open Settings", "Summarize PDF", "Create Presentation"];
    var idx = 0;
    setInterval(function () {
      idx = (idx + 1) % commands.length;
      commandCycle.textContent = commands[idx];
    }, 1800);
  }

  /* -------- Live feature lab -------- */
  var featureData = {
    voice: {
      label: "Ask CEASER",
      title: "Try browser-ready intelligence.",
      body: "Choose a prepared command and CEASER will generate a useful response in the browser experience.",
      prompts: [
        { text: "Explain Quantum Computing", action: "ai", prompt: "Explain quantum computing in simple, beginner-friendly language. Include qubits, superposition, entanglement, and one practical example." },
        { text: "Summarize the Ramayana", action: "ai", prompt: "Summarize the Ramayana clearly for a beginner. Include the main characters, core story, major events, and lessons." },
        { text: "Check Hyderabad weather", action: "weather", prompt: "Hyderabad" },
        { text: "Create an AI trend briefing", action: "ai", prompt: "Create a concise AI industry trend briefing for a launch visitor. Focus on major AI themes people should watch: multimodal AI, agents, enterprise AI, regulation, and AI infrastructure. Do not claim this is breaking news or live reporting." }
      ],
      steps: ["Request understood", "Context prepared", "Answer ready"],
      visual: "voice",
      results: []
    },
    capture: {
      label: "Smart Capture",
      title: "Analyze real sample context.",
      body: "Use built-in demo material or upload your own file. CEASER receives the context before generating an answer.",
      prompts: [
        { text: "Analyze sample monthly expenses", action: "ai", prompt: "Analyze this sample monthly expense report for Rahul, a college student in Hyderabad. Monthly income: ₹30,000. Expenses: Rent ₹10,000, Food ₹5,500, Transport ₹2,000, Entertainment ₹2,500, Shopping ₹3,000, Miscellaneous ₹2,000, Savings ₹5,000. Output: summary, table, biggest spending category, savings suggestions, and a simple budget recommendation." },
        { text: "Summarize sample research paper", action: "ai", prompt: "Summarize this sample research paper abstract. Title: AI-Assisted Learning for Engineering Students. Abstract: The study evaluates how AI tools help engineering students prepare notes, summarize technical papers, generate practice questions, and organize project work. Results suggest that structured AI assistance improves revision speed, concept clarity, and project planning, but students still need human review for accuracy. Output: summary, key findings, limitations, and student use cases." },
        { text: "Review sample resume", action: "ai", prompt: "Review this sample resume for a frontend intern. Candidate: Priya Sharma. Skills: HTML, CSS, JavaScript, React basics, Tailwind, Git. Projects: Portfolio website, weather app using API, task manager. Experience: college coding club volunteer. Goal: frontend internship. Output: strengths, gaps, improvements, rewritten summary, and interview preparation tips." },
        { text: "Explain sample offer letter", action: "ai", prompt: "Explain this sample internship offer letter in simple words. Company: CEASER Technologies. Candidate: Chirag Chouhan. Role: Product Design Intern. Start date: 19 August 2026. Duration: 3 months. Stipend: ₹12,000 per month. Requirements: submit ID proof, sign NDA, join onboarding call, report weekly progress. Output: summary, important dates, responsibilities, required actions, and warnings." }
      ],
      steps: ["Sample loaded", "Context analyzed", "Insights ready"],
      visual: "capture",
      results: []
    },
    create: {
      label: "Creation Engine",
      title: "Generate polished work.",
      body: "Turn a rough intent into emails, plans, reports, documents, study notes, and presentations.",
      prompts: [
        { text: "Write a leave request email", action: "ai", prompt: "Write a professional leave request email. Context: Employee named Rahul needs leave on 21 August 2026 for a family function. Recipient: manager named Sainath. Tone: polite and concise. Include subject, reason, date, handover assurance, and closing." },
        { text: "Create a LinkedIn launch post", action: "ai", prompt: "Write a polished LinkedIn launch post for CEASER. Context: CEASER is an AI operating system launching for students, founders, and professionals. It includes AI chat, Smart Capture, workflow planning, projects, memory, billing, and a Windows Desktop Companion. Tone: confident, premium, practical. Include a strong opening hook and short call to action." },
        { text: "Generate Python expense tracker", action: "ai", prompt: "Generate a beginner-friendly Python expense tracker script for a student. Requirements: add expenses with category and amount, show total spend, show spend by category, allow typing done to finish, and print a clean summary. Include comments and a short explanation after the code." },
        { text: "Draft a product announcement", action: "ai", prompt: "Draft a product launch announcement for CEASER V1. Context: CEASER helps users move from intent to execution using AI chat, Smart Capture, workflows, projects, memory, and Desktop Companion voice control. Audience: early users, students, creators, and startup teams. Include headline, short body, key benefits, availability, and call to action." }
      ],
      steps: ["Structuring", "Drafting", "Refining"],
      visual: "create",
      results: []
    },
    control: {
      label: "Desktop Companion",
      title: "Preview desktop-native control.",
      body: "These actions require the installed CEASER Desktop Companion. The website shows how the command flow works.",
      prompts: [
        { text: "Play Hanuman Chalisa", action: "desktop", result: "CEASER Desktop Companion can open the right music result and start playback from your device." },
        { text: "Pause or resume music", action: "desktop", result: "CEASER Desktop Companion can control playback with natural voice commands while you work." },
        { text: "Open any application", action: "desktop", result: "CEASER Desktop Companion discovers installed Windows apps and launches the best match from your voice command." },
        { text: "Take a screenshot", action: "desktop", result: "CEASER Desktop Companion captures the screen and keeps the result available for follow-up actions." }
      ],
      steps: ["Command heard", "Device matched", "Companion acts"],
      visual: "control",
      results: []
    },
    workflow: {
      label: "Workflow OS",
      title: "Complete sequences, not single tasks.",
      body: "CEASER plans multi-step work and guides the task from intent to finished output.",
      prompts: [
        { text: "Turn meeting transcript into notes", action: "ai", prompt: "Turn this meeting transcript into structured notes. Context: CEASER launch meeting for August 21. Transcript: Billing checkout needs live-key verification. Landing page demo needs scenario-based cards. Desktop Companion installer needs testing on another laptop. Backend logs must be monitored during launch. Support needs prepared responses. Akshay owns QA, Sainath owns backend monitoring, frontend team owns UI polish. Output: summary, decisions, action items, owners, deadlines, and risks." },
        { text: "Convert expenses into report", action: "ai", prompt: "Convert this expense data into a short monthly finance report. Person: Rahul, Hyderabad student. Income: ₹30,000. Rent ₹10,000, Food ₹5,500, Transport ₹2,000, Entertainment ₹2,500, Shopping ₹3,000, Misc ₹2,000, Savings ₹5,000. Output: executive summary, table, insights, risks, and recommendations." },
        { text: "Build study plan from syllabus", action: "ai", prompt: "Build a 7-day exam study plan from this sample syllabus. Subject: Operating Systems. Units: processes and threads, CPU scheduling, memory management, file systems, deadlocks, synchronization. Student has 2 hours per day and a mock test on day 6. Output: day-wise plan, revision slots, practice tasks, and final-day checklist." },
        { text: "Create roadmap from project brief", action: "ai", prompt: "Create a practical roadmap from this project brief. Project: Car Rental Digital Platform. Goal: allow users to browse cars, book rentals, manage payments, verify documents, and let admins manage vehicles and bookings. Team: 2 frontend developers, 1 backend developer, 1 designer. Timeline: 6 weeks. Output: milestones, weekly plan, risks, and deliverables." }
      ],
      steps: ["Plan created", "Tasks ordered", "Next action ready"],
      visual: "workflow",
      results: []
    }
  };
  var lab = document.querySelector("[data-feature-lab]");
  if (lab) {
    var tabs = lab.querySelectorAll("[data-feature-tab]");
    var label = lab.querySelector("[data-feature-label]");
    var title = lab.querySelector("[data-feature-title]");
    var body = lab.querySelector("[data-feature-body]");
    var prompt = lab.querySelector("[data-feature-prompt]");
    var promptList = lab.querySelector("[data-feature-prompts]");
    var visual = lab.querySelector("[data-feature-visual]");
    var stepsWrap = lab.querySelector("[data-feature-steps]");
    var activeKey = "voice";
    var activePromptIndex = 0;
    var capturedFileContext = null;
    var resultModal = null;
    var resultModalBody = null;
    var statusTimer = null;
    var uploadedCapturePrompts = [
      { text: "Summarize uploaded document", action: "capture" },
      { text: "Extract uploaded key points", action: "capture" },
      { text: "Find uploaded action items", action: "capture" },
      { text: "Explain uploaded file simply", action: "capture" }
    ];

    function getApiBase() {
      return ((window.CEASER_CONFIG && window.CEASER_CONFIG.API_BASE_URL) || "https://ceaser-backend-production-ur04.onrender.com").replace(/\/$/, "");
    }

    function getStoredAccessToken() {
      var directKeys = ["ceaser_access_token", "access_token", "supabase.auth.token"];
      for (var i = 0; i < directKeys.length; i += 1) {
        var direct = window.localStorage.getItem(directKeys[i]);
        if (direct && direct.length > 20) {
          try {
            var parsedDirect = JSON.parse(direct);
            if (parsedDirect && parsedDirect.access_token) return parsedDirect.access_token;
            if (parsedDirect && parsedDirect.currentSession && parsedDirect.currentSession.access_token) return parsedDirect.currentSession.access_token;
          } catch (_error) {
            return direct;
          }
        }
      }
      for (var j = 0; j < window.localStorage.length; j += 1) {
        var key = window.localStorage.key(j);
        if (!key || key.indexOf("auth-token") === -1) continue;
        try {
          var parsed = JSON.parse(window.localStorage.getItem(key) || "{}");
          if (parsed && parsed.access_token) return parsed.access_token;
          if (parsed && parsed.currentSession && parsed.currentSession.access_token) return parsed.currentSession.access_token;
        } catch (_ignored) {}
      }
      return "";
    }

    function normalizeAiResponse(body) {
      if (!body) return "";
      if (typeof body === "string") return body;
      return body.response || body.answer || body.message || body.content || body.result || body.text || (body.data && (body.data.response || body.data.answer || body.data.message)) || "";
    }

    function escapeHtml(text) {
      return String(text || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
    }

    function renderMarkdownLite(text) {
      var lines = String(text || "").replace(/\r\n/g, "\n").split("\n");
      var html = [];
      var listOpen = false;
      var tableOpen = false;

      function closeList() {
        if (listOpen) {
          html.push("</ul>");
          listOpen = false;
        }
      }
      function closeTable() {
        if (tableOpen) {
          html.push("</tbody></table>");
          tableOpen = false;
        }
      }
      function inline(value) {
        return escapeHtml(value)
          .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
          .replace(/\*(.*?)\*/g, "<em>$1</em>");
      }
      function isSeparator(row) {
        return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(row);
      }

      for (var i = 0; i < lines.length; i += 1) {
        var line = lines[i].trim();
        if (!line || /^-{3,}$/.test(line)) {
          closeList();
          closeTable();
          continue;
        }
        if (line.indexOf("|") !== -1 && i + 1 < lines.length && isSeparator(lines[i + 1])) {
          closeList();
          closeTable();
          var heads = line.replace(/^\||\|$/g, "").split("|").map(function (cell) { return "<th>" + inline(cell.trim()) + "</th>"; }).join("");
          html.push('<table class="demo-output-table"><thead><tr>' + heads + "</tr></thead><tbody>");
          tableOpen = true;
          i += 1;
          continue;
        }
        if (tableOpen && line.indexOf("|") !== -1) {
          var cells = line.replace(/^\||\|$/g, "").split("|").map(function (cell) { return "<td>" + inline(cell.trim()) + "</td>"; }).join("");
          html.push("<tr>" + cells + "</tr>");
          continue;
        }
        closeTable();
        if (/^#{1,4}\s+/.test(line)) {
          closeList();
          html.push("<h3>" + inline(line.replace(/^#{1,4}\s+/, "")) + "</h3>");
          continue;
        }
        if (/^[-*]\s+/.test(line)) {
          if (!listOpen) {
            html.push("<ul>");
            listOpen = true;
          }
          html.push("<li>" + inline(line.replace(/^[-*]\s+/, "")) + "</li>");
          continue;
        }
        closeList();
        html.push("<p>" + inline(line) + "</p>");
      }
      closeList();
      closeTable();
      return html.join("");
    }

    function aiUnavailableMessage() {
      return "CEASER AI is taking longer than expected.\n\nPlease try again in a moment.";
    }

    function callCeaserAi(promptText) {
      var headers = { "Content-Type": "application/json" };
      var controller = new AbortController();
      var timeout = setTimeout(function () { controller.abort(); }, 12000);
      return fetch(getApiBase() + "/ceaser/demo", {
        method: "POST",
        headers: headers,
        body: JSON.stringify({ message: promptText }),
        signal: controller.signal
      })
        .then(function (response) {
          return response.text().then(function (text) {
            var body = {};
            try { body = text ? JSON.parse(text) : {}; } catch (_error) { body = { response: text }; }
            if (!response.ok) {
              throw new Error((body && (body.detail || body.message)) || "Sign in to run this with CEASER AI.");
            }
            return normalizeAiResponse(body) || "CEASER generated the response, but no readable text was returned.";
          });
        })
        .finally(function () { clearTimeout(timeout); });
    }

    function weatherCodeLabel(code) {
      var map = {
        0: "clear sky",
        1: "mostly clear",
        2: "partly cloudy",
        3: "cloudy",
        45: "foggy",
        48: "foggy",
        51: "light drizzle",
        53: "drizzle",
        55: "heavy drizzle",
        61: "light rain",
        63: "rain",
        65: "heavy rain",
        80: "light showers",
        81: "showers",
        82: "heavy showers",
        95: "thunderstorm"
      };
      return map[code] || "changing conditions";
    }

    function callHyderabadWeather() {
      var controller = new AbortController();
      var timeout = setTimeout(function () { controller.abort(); }, 7000);
      var url = "https://api.open-meteo.com/v1/forecast?latitude=17.3850&longitude=78.4867&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m&forecast_days=1&timezone=Asia%2FKolkata";
      return fetch(url, { signal: controller.signal })
        .then(function (response) {
          if (!response.ok) throw new Error("Weather service unavailable");
          return response.json();
        })
        .then(function (body) {
          var current = body && body.current ? body.current : {};
          var temp = Math.round(Number(current.temperature_2m));
          var feels = Math.round(Number(current.apparent_temperature));
          var humidity = Math.round(Number(current.relative_humidity_2m));
          var rain = Number(current.precipitation || 0);
          var wind = Math.round(Number(current.wind_speed_10m || 0));
          var condition = weatherCodeLabel(Number(current.weather_code));
          return [
            "Hyderabad Weather",
            "",
            "Current condition: " + condition + ".",
            "Temperature: " + temp + "°C, feels like " + feels + "°C.",
            "Humidity: " + humidity + "%.",
            "Rain now: " + rain + " mm.",
            "Wind speed: " + wind + " km/h.",
            "",
            "Suggestion:",
            "- Carry water and keep the day light if you are travelling.",
            rain > 0 ? "- Carry an umbrella or raincoat before leaving." : "- Rain is not showing right now, but check once before a long commute.",
            "- Plan extra travel time during peak Hyderabad traffic."
          ].join("\n");
        })
        .finally(function () { clearTimeout(timeout); });
    }

    if (window.pdfjsLib && window.pdfjsLib.GlobalWorkerOptions) {
      window.pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
    }

    function renderPrompts(item) {
      if (!promptList) return;
      var prompts = getActivePrompts(item);
      promptList.innerHTML = prompts.map(function (entry, index) {
        var disabled = false;
        return '<button type="button" class="' + (index === activePromptIndex ? "active" : "") + '" data-prompt-index="' + index + '"' + (disabled ? " disabled" : "") + '>' + entry.text + '</button>';
      }).join("");
      promptList.querySelectorAll("button").forEach(function (button) {
        button.addEventListener("click", function () {
          if (button.disabled) return;
          activePromptIndex = Number(button.getAttribute("data-prompt-index")) || 0;
          setFeature(activeKey);
        });
      });
    }

    function getActivePrompts(item) {
      if (activeKey === "capture" && capturedFileContext) return uploadedCapturePrompts;
      return item.prompts;
    }

    function readCapturedFile(file) {
      var sizeKb = Math.max(1, Math.round(file.size / 1024));
      var ext = (file.name.split(".").pop() || "file").toUpperCase();
      var base = file.name + " selected. Type: " + ext + ". Size: " + sizeKb + " KB.";
      return new Promise(function (resolve) {
        if (/\.pdf$/i.test(file.name) && window.pdfjsLib) {
          var pdfReader = new FileReader();
          pdfReader.onload = function () {
            window.pdfjsLib.getDocument({ data: new Uint8Array(pdfReader.result) }).promise
              .then(function (pdf) {
                var pages = [];
                var maxPages = Math.min(pdf.numPages, 12);
                var chain = Promise.resolve();
                for (var pageNumber = 1; pageNumber <= maxPages; pageNumber += 1) {
                  (function (n) {
                    chain = chain.then(function () {
                      return pdf.getPage(n).then(function (page) {
                        return page.getTextContent().then(function (content) {
                          pages.push(content.items.map(function (item) { return item.str; }).join(" "));
                        });
                      });
                    });
                  })(pageNumber);
                }
                return chain.then(function () {
                  resolve({
                    name: file.name,
                    type: ext,
                    sizeKb: sizeKb,
                    text: pages.join("\n\n").trim(),
                    note: base + " Extracted text from " + maxPages + " page" + (maxPages === 1 ? "" : "s") + "."
                  });
                });
              })
              .catch(function () {
                resolve({ name: file.name, type: ext, sizeKb: sizeKb, text: "", note: base + " PDF text extraction could not complete in this browser." });
              });
          };
          pdfReader.onerror = function () {
            resolve({ name: file.name, type: ext, sizeKb: sizeKb, text: "", note: base + " PDF could not be read in this browser." });
          };
          pdfReader.readAsArrayBuffer(file);
          return;
        }
        if (/text|json|csv|markdown|xml/i.test(file.type) || /\.(txt|md|csv|json|xml)$/i.test(file.name)) {
          var reader = new FileReader();
          reader.onload = function () {
            var text = String(reader.result || "").trim();
            resolve({ name: file.name, type: ext, sizeKb: sizeKb, text: text, note: base });
          };
          reader.onerror = function () {
            resolve({ name: file.name, type: ext, sizeKb: sizeKb, text: "", note: base + " Text could not be read in the browser." });
          };
          reader.readAsText(file);
          return;
        }
        resolve({ name: file.name, type: ext, sizeKb: sizeKb, text: "", note: base + " Full PDF, Office, and image parsing runs in the CEASER console or Desktop Companion." });
      });
    }

    function buildCapturePrompt(commandText) {
      var file = capturedFileContext;
      var readableText = file && file.text ? file.text.slice(0, 12000) : "";
      var instruction = commandText + " for the uploaded file named " + (file ? file.name : "the selected file") + ".";
      if (!readableText) {
        return instruction + " The browser only has file metadata: type " + (file ? file.type : "unknown") + ", size " + (file ? file.sizeKb : 0) + " KB. Explain what can be inferred and what needs full file parsing.";
      }
      return [
        "You are CEASER Smart Capture.",
        "Do not copy or read the document line by line.",
        "Produce a concise, useful result based on the selected action.",
        "If the document is a letter, identify sender, recipient, purpose, dates, obligations, next steps, and important warnings.",
        "Keep the answer structured and under 220 words unless the user asks for detail.",
        "",
        "Selected action: " + commandText,
        "File name: " + (file ? file.name : "uploaded file"),
        "",
        "Extracted document text:",
        readableText
      ].join("\n");
    }

    function ensureResultModal() {
      if (resultModal) return;
      resultModal = document.createElement("div");
      resultModal.className = "try-result-modal";
      resultModal.hidden = true;
      resultModal.innerHTML = [
        '<div class="try-result-dialog" role="dialog" aria-modal="true" aria-label="CEASER output">',
        '<button type="button" class="try-result-close" aria-label="Close output">×</button>',
        '<div class="try-result-kicker">CEASER Output</div>',
        '<div class="try-result-body"></div>',
        '</div>'
      ].join("");
      document.body.appendChild(resultModal);
      resultModalBody = resultModal.querySelector(".try-result-body");
      resultModal.querySelector(".try-result-close").addEventListener("click", closeResultModal);
      var stopButton = document.createElement("button");
      stopButton.type = "button";
      stopButton.className = "try-result-stop";
      stopButton.textContent = "Stop Speaking";
      stopButton.setAttribute("aria-label", "Stop speaking");
      stopButton.addEventListener("click", function () {
        if ("speechSynthesis" in window) window.speechSynthesis.cancel();
      });
      resultModal.querySelector(".try-result-dialog").appendChild(stopButton);
      resultModal.addEventListener("click", function (event) {
        if (event.target === resultModal) closeResultModal();
      });
      document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") closeResultModal();
      });
    }

    function closeResultModal() {
      if (resultModal) resultModal.hidden = true;
      if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    }

    function setResultText(text, openPopup) {
      if (openPopup) {
        ensureResultModal();
        if (resultModalBody) resultModalBody.innerHTML = renderMarkdownLite(text);
        if (resultModal) resultModal.hidden = false;
      }
    }

    function setStepLabels(labels, activeIndex) {
      var chips = lab.querySelectorAll("[data-feature-steps] span");
      chips.forEach(function (chip, index) {
        chip.textContent = labels[index] || chip.textContent;
        chip.classList.toggle("active", index === activeIndex);
        chip.classList.toggle("done", index < activeIndex);
      });
    }

    function startStatusCycle(kind) {
      stopStatusCycle();
      var states = kind === "capture"
        ? [
            ["File loaded", "Reading content", "Ready to analyze"],
            ["Scanning file", "Extracting context", "Preparing insight"],
            ["Understanding", "Finding key details", "Generating answer"]
          ]
        : [
            ["Request understood", "Preparing context", "Ready"],
            ["Understanding goal", "Building answer", "Generating"],
            ["Structuring output", "Polishing response", "Almost ready"]
          ];
      var index = 0;
      setStepLabels(states[0], 0);
      statusTimer = setInterval(function () {
        index = (index + 1) % states.length;
        setStepLabels(states[index], Math.min(index, 2));
      }, 900);
    }

    function stopStatusCycle() {
      if (statusTimer) {
        clearInterval(statusTimer);
        statusTimer = null;
      }
    }

    function speakOutput(text) {
      if (!("speechSynthesis" in window)) return;
      try {
        window.speechSynthesis.cancel();
        var spokenText = String(text || "")
          .replace(/```[\s\S]*?```/g, " Code block prepared on screen. ")
          .replace(/`([^`]+)`/g, "$1")
          .replace(/^#{1,6}\s*/gm, "")
          .replace(/\*\*(.*?)\*\*/g, "$1")
          .replace(/\*(.*?)\*/g, "$1")
          .replace(/^\s*[-*]\s+/gm, "")
          .replace(/^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*$/gm, "")
          .replace(/\|/g, ", ")
          .replace(/-{3,}/g, " ")
          .replace(/[_>#]/g, " ")
          .replace(/\s+/g, " ")
          .trim();
        var utterance = new SpeechSynthesisUtterance(spokenText.slice(0, 900));
        utterance.rate = 1;
        utterance.pitch = 1;
        window.speechSynthesis.speak(utterance);
      } catch (_error) {}
    }

    function runSelectedCommand() {
      var item = featureData[activeKey] || featureData.voice;
      var prompts = getActivePrompts(item);
      var selected = prompts[activePromptIndex] || prompts[0];
      lab.classList.remove("is-running");
      void lab.offsetWidth;
      lab.classList.add("is-running");

      if (selected.action === "desktop") {
        var desktopPreview = "Available after installing CEASER Desktop Companion.\n\n" + selected.result + "\n\nUse the Download Desktop Companion button to enable this on your Windows device.";
        setResultText(desktopPreview, true);
        speakOutput("This is available in the CEASER Desktop Companion.");
        setTimeout(function () { lab.classList.remove("is-running"); }, 1200);
        return Promise.resolve();
      }

      if (selected.action === "capture") {
        if (!capturedFileContext) {
          setStepLabels(["Drop a file", "Choose action", "Analyze"], 0);
          setTimeout(function () { lab.classList.remove("is-running"); }, 1200);
          return Promise.resolve();
        }
        startStatusCycle("capture");
        return callCeaserAi(buildCapturePrompt(selected.text))
          .then(function (answer) {
            stopStatusCycle();
            setStepLabels(["File analyzed", "Insight prepared", "Answer ready"], 2);
            setResultText(answer, true);
            speakOutput(answer);
          })
          .catch(function (error) {
            stopStatusCycle();
            var message = aiUnavailableMessage();
            setResultText(message, true);
            speakOutput("CEASER AI could not respond from the live backend within five seconds.");
          })
          .finally(function () { stopStatusCycle(); setTimeout(function () { lab.classList.remove("is-running"); }, 900); });
      }

      if (selected.action === "weather") {
        startStatusCycle("ai");
        return callHyderabadWeather()
          .then(function (answer) {
            stopStatusCycle();
            setStepLabels(["Location matched", "Weather checked", "Briefing ready"], 2);
            setResultText(answer, true);
            speakOutput(answer);
          })
          .catch(function () {
            stopStatusCycle();
            var message = "Weather service is taking longer than expected.\n\nPlease try again in a moment.";
            setResultText(message, true);
            speakOutput("Weather service is taking longer than expected.");
          })
          .finally(function () { stopStatusCycle(); setTimeout(function () { lab.classList.remove("is-running"); }, 900); });
      }

      if (selected.action === "ai") {
        startStatusCycle("ai");
        setResultText("CEASER is preparing a live answer.");
        return callCeaserAi(selected.prompt || selected.text)
          .then(function (answer) {
            stopStatusCycle();
            setStepLabels(["Request understood", "Context prepared", "Answer ready"], 2);
            setResultText(answer, true);
            speakOutput(answer);
          })
          .catch(function (error) {
            stopStatusCycle();
            var message = aiUnavailableMessage();
            setResultText(message, true);
            speakOutput("CEASER AI could not respond from the live backend within five seconds.");
          })
          .finally(function () { stopStatusCycle(); setTimeout(function () { lab.classList.remove("is-running"); }, 900); });
      }

      setResultText(selected.result || "Ready.");
      setTimeout(function () { lab.classList.remove("is-running"); }, 1200);
      return Promise.resolve();
    }

    function bindDropZone() {
      var zone = lab.querySelector("[data-drop-zone]");
      if (!zone) return;
      var fileInput = lab.querySelector("[data-capture-file]");
      zone.addEventListener("click", function () {
        if (fileInput) fileInput.click();
      });
      ["dragenter", "dragover"].forEach(function (name) {
        zone.addEventListener(name, function (event) {
          event.preventDefault();
          zone.classList.add("dragging");
        });
      });
      ["dragleave", "drop"].forEach(function (name) {
        zone.addEventListener(name, function (event) {
          event.preventDefault();
          zone.classList.remove("dragging");
        });
      });
      zone.addEventListener("drop", function (event) {
        var file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
        if (!file) return;
        handleCaptureFile(file);
      });
    }

    function handleCaptureFile(file) {
      setFeature("capture");
      setStepLabels(["Reading file", "Preparing actions", "Ready"], 0);
      readCapturedFile(file).then(function (context) {
        capturedFileContext = context;
        activePromptIndex = 0;
        setFeature("capture");
        setStepLabels(["File uploaded", "Choose action", "Ready"], 2);
      });
    }

    function renderVisual(item) {
      if (!visual) return;
      var prompts = getActivePrompts(item);
      visual.setAttribute("data-visual", item.visual);
      visual.innerHTML = [
        '<div class="try-orb"></div>',
        item.visual === "capture" ? '<div class="try-drop-card" data-drop-zone><strong>Drop Zone</strong><span>Drop a file here or click to choose</span><i></i></div>' : '',
        item.visual === "create" ? '<div class="try-create-flow"><span>Intent</span><span>Outline</span><span>Draft</span><span>Polish</span></div>' : '',
        item.visual === "control" ? '<div class="try-app-grid"><span>Music</span><span>Apps</span><span>Screenshot</span><span>Media</span></div><div class="desktop-preview-lock"><strong>Available on Desktop Companion</strong><span>Install CEASER on Windows to run music, app, screenshot, media, and local device commands.</span><a href="/downloads/">Download Companion</a></div>' : '',
        item.visual === "workflow" ? '<div class="try-workflow-mini"><span>Plan</span><span>Build</span><span>Review</span><span>Done</span></div>' : '',
        '<div class="try-lines" data-feature-steps>' + item.steps.map(function (step) { return '<span>' + step + '</span>'; }).join("") + '</div>'
      ].join("");
      bindDropZone();
    }
    function setFeature(key) {
      var item = featureData[key] || featureData.voice;
      activeKey = key;
      if (activePromptIndex >= getActivePrompts(item).length) activePromptIndex = 0;
      tabs.forEach(function (tab) { tab.classList.toggle("active", tab.getAttribute("data-feature-tab") === key); });
      if (label) label.textContent = item.label;
      if (title) title.textContent = item.title;
      if (body) body.textContent = item.body;
      if (prompt) prompt.textContent = getActivePrompts(item)[activePromptIndex].text;
      renderPrompts(item);
      renderVisual(item);
      lab.setAttribute("data-active-feature", key);
    }
    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () { setFeature(tab.getAttribute("data-feature-tab")); });
    });
    var runner = lab.querySelector("[data-try-runner]");
    if (runner) {
      runner.addEventListener("submit", function (event) {
        event.preventDefault();
        runSelectedCommand();
      });
    }
    var mic = lab.querySelector("[data-try-mic]");
    if (mic && runner) {
      mic.addEventListener("click", function () {
        runner.requestSubmit();
      });
    }
    var captureFile = lab.querySelector("[data-capture-file]");
    if (captureFile) {
      captureFile.addEventListener("change", function () {
        var file = captureFile.files && captureFile.files[0];
        if (!file) return;
        handleCaptureFile(file);
      });
    }
    setFeature("voice");
  }

  /* -------- Rotating workflow motion examples -------- */
  var workflow = document.querySelector("[data-workflow-motion]");
  if (workflow) {
    var examples = [
      { title: "Prepare Monthly Report", desc: "Collect data, generate charts, write the report, and export it.", steps: ["Collect Information", "Generate Charts", "Write Report", "Export PDF"] },
      { title: "Study Research Paper", desc: "Understand dense material and turn it into study-ready output.", steps: ["Summarize", "Explain", "Generate Questions", "Voice Review"] },
      { title: "Launch Product Campaign", desc: "Move from idea to launch assets without scattered tools.", steps: ["Define Audience", "Draft Copy", "Plan Calendar", "Create Assets"] },
      { title: "Prepare Interview", desc: "Build a practical preparation path from the role and resume.", steps: ["Analyze Role", "Generate Questions", "Practice Answers", "Score Response"] }
    ];
    var titleEl = workflow.querySelector("[data-workflow-title]");
    var descEl = workflow.querySelector("[data-workflow-desc]");
    var stepEls = workflow.querySelectorAll("[data-wf-step]");
    var current = 0;
    function setWorkflow() {
      var item = examples[current % examples.length];
      if (titleEl) titleEl.textContent = item.title;
      if (descEl) descEl.textContent = item.desc;
      stepEls.forEach(function (el, i) { el.textContent = item.steps[i]; });
      current += 1;
    }
    setInterval(setWorkflow, 4200);
  }

  /* -------- Launch waitlist form handling -------- */
  document.querySelectorAll("form[data-launch-form]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();

      var card = form.closest(".form-card");
      var success = card ? card.querySelector(".form-success") : null;
      var submitBtn = form.querySelector('button[type="submit"]');
      var emailInput = form.querySelector('input[name="email"]');
      var nameInput = form.querySelector('input[name="name"]');
      var userTypeInput = form.querySelector('select[name="userType"]');

      if (!emailInput || !emailInput.value.trim()) return;

      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = "Submitting…";
      }

      var payload = {
        email: emailInput.value.trim()
      };

      var apiBase = ((window.CEASER_CONFIG && window.CEASER_CONFIG.API_BASE_URL) || "https://ceaser-backend-production-ur04.onrender.com").replace(/\/$/, "");

      fetch(apiBase + "/api/v1/waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      })
        .then(function (response) {
          return response.text().then(function (text) {
            var body = {};
            try {
              body = text ? JSON.parse(text) : {};
            } catch (_error) {
              body = {};
            }
            if (!response.ok) {
              throw new Error(body.detail || "Unable to join the launch list right now.");
            }
            return body;
          });
        })
        .then(function () {
          form.style.display = "none";
          if (success) {
            success.querySelector("h3").textContent = "🎉 You're officially on the CEASER Launch List.";
            success.querySelector("p").textContent = "Please check your inbox for your welcome email.";
            success.classList.add("show");
          }
        })
        .catch(function (error) {
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = "Get Launch Updates";
          }
          if (emailInput) {
            emailInput.setAttribute("aria-invalid", "true");
          }
          if (success) {
            success.querySelector("h3").textContent = "Unable to join right now";
            success.querySelector("p").textContent = error.message || "Please try again in a moment.";
            success.classList.add("show");
          }
        });
    });
  });

  /* -------- Route gating (client-side guard for protected paths) -------- */
  (function gate() {
    var cfg = window.CEASER_CONFIG;
    if (!cfg || cfg.LAUNCHED) return;
    var path = window.location.pathname;
    var isProtected = cfg.PROTECTED_ROUTES.some(function (p) {
      return path === p || path.indexOf(p + "/") === 0;
    });
    if (isProtected) {
      window.location.replace(cfg.GATE_REDIRECT);
    }
  })();
})();
