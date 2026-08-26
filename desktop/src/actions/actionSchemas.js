const INTENT_TYPES = {
  DESKTOP: "desktop_action",
  AGENT: "agent_action",
  CHAT: "chat_action",
  IDENTITY: "identity_action",
  BLOCKED: "blocked_action",
}

const RISK = {
  LOW: "low",
  MEDIUM: "medium",
  HIGH: "high",
  BLOCKED: "blocked",
}

module.exports = { INTENT_TYPES, RISK }
