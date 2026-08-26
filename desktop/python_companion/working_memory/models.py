from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


MemoryCategory = Literal["desktop", "project", "conversation", "resource", "integration", "clipboard"]


class MemoryItem(BaseModel):
    category: MemoryCategory
    key: str
    value: Any
    timestamp: float
    expires_at: float | None = None
    source: str = ""


class ContextSnapshot(BaseModel):
    active_app: str = ""
    active_window: str = ""
    active_process: str = ""
    current_monitor: str = ""
    current_workspace: str = ""
    current_project: str = ""
    current_folder: str = ""
    repository: str = ""
    branch: str = ""
    selected_file: str = ""
    current_language: str = ""
    current_editor: str = ""
    conversation_summary: str = ""
    previous_response: str = ""
    last_command: str = ""
    last_capability: str = ""
    pending_clarification: dict[str, Any] | None = None
    pending_confirmation: dict[str, Any] | None = None
    session_memory_disabled: bool = False
    pending_memory_confirmation: dict[str, Any] | None = None
    last_memory_action: str = ""
    current_goal: str = ""
    active_workflow_id: str = ""
    current_step: str = ""
    latest_partial_result: dict[str, Any] = Field(default_factory=dict)
    active_resource: dict[str, Any] = Field(default_factory=dict)
    clipboard: dict[str, Any] = Field(default_factory=dict)
    current_selection: dict[str, Any] = Field(default_factory=dict)
    connected_integrations: list[str] = Field(default_factory=list)
    active_integration: str = ""
    github_repository: str = ""
    notion_page: str = ""
    recent_events: list[dict[str, Any]] = Field(default_factory=list)
    notification_cards: list[dict[str, Any]] = Field(default_factory=list)
    timestamp: float = 0.0
    expires_at: float | None = None

    def as_context(self) -> dict[str, Any]:
        try:
            return self.model_dump()
        except AttributeError:
            return self.dict()
