from __future__ import annotations

import time

from working_memory.memory_store import MemoryStore
from working_memory.models import ContextSnapshot


def build_context_snapshot(store: MemoryStore) -> ContextSnapshot:
    desktop = store.category("desktop")
    project = store.category("project")
    conversation = store.category("conversation")
    resource = store.category("resource")
    clipboard = store.category("clipboard")
    integration = store.category("integration")
    return ContextSnapshot(
        active_app=desktop.get("active_app", ""),
        active_window=desktop.get("active_window", ""),
        active_process=desktop.get("active_process", ""),
        current_monitor=desktop.get("current_monitor", ""),
        current_workspace=desktop.get("current_workspace", ""),
        current_project=project.get("current_project", ""),
        current_folder=project.get("current_folder", ""),
        repository=project.get("repository", ""),
        branch=project.get("branch", ""),
        selected_file=project.get("selected_file", ""),
        current_language=project.get("current_language", ""),
        current_editor=project.get("current_editor", ""),
        conversation_summary=conversation.get("conversation_summary", ""),
        previous_response=conversation.get("previous_response", ""),
        last_command=conversation.get("last_command", ""),
        last_capability=conversation.get("last_capability", ""),
        pending_clarification=conversation.get("pending_clarification"),
        pending_confirmation=conversation.get("pending_confirmation"),
        session_memory_disabled=bool(conversation.get("session_memory_disabled", False)),
        pending_memory_confirmation=conversation.get("pending_memory_confirmation"),
        last_memory_action=conversation.get("last_memory_action", ""),
        current_goal=conversation.get("current_goal", ""),
        active_workflow_id=conversation.get("active_workflow_id", ""),
        current_step=conversation.get("current_step", ""),
        latest_partial_result=conversation.get("latest_partial_result", {}),
        active_resource=resource.get("active_resource", {}),
        clipboard=clipboard.get("clipboard", {}),
        current_selection=resource.get("current_selection", {}),
        connected_integrations=integration.get("connected_integrations", []),
        active_integration=integration.get("active_integration", ""),
        github_repository=integration.get("github_repository", ""),
        notion_page=integration.get("notion_page", ""),
        timestamp=time.time(),
    )
