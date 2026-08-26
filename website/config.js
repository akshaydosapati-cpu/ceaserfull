/**
 * CEASER launch configuration.
 * The launch date is authoritative so a stale deployment flag cannot expose
 * the post-launch experience before the announced time.
 */
(function () {
  var injected = "__CEASER_LAUNCHED__";
  var launchDate = "2026-08-21T14:15:00+05:30";
  var launchedByEnv = injected === "true" && Date.now() >= new Date(launchDate).getTime();
  var launchedByDate = Date.now() >= new Date(launchDate).getTime();

  window.CEASER_CONFIG = {
    LAUNCHED: launchedByEnv || launchedByDate,
    LAUNCH_DATE: launchDate,
    CONSOLE_URL: "/console/",
    DOWNLOAD_URL: "/downloads/",
    API_BASE_URL: "https://ceaser-backend-production-ur04.onrender.com",
    SUPABASE_URL: "https://rrfqqgxhmimffrcckxay.supabase.co",
    CONTACT_EMAIL: "teamceaser@heyceaser.in",
    SUPPORT_EMAIL: "teamceaser@heyceaser.in",
    PROTECTED_ROUTES: [
      "/dashboard", "/app", "/chat", "/projects",
      "/files", "/memory", "/agents", "/settings", "/admin",
      "/developer", "/internal", "/downloads"
    ],
    GATE_REDIRECT: "/launching-soon.html"
  };
})();
