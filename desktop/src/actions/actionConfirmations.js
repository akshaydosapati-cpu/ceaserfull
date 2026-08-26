const confirmationActions = new Set([
  "create_folder",
  "rename_folder",
  "move_folder",
  "rename_file",
  "move_file",
  "clear_clipboard",
  "take_screenshot",
  "lock_computer",
  "shutdown_computer",
  "restart_computer",
  "sleep_computer",
  "restart_app",
])

function requiresConfirmation(action) {
  return confirmationActions.has(action)
}

function confirmationQuestion(intent) {
  const params = intent.parameters || {}
  if (intent.action === "create_folder") return `Create folder "${params.name}" in ${params.base || "Documents"}?`
  if (intent.action === "take_screenshot") return "Allow CEASER to take a screenshot now?"
  if (intent.action === "clear_clipboard") return "Clear clipboard contents?"
  if (intent.action === "lock_computer") return "Lock this computer now?"
  if (intent.action === "shutdown_computer") return "Shut down this computer now?"
  if (intent.action === "restart_computer") return "Restart this computer now?"
  if (intent.action === "sleep_computer") return "Put this computer to sleep now?"
  if (intent.action === "restart_app") return `Restart ${params.label || params.app || "this app"}?`
  if (intent.action?.startsWith("rename_")) return `Rename "${params.name || params.source || "this item"}"?`
  if (intent.action?.startsWith("move_")) return `Move "${params.name || params.source || "this item"}"?`
  return "Confirm this action before CEASER continues?"
}

module.exports = { confirmationQuestion, requiresConfirmation }
