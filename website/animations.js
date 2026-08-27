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
          '<a href="#pricing" data-feature="pricing">Pricing</a>'
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

    /* -------- Guest workspace -------- */
  var guestWorkspace = document.querySelector("[data-guest-workspace]");
  if (guestWorkspace) {
    var guestGreeting = guestWorkspace.querySelector("[data-guest-greeting]");
    var guestThread = guestWorkspace.querySelector("[data-guest-thread]");
    var guestForm = guestWorkspace.querySelector("[data-guest-form]");
    var guestInput = guestWorkspace.querySelector("[data-guest-input]");
    var guestSuggestions = guestWorkspace.querySelectorAll("[data-guest-suggestion]");
    var guestProfileButtons = guestWorkspace.querySelectorAll("[data-guest-profile-button]");
    var guestProfilePopover = guestWorkspace.querySelector("[data-guest-profile-popover]");
    var guestLockBanner = guestWorkspace.querySelector("[data-guest-lock-banner]");
    var guestLockSource = guestWorkspace.querySelector("[data-guest-lock-source]");
    var guestLockCopy = guestWorkspace.querySelector("[data-guest-lock-copy]");
    var guestNewChatButton = guestWorkspace.querySelector("[data-guest-new-chat]");
    var guestLockedItems = guestWorkspace.querySelectorAll("[data-guest-locked]");
    var guestHistoryKey = "ceaser_guest_chat_history_v1";
    var guestMessages = [];
    var guestLoading = false;
    var lastGuestPrompt = "";
    var guestGreetingText = guestGreetingForHour(new Date().getHours());

    function guestGreetingForHour(hour) {
      if (hour < 12) return "Good morning";
      if (hour < 17) return "Good afternoon";
      return "Good evening";
    }

    function guestWelcomeMessage() {
      return guestGreetingText + ", Guest.\n\nWhat can I help you with? Ask about anything public, keep the conversation going, and create your CEASER account whenever you want the full workspace.";
    }

    function accountRequiredNotice(label) {
      var feature = label ? String(label).toLowerCase() : "this feature";
      return [
        label ? label + " is locked for guest sessions." : "This feature is locked for guest sessions.",
        "",
        "Create your CEASER account to unlock " + feature + ".",
        "",
        "[Create Account](/console/?mode=signup)",
        "[Sign In](/console/?mode=login)"
      ].join("\n");
    }

    function readGuestHistory() {
      try {
        var raw = window.sessionStorage.getItem(guestHistoryKey);
        return raw ? JSON.parse(raw) : null;
      } catch (_error) {
        return null;
      }
    }

    function writeGuestHistory() {
      try {
        window.sessionStorage.setItem(guestHistoryKey, JSON.stringify(guestMessages));
      } catch (_error) {}
    }

    function guestRequiresAccount(message) {
      var normalized = String(message || "").toLowerCase().replace(/\s+/g, " ");
      return /\b(my|our|saved|private|personal)\b.{0,20}\b(projects?|files?|documents?|conversations?|history|settings|integrations?|plugins?|billing|memory|goals?|tasks?|workspace)\b/.test(normalized)
        || /\b(open|show|list|manage|edit|delete|sync|configure)\b.{0,20}\b(projects?|files?|documents?|conversations?|history|settings|integrations?|plugins?|billing|memory|goals?|tasks?|workspace)\b/.test(normalized)
        || /\b(desktop control|desktop companion|saved conversations?|account settings|private workspace)\b/.test(normalized);
    }

    function setGuestGreeting() {
      if (!guestGreeting) return;
      guestGreeting.textContent = guestGreetingText + ", Guest";
    }

    function scrollGuestThread() {
      if (!guestThread) return;
      guestThread.scrollTop = guestThread.scrollHeight;
    }

    function renderGuestThread() {
      if (!guestThread) return;
      var html = guestMessages.map(function (message) {
        var isUser = message.role === "user";
        var body = isUser ? escapeHtml(message.content) : renderMarkdownLite(message.content);
        return [
          '<article class="guest-message ' + (isUser ? "user" : "assistant") + '">',
          '<div class="guest-message-head">',
          '<span>' + (isUser ? "You" : "CEASER") + '</span>',
          '<span>' + escapeHtml(message.timestamp || "") + '</span>',
          '</div>',
          '<div class="guest-message-content">' + body + '</div>',
          message.retryable ? '<div class="guest-message-actions"><button type="button" data-guest-retry="true">Retry</button></div>' : '',
          '</article>'
        ].join("");
      }).join("");
      if (guestLoading) {
        html += '<div class="guest-message assistant guest-message-typing"><div class="guest-message-head"><span>CEASER</span><span>Now</span></div><div class="guest-typing" aria-label="CEASER is preparing a response"><span></span><span></span><span></span></div></div>';
      }
      guestThread.innerHTML = html || '<div class="guest-empty-state">Start a conversation with CEASER.</div>';
      guestThread.setAttribute("aria-busy", guestLoading ? "true" : "false");
      scrollGuestThread();
    }

    function pushGuestMessage(role, content, extras) {
      guestMessages.push({ role: role, content: content, timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }), retryable: extras && extras.retryable ? true : false });
      writeGuestHistory();
      renderGuestThread();
    }

    function ensureGuestHistory() {
      var cached = readGuestHistory();
      if (cached && Array.isArray(cached) && cached.length) {
        guestMessages = cached;
        return;
      }
      guestMessages = [{ role: "assistant", content: guestWelcomeMessage(), timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }), retryable: false }];
      writeGuestHistory();
    }

    function setGuestLoading(next) {
      guestLoading = Boolean(next);
      renderGuestThread();
    }

    function setGuestPopover(open) {
      if (!guestProfilePopover) return;
      guestProfileButtons.forEach(function (button) {
        button.setAttribute("aria-expanded", open ? "true" : "false");
      });
      guestProfilePopover.hidden = !open;
    }

    function closeGuestPopover() {
      setGuestPopover(false);
    }

    function openGuestPopover() {
      setGuestPopover(true);
    }

    function hideGuestLockNotice() {
      if (!guestLockBanner) return;
      guestLockBanner.hidden = true;
    }

    function showGuestLockNotice(label) {
      if (!guestLockBanner) return;
      if (guestLockSource) guestLockSource.textContent = label ? label + " is locked" : "Locked feature";
      if (guestLockCopy) guestLockCopy.textContent = label ? "Create your CEASER account to unlock " + label.toLowerCase() + "." : "Create your CEASER account to unlock this feature.";
      guestLockBanner.hidden = false;
      closeGuestPopover();
    }

    function resetGuestConversation() {
      guestMessages = [{ role: "assistant", content: guestWelcomeMessage(), timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }), retryable: false }];
      lastGuestPrompt = "";
      guestLoading = false;
      try {
        window.sessionStorage.removeItem(guestHistoryKey);
      } catch (_error) {}
      hideGuestLockNotice();
      if (guestInput) guestInput.value = "";
      renderGuestThread();
      closeGuestPopover();
    }

    function submitGuestPrompt(message) {
      var prompt = String(message || "").trim();
      if (!prompt || guestLoading) return Promise.resolve();
      lastGuestPrompt = prompt;
      hideGuestLockNotice();
      pushGuestMessage("user", prompt);
      if (guestRequiresAccount(prompt)) {
        showGuestLockNotice("Private features");
        pushGuestMessage("assistant", accountRequiredNotice("Private features"), { retryable: false });
        return Promise.resolve();
      }
      setGuestLoading(true);
      return callCeaserAi(prompt)
        .then(function (answer) {
          pushGuestMessage("assistant", answer || "CEASER did not return a readable answer.");
        })
        .catch(function () {
          pushGuestMessage("assistant", "CEASER is taking longer than expected. Please try again.", { retryable: true });
        })
        .finally(function () {
          setGuestLoading(false);
        });
    }

    setGuestGreeting();
    ensureGuestHistory();
    renderGuestThread();

    guestProfileButtons.forEach(function (button) {
      button.addEventListener("click", function () {
        if (guestProfilePopover && !guestProfilePopover.hidden) closeGuestPopover();
        else openGuestPopover();
      });
    });

    document.addEventListener("click", function (event) {
      if (!guestProfilePopover || guestProfilePopover.hidden) return;
      var target = event.target;
      if (target && guestWorkspace.contains(target) && !guestProfilePopover.contains(target) && !Array.prototype.some.call(guestProfileButtons, function (button) { return button.contains(target); })) {
        closeGuestPopover();
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closeGuestPopover();
    });

    guestLockedItems.forEach(function (button) {
      button.addEventListener("click", function () {
        var label = button.getAttribute("data-locked-label") || button.textContent || "this feature";
        showGuestLockNotice(label);
      });
    });

    if (guestNewChatButton) {
      guestNewChatButton.addEventListener("click", function () {
        resetGuestConversation();
      });
    }

    guestSuggestions.forEach(function (button) {
      button.addEventListener("click", function () {
        var prompt = button.getAttribute("data-guest-suggestion") || button.textContent || "";
        if (guestInput) guestInput.value = prompt;
        void submitGuestPrompt(prompt);
      });
    });

    if (guestForm) {
      guestForm.addEventListener("submit", function (event) {
        event.preventDefault();
        var prompt = guestInput ? guestInput.value : "";
        if (guestInput) guestInput.value = "";
        closeGuestPopover();
        void submitGuestPrompt(prompt);
      });
    }

    if (guestThread) {
      guestThread.addEventListener("click", function (event) {
        var retryButton = event.target && event.target.closest ? event.target.closest('[data-guest-retry="true"]') : null;
        if (!retryButton || !lastGuestPrompt) return;
        void submitGuestPrompt(lastGuestPrompt);
      });
    }
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
