from __future__ import annotations

import time
from typing import Any, Literal

from pydantic import BaseModel, Field


OutcomeStatus = Literal["success", "failure", "partial", "clarification", "confirmation", "cancelled"]


class ExperienceOutcome(BaseModel):
    id: str
    user_id: str = ""
    session_id: str
    request_id: str
    source: str
    route: str
    intent: str
    capability: str
    command_signature: str
    status: OutcomeStatus
    success: bool = False
    verified: bool = False
    latency_ms: int = 0
    clarification_needed: bool = False
    confirmation_state: str = ""
    workflow_id: str = ""
    workflow_type: str = ""
    active_project: str = ""
    active_app: str = ""
    hour_of_day: int = 0
    created_at: float = Field(default_factory=time.time)
    evidence: dict[str, Any] = Field(default_factory=dict)


class CapabilityExperience(BaseModel):
    capability: str
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    clarification_count: int = 0
    confirmation_count: int = 0
    average_latency_ms: float = 0.0
    last_used_at: float = 0.0

    @property
    def success_rate(self) -> float:
        return self.successes / self.attempts if self.attempts else 0.0


class ExperiencePattern(BaseModel):
    key: str
    type: str
    label: str
    count: int = 0
    confidence: float = 0.0
    last_seen_at: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExperienceContext(BaseModel):
    capability_success: dict[str, float] = Field(default_factory=dict)
    repeated_commands: list[dict[str, Any]] = Field(default_factory=list)
    repeated_workflows: list[dict[str, Any]] = Field(default_factory=list)
    latency_hotspots: list[dict[str, Any]] = Field(default_factory=list)
    clarification_hotspots: list[dict[str, Any]] = Field(default_factory=list)
    recent_successes: list[dict[str, Any]] = Field(default_factory=list)
    recent_failures: list[dict[str, Any]] = Field(default_factory=list)
    latest_experience_summary: str = ""

    def as_context(self) -> dict[str, Any]:
        return self.model_dump() if hasattr(self, "model_dump") else self.dict()
