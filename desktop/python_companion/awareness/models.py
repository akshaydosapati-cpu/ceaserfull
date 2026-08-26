from __future__ import annotations

import time
from typing import Any, Literal

from pydantic import BaseModel, Field


EventCategory = Literal["desktop", "development", "integration", "system"]
EventStatus = Literal["queued", "ignored", "delayed", "notified"]
AwarenessAction = Literal["notify", "ignore", "delay"]


class AwarenessEvent(BaseModel):
    id: str
    category: EventCategory
    type: str
    source: str
    title: str
    summary: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    dedupe_key: str = ""
    importance: float = 0.0
    created_at: float = Field(default_factory=time.time)
    expires_at: float | None = None
    status: EventStatus = "queued"
    metadata: dict[str, Any] = Field(default_factory=dict)


class AwarenessDecision(BaseModel):
    event_id: str
    action: AwarenessAction
    importance: float
    reason: str
    notification_title: str = ""
    notification_summary: str = ""
    should_speak: bool = False
    delay_seconds: int = 0
    evidence: dict[str, Any] = Field(default_factory=dict)


class AwarenessContext(BaseModel):
    recent_events: list[dict[str, Any]] = Field(default_factory=list)
    notification_cards: list[dict[str, Any]] = Field(default_factory=list)
    delayed_events: list[dict[str, Any]] = Field(default_factory=list)
    ignored_count: int = 0
    high_importance_count: int = 0
    latest_event_summary: str = ""

    def as_context(self) -> dict[str, Any]:
        return self.model_dump() if hasattr(self, "model_dump") else self.dict()
