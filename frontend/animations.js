(function () {
  "use strict";

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

  /* -------- Form handling (front-end only demo; wire to backend later) -------- */
  document.querySelectorAll("form[data-launch-form]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var card = form.closest(".form-card");
      var success = card ? card.querySelector(".form-success") : null;
      var submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = "Submitting…";
      }
      setTimeout(function () {
        form.style.display = "none";
        if (success) success.classList.add("show");
      }, 500);
    });
  });

  /* -------- Route gating (client-side guard for protected paths) -------- */
  (function gate() {
    var cfg = window.CEASER_CONFIG;
    if (!cfg || cfg.LAUNCHED) return;
    var path = window.location.pathname;
    var params = new URLSearchParams(window.location.search);
    var bypassKeys = cfg.ADMIN_BYPASS_KEYS || [];
    var hasBypass = bypassKeys.some(function (key) {
      return params.has(key) || window.localStorage.getItem("ceaser_" + key + "_access") === "true";
    });
    if (hasBypass) {
      bypassKeys.forEach(function (key) {
        if (params.has(key)) window.localStorage.setItem("ceaser_" + key + "_access", "true");
      });
      return;
    }
    var isProtected = cfg.PROTECTED_ROUTES.some(function (p) {
      return path === p || path.indexOf(p + "/") === 0;
    });
    if (isProtected) {
      window.location.replace(cfg.GATE_REDIRECT);
    }
  })();
})();
