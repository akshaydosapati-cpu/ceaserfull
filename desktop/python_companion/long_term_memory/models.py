from __future__ import annotations

import time
from typing import Any, Literal

from pydantic import BaseModel, Field


LongTermMemoryType = Literal["preference", "project", "goal", "episodic", "relationship", "workflow_preference"]
MemoryStatus = Literal["active", "pending_confirmation", "deleted", "rejected"]


class LongTermMemoryItem(BaseModel):
    id: str
    user_id: str
    type: LongTermMemoryType
    content: str
    structured_data: dict[str, Any] = Field(default_factory=dict)
    source: str = ""
    confidence: float = 0.0
    importance: float = 0.0
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    last_used_at: float | None = None
    expires_at: float | None = None
    user_confirmed: bool = False
    sensitive: bool = False
    status: MemoryStatus = "active"


class MemoryCandidate(BaseModel):
    type: LongTermMemoryType
    content: str
    structured_data: dict[str, Any] = Field(default_factory=dict)
    source: str = ""
    confidence: float = 0.0
    importance: float = 0.0
    requires_confirmation: bool = False
    sensitive: bool = False
    reason: str = ""


class MemoryQuery(BaseModel):
    user_id: str
    text: str = ""
    memory_type: LongTermMemoryType | None = None
    limit: int = 5


class MemoryRetrievalResult(BaseModel):
    memories: list[LongTermMemoryItem] = Field(default_factory=list)
    confidence: float = 0.0
    reason: str = ""
