from __future__ import annotations

import time
from typing import Any, Literal

from pydantic import BaseModel, Field


PredictionType = Literal["next_capability", "next_workflow", "next_command"]
PreparationStatus = Literal["prepared", "cache_hit", "cache_miss", "skipped", "expired"]


class Prediction(BaseModel):
    id: str
    type: PredictionType
    label: str
    confidence: float
    evidence: list[str] = Field(default_factory=list)
    expires_at: float
    created_at: float = Field(default_factory=time.time)
    likely_capability: str = ""
    likely_workflow: str = ""
    likely_command: str = ""
    preparation_key: str = ""
    safe_read_only: bool = True


class PreparationTask(BaseModel):
    key: str
    kind: str
    description: str
    provider: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    read_only: bool = True
    ttl_seconds: int = 300


class PreparationResult(BaseModel):
    key: str
    status: PreparationStatus
    latency_ms: int = 0
    expires_at: float = 0.0
    cache_hit: bool = False
    data: dict[str, Any] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)


class PredictionContext(BaseModel):
    predictions: list[dict[str, Any]] = Field(default_factory=list)
    preparation: dict[str, Any] = Field(default_factory=dict)
    cache: dict[str, Any] = Field(default_factory=dict)
    summary: str = "no_prediction"
    generated_at: float = Field(default_factory=time.time)

    def as_context(self) -> dict[str, Any]:
        return self.model_dump() if hasattr(self, "model_dump") else self.dict()
