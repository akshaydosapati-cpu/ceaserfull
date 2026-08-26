from __future__ import annotations

from awareness.models import AwarenessEvent


class ImportanceScorer:
    BASE_SCORES = {
        "active_application_changed": 0.12,
        "active_window_changed": 0.1,
        "clipboard_updated": 0.08,
        "file_created": 0.24,
        "file_renamed": 0.28,
        "file_deleted": 0.42,
        "screenshot_taken": 0.22,
        "usb_connected": 0.35,
        "network_down": 0.9,
        "network_changed": 0.48,
        "battery_low": 0.82,
        "locked": 0.2,
        "unlocked": 0.26,
        "sleep": 0.35,
        "resume": 0.55,
        "git_repository_changed": 0.45,
        "new_commit": 0.55,
        "build_completed": 0.45,
        "build_failed": 0.9,
        "tests_finished": 0.45,
        "tests_failed": 0.88,
        "github_sync_complete": 0.46,
        "github_issue_assigned": 0.82,
        "pull_request_merged": 0.76,
        "notion_page_updated": 0.55,
        "notion_database_changed": 0.62,
        "download_completed": 0.58,
        "workflow_finished": 0.74,
        "workflow_completed": 0.74,
        "task_completed": 0.7,
        "task_failed": 0.86,
        "update_available": 0.48,
    }

    def score(self, event: AwarenessEvent, context: dict | None = None) -> float:
        context = context or {}
        score = self.BASE_SCORES.get(event.type, 0.3)
        working = context.get("working_memory") or context.get("context_snapshot") or {}
        active_app = str(working.get("active_app") or "").lower()
        if event.category == "development" and ("code" in active_app or "visual studio" in active_app):
            score += 0.08
        if event.category == "integration" and event.payload.get("assigned_to_user"):
            score += 0.12
        if event.payload.get("failed") or event.payload.get("error"):
            score += 0.18
        if event.payload.get("current_project") and working.get("current_project") and str(event.payload.get("current_project")).lower() == str(working.get("current_project")).lower():
            score += 0.08
        return max(0.0, min(1.0, score))
