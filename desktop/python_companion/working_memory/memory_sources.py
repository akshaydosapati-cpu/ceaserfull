from __future__ import annotations

import os
import re
from typing import Any

from core.schemas import ActionResult, CommandRequest, IntentResult
from working_memory.memory_store import MemoryStore


class DesktopSource:
    def update(self, store: MemoryStore, request: CommandRequest) -> None:
        context = request.context or {}
        foreground = context.get("foreground") or context.get("activeWindow") or {}
        active_app = foreground.get("process") or foreground.get("app") or context.get("active_app") or ""
        window_title = foreground.get("title") or context.get("active_window") or ""
        store.set("desktop", "active_app", active_app, ttl_seconds=90, source="desktop")
        store.set("desktop", "active_process", active_app, ttl_seconds=90, source="desktop")
        store.set("desktop", "active_window", window_title, ttl_seconds=90, source="desktop")
        if context.get("monitor"):
            store.set("desktop", "current_monitor", context.get("monitor"), ttl_seconds=90, source="desktop")
        if context.get("workspace"):
            store.set("desktop", "current_workspace", context.get("workspace"), ttl_seconds=90, source="desktop")


class ProjectSource:
    def update(self, store: MemoryStore, request: CommandRequest) -> None:
        context = request.context or {}
        folder = context.get("current_folder") or context.get("folder") or ""
        active_file = context.get("active_file") or context.get("selected_file") or ""
        project_name = context.get("active_project") or context.get("current_project") or context.get("project") or ""
        repository_name = context.get("active_repository") or context.get("repository") or context.get("repo") or ""
        branch = context.get("branch") or context.get("current_branch") or ""
        if project_name:
            store.set("project", "current_project", project_name, ttl_seconds=300, source="project")
        if repository_name:
            store.set("project", "repository", repository_name, ttl_seconds=300, source="project")
        if branch:
            store.set("project", "branch", branch, ttl_seconds=300, source="project")
        if folder:
            store.set("project", "current_folder", folder, ttl_seconds=300, source="project")
        if active_file:
            store.set("project", "selected_file", active_file, ttl_seconds=300, source="project")
            ext = os.path.splitext(active_file)[1].lower().strip(".")
            if ext:
                store.set("project", "current_language", ext, ttl_seconds=300, source="project")
        title = str((context.get("foreground") or context.get("activeWindow") or {}).get("title") or "")
        repo_match = re.search(r"([A-Za-z0-9_.-]+)\s*[-—]\s*(?:Visual Studio Code|VS Code)", title)
        if repo_match:
            store.set("project", "repository", repo_match.group(1), ttl_seconds=300, source="project")
            store.set("project", "current_project", repo_match.group(1), ttl_seconds=300, source="project")
            store.set("project", "current_editor", "VS Code", ttl_seconds=300, source="project")


class ConversationSource:
    def update_before(self, store: MemoryStore, request: CommandRequest) -> None:
        store.set("conversation", "last_command", request.normalized_text, ttl_seconds=1800, source="conversation")

    def update_after(self, store: MemoryStore, request: CommandRequest, intent: IntentResult, result: ActionResult) -> None:
        store.set("conversation", "previous_response", result.summary[:1200], ttl_seconds=1800, source="conversation")
        store.set("conversation", "last_capability", result.capability or intent.capability or "", ttl_seconds=1800, source="conversation")
        store.set("conversation", "conversation_summary", result.summary[:500], ttl_seconds=1800, source="conversation")
        if result.capability == "workflow.plan":
            workflow = (result.data or {}).get("workflow_result") or {}
            evidence = result.evidence or {}
            store.set("conversation", "active_workflow_id", evidence.get("workflow_id", ""), ttl_seconds=1800, source="workflow")
            store.set("conversation", "current_goal", workflow.get("goal", result.summary[:120]), ttl_seconds=1800, source="workflow")
            store.set("conversation", "latest_partial_result", workflow, ttl_seconds=1800, source="workflow")
        if result.status == "needs_input":
            store.set("conversation", "pending_clarification", {"question": result.summary}, ttl_seconds=600, source="conversation")
        if result.status == "needs_confirmation":
            store.set("conversation", "pending_confirmation", result.confirmation or {}, ttl_seconds=600, source="conversation")
        if (result.capability or "").startswith("memory."):
            store.set("conversation", "last_memory_action", result.capability or "", ttl_seconds=1800, source="memory")
            if result.capability == "memory.disable_session":
                store.set("conversation", "session_memory_disabled", True, source="memory")
            pending_memory = (result.data or {}).get("pending_memory_confirmation")
            if result.status == "needs_confirmation" and pending_memory:
                store.set("conversation", "pending_memory_confirmation", {"items": pending_memory}, ttl_seconds=600, source="memory")


class ClipboardSource:
    def update(self, store: MemoryStore, request: CommandRequest) -> None:
        context = request.context or {}
        clipboard = context.get("clipboard")
        if isinstance(clipboard, dict):
            safe = {key: clipboard.get(key) for key in ("type", "length", "preview") if key in clipboard}
            store.set("clipboard", "clipboard", safe, ttl_seconds=120, source="clipboard")


class ResourceSource:
    def update(self, store: MemoryStore, request: CommandRequest, result: ActionResult | None = None) -> None:
        context = request.context or {}
        resource = context.get("active_resource") or context.get("dropped_file") or {}
        if result and result.data.get("path"):
            resource = {"type": "file", "path": result.data.get("path")}
        if resource:
            store.set("resource", "active_resource", resource, source="resource")
        selection = context.get("selection")
        if isinstance(selection, dict):
            safe = {key: selection.get(key) for key in ("type", "length", "preview") if key in selection}
            store.set("resource", "current_selection", safe, ttl_seconds=45, source="resource")


class IntegrationSource:
    def update(self, store: MemoryStore, request: CommandRequest, result: ActionResult | None = None) -> None:
        context = request.context or {}
        integrations = context.get("connected_integrations")
        if isinstance(integrations, list):
            store.set("integration", "connected_integrations", [str(item) for item in integrations], ttl_seconds=300, source="integration")
        text = request.normalized_text.lower()
        if "github" in text or "repo" in text or "repository" in text:
            store.set("integration", "active_integration", "github", ttl_seconds=300, source="integration")
        if "notion" in text:
            store.set("integration", "active_integration", "notion", ttl_seconds=300, source="integration")
        if result:
            data = result.data or {}
            if data.get("repository"):
                store.set("integration", "github_repository", data.get("repository"), ttl_seconds=600, source="integration")
            if data.get("notion_page"):
                store.set("integration", "notion_page", data.get("notion_page"), ttl_seconds=600, source="integration")
