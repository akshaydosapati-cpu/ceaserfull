from __future__ import annotations

import time
from typing import Any, Literal

from pydantic import BaseModel, Field

from core.schemas import ActionResult, RiskLevel


WorkflowStatus = Literal[
    "PLANNED",
    "WAITING_FOR_CONFIRMATION",
    "RUNNING",
    "PAUSED",
    "COMPLETED",
    "PARTIAL",
    "FAILED",
    "CANCELLED",
]


class WorkflowStep(BaseModel):
    step_id: str
    capability: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = "low"
    requires_confirmation: bool = False
    timeout_seconds: int = 20
    retry_limit: int = 0
    optional: bool = False
    expected_output: str = ""


class WorkflowPlan(BaseModel):
    workflow_id: str
    request_id: str
    session_id: str
    goal: str
    summary: str
    steps: list[WorkflowStep]
    created_at: float = Field(default_factory=time.time)
    status: WorkflowStatus = "PLANNED"
    risk_level: RiskLevel = "low"
    requires_confirmation: bool = False
    planner_evidence: dict[str, Any] = Field(default_factory=dict)


class StepResult(BaseModel):
    step_id: str
    capability: str
    status: str
    result: ActionResult | None = None
    attempts: int = 0
    skipped: bool = False
    warning: str = ""


class WorkflowRun(BaseModel):
    workflow_id: str
    plan: WorkflowPlan
    status: WorkflowStatus = "PLANNED"
    step_results: list[StepResult] = Field(default_factory=list)
    cancelled: bool = False
    pending_step_id: str = ""
    pending_confirmation_id: str = ""
    approved_steps: list[str] = Field(default_factory=list)
    started_at: float | None = None
    completed_at: float | None = None


class WorkflowResult(BaseModel):
    status: WorkflowStatus
    goal: str
    completed_steps: list[str] = Field(default_factory=list)
    failed_steps: list[str] = Field(default_factory=list)
    skipped_steps: list[str] = Field(default_factory=list)
    partial_results: list[dict[str, Any]] = Field(default_factory=list)
    created_resources: list[dict[str, Any]] = Field(default_factory=list)
    modified_resources: list[dict[str, Any]] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    spoken_response: str = ""
    display_summary: str = ""
    verified: bool = False


class PendingConfirmation(BaseModel):
    confirmation_id: str
    workflow_id: str
    step_id: str
    capability: str
    arguments: dict[str, Any]
    risk_level: RiskLevel
    expires_at: float
    preview: str
