from __future__ import annotations

import time
from typing import Any, Literal

from pydantic import BaseModel, Field


EntityType = Literal[
    "user_session",
    "project",
    "local_workspace",
    "repository",
    "file",
    "folder",
    "document",
    "webpage",
    "notion_page",
    "integration",
    "conversation",
    "task",
    "goal",
]

RelationshipType = Literal[
    "active_in",
    "belongs_to",
    "stored_in",
    "connected_to",
    "derived_from",
    "discussed_in",
    "related_to",
    "current_for",
    "opened_from",
    "associated_with",
    "working_on",
    "next_step_for",
]


class WorldEntity(BaseModel):
    id: str
    type: EntityType
    name: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    source: str = ""
    confidence: float = 1.0
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    expires_at: float | None = None


class WorldRelationship(BaseModel):
    id: str
    source_id: str
    target_id: str
    type: RelationshipType
    source: str = ""
    confidence: float = 1.0
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    expires_at: float | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class EntityResolution(BaseModel):
    entity: WorldEntity | None = None
    confidence: float = 0.0
    evidence: dict[str, Any] = Field(default_factory=dict)
    ambiguity_candidates: list[WorldEntity] = Field(default_factory=list)
    reason: str = ""

    @property
    def ambiguous(self) -> bool:
        return bool(self.ambiguity_candidates) and self.entity is None


class WorldQueryResult(BaseModel):
    entities: list[WorldEntity] = Field(default_factory=list)
    relationships: list[WorldRelationship] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
