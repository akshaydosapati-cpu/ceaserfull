"use client"

import { clearAuthTokens } from "./api/client"

const SESSION_LOCAL_STORAGE_KEYS = [
  "ceaser_user_profile",
  "ceaser_current_page",
  "ceaser_active_conversation_id",
  "ceaser_selected_project_id",
  "ceaser_selected_agent_id",
  "ceaser_saved_responses",
  "ceaser_read_notifications",
  "ceaser_onboarding_complete",
  "ceaser_chat_seed",
  "ceaser_chat_autosend",
  "ceaser_project_file_ids",
  "ceaser_chat_agent_context",
  "ceaser_referral_code",
  "ceaser_recent_activity",
  "ceaser_preferences",
  "ceaser_commercial_cache_v1",
  "ceaser_favorite_projects",
  "ceaser_project_workflow_links",
  "ceaser_mission_control_cache_v1",
  "ceaser-agent-store",
  "ceaser-project-store",
  "ceaser-memory-store",
  "ceaser-file-automation-store",
  "ceaser-task-goal-store",
]

const SESSION_SESSION_STORAGE_KEYS = [
  "ceaser_desktop_auth_return",
  "ceaser_pending_plugin",
]

export function clearConsoleSessionState() {
  if (typeof window === "undefined") return
  clearAuthTokens()
  SESSION_LOCAL_STORAGE_KEYS.forEach((key) => window.localStorage.removeItem(key))
  SESSION_SESSION_STORAGE_KEYS.forEach((key) => window.sessionStorage.removeItem(key))
  window.dispatchEvent(new CustomEvent("ceaser:session-reset"))
  window.dispatchEvent(new CustomEvent("ceaser:profile-updated"))
}
