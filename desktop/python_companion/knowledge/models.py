from __future__ import annotations

import time
from typing import Any, Literal

from pydantic import BaseModel, Field


KnowledgeCategory = Literal[
    "architecture",
    "capability",
    "command_example",
    "workflow",
    "schema",
    "safety_rule",
    "documentation",
    "faq",
    "integration",
    "troubleshooting",
]
TrustLevel = Literal["authoritative", "trusted", "informational", "deprecated"]


class KnowledgeItem(BaseModel):
    id: str
    category: KnowledgeCategory
    title: str
    content: str
    summary: str = ""
    keywords: list[str] = Field(default_factory=list)
    source_path: str = ""
    source_type: str = ""
    trust_level: TrustLevel = "trusted"
    version: str = "1"
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    content_hash: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSource(BaseModel):
    source_path: str
    source_type: str
    trust_level: TrustLevel = "trusted"
    category: KnowledgeCategory = "documentation"


class KnowledgeQuery(BaseModel):
    text: str
    category: KnowledgeCategory | None = None
    include_deprecated: bool = False
    limit: int = 5


class KnowledgeMatch(BaseModel):
    item: KnowledgeItem
    score: float
    confidence: float
    matched_terms: list[str] = Field(default_factory=list)


class KnowledgeResponse(BaseModel):
    status: Literal["completed", "not_found", "partial", "failed"]
    query: str
    summary: str
    matches: list[KnowledgeMatch] = Field(default_factory=list)
    confidence: float = 0.0
    sources: list[str] = Field(default_factory=list)
    ambiguity: bool = False
    warnings: list[str] = Field(default_factory=list)
