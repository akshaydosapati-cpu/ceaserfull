export type CeaserAnalyticsEvent =
  | "try_ceaser_clicked" | "sign_up_started" | "sign_up" | "login" | "console_opened"
  | "chat_message_sent" | "chat_response_completed" | "desktop_download_clicked"
  | "artifact_requested" | "artifact_completed" | "plugin_connect_started" | "plugin_connected" | "desktop_connected"

type AnalyticsParams = Record<string, string | number | boolean | undefined>

declare global {
  interface Window { gtag?: (...args: unknown[]) => void }
}

const allowedHosts = new Set(["heyceaser.in", "www.heyceaser.in"])

export function trackEvent(name: CeaserAnalyticsEvent, params: AnalyticsParams = {}) {
  if (typeof window === "undefined" || !allowedHosts.has(window.location.hostname) || typeof window.gtag !== "function") return
  window.gtag("event", name, Object.fromEntries(Object.entries(params).filter(([, value]) => value !== undefined)))
}
