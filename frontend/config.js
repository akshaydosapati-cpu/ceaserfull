/**
 * CEASER launch configuration.
 * Build can inject NEXT_PUBLIC_CEASER_LAUNCHED through __CEASER_LAUNCHED__.
 * If not injected, the launch date automatically activates public actions.
 */
(function () {
  var injected = "__CEASER_LAUNCHED__";
  var launchDate = "2026-07-30T19:00:00+05:30";
  var launchedByEnv = injected === "true";
  var launchedByDate = Date.now() >= new Date(launchDate).getTime();

  window.CEASER_CONFIG = {
    LAUNCHED: launchedByEnv || launchedByDate,
    LAUNCH_DATE: launchDate,
    CONSOLE_URL: "/console/",
    DOWNLOAD_URL: "/downloads/",
    CONTACT_EMAIL: "hello@ceaser.tech",
    SUPPORT_EMAIL: "support@ceaser.tech",
    ADMIN_BYPASS_KEYS: ["admin", "founder", "demo"],
    PROTECTED_ROUTES: [
      "/dashboard", "/app", "/chat", "/projects",
      "/files", "/memory", "/agents", "/settings", "/admin",
      "/developer", "/internal", "/downloads"
    ],
    GATE_REDIRECT: "/launching-soon.html"
  };
})();
