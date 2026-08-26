from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from core.schemas import RiskLevel


ReasoningDecisionType = Literal["proceed", "clarify", "suggest_alternative", "block", "request_confirmation"]


class ReasoningDecision(BaseModel):
    decision: ReasoningDecisionType
    confidence: float
    reason: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    conflicts: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    safer_alternative: str = ""
    requires_clarification: bool = False
    clarification_question: str = ""
    recommended_risk_level: RiskLevel = "low"
    allowed_to_execute: bool = True


class ReasoningInput(BaseModel):
    request_text: str
    route: str
    intent: str
    capability: str
    capability_risk_level: RiskLevel = "low"
    capability_requires_confirmation: bool = False
    context: dict[str, Any] = Field(default_factory=dict)
    workflow_plan: dict[str, Any] | None = None
    security: dict[str, Any] = Field(default_factory=dict)
