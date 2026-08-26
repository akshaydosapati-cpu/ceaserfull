from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


CommandSource = Literal["voice", "typed", "hotkey", "overlay", "automation", "integration"]
CommandRoute = Literal["desktop", "backend_ai", "integration", "workflow", "knowledge", "memory", "conversation", "unsupported"]
ActionStatus = Literal["completed", "failed", "partial", "needs_input", "needs_confirmation", "cancelled"]
RiskLevel = Literal["low", "medium", "high", "blocked"]


class CommandRequest(BaseModel):
    request_id: str
    user_id: str = ""
    session_id: str
    source: CommandSource
    raw_text: str
    normalized_text: str
    context: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IntentResult(BaseModel):
    intent: str
    capability: str | None = None
    confidence: float
    entities: dict[str, Any] = Field(default_factory=dict)
    route: CommandRoute
    requires_clarification: bool = False
    clarification_question: str | None = None


class CortexDecision(BaseModel):
    destination: CommandRoute
    intent: IntentResult
    reason: str
    needs_clarification: bool = False
    clarification_question: str | None = None
    signals: dict[str, Any] = Field(default_factory=dict)


class ActionResult(BaseModel):
    status: ActionStatus
    capability: str | None = None
    summary: str
    spoken_response: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    verified: bool = False
    retryable: bool = False
    error_code: str | None = None
    confirmation: dict[str, Any] | None = None

    @classmethod
    def from_legacy(cls, payload: dict[str, Any], capability: str | None = None) -> "ActionResult":
        legacy_status = str(payload.get("status") or "completed")
        status_map = {
            "error": "failed",
            "empty": "needs_input",
            "needs_context": "needs_input",
            "needs_clarification": "needs_input",
            "resting": "cancelled",
        }
        status = status_map.get(legacy_status, legacy_status)
        if status not in {"completed", "failed", "partial", "needs_input", "needs_confirmation", "cancelled"}:
            status = "failed"
        summary = str(payload.get("message") or payload.get("summary") or "")
        verified = bool(payload.get("verified"))
        if status == "completed":
            verified = payload.get("verified", True) is not False
        return cls(
            status=status,  # type: ignore[arg-type]
            capability=capability or payload.get("capability"),
            summary=summary,
            spoken_response=payload.get("spoken_response") or summary,
            data={key: value for key, value in payload.items() if key not in {"status", "message", "summary"}},
            evidence=payload.get("evidence") or {},
            warnings=payload.get("warnings") or [],
            verified=verified,
            retryable=bool(payload.get("retryable")),
            error_code=payload.get("error_code") or payload.get("error"),
        )

    def to_legacy(self) -> dict[str, Any]:
        legacy_status = {
            "failed": "error",
            "needs_input": "needs_clarification",
            "needs_confirmation": "needs_clarification",
        }.get(self.status, self.status)
        try:
            dumped = self.model_dump()
        except AttributeError:
            dumped = self.dict()
        payload = {
            "status": legacy_status,
            "message": self.summary,
            "capability": self.capability,
            "spoken_response": self.spoken_response,
            "verified": self.verified,
            "evidence": self.evidence,
            "warnings": self.warnings,
            "error_code": self.error_code,
            "action_result": dumped,
        }
        payload.update(self.data)
        return payload


class CapabilityDefinition(BaseModel):
    name: str
    description: str
    handler: str
    route: str
    risk_level: RiskLevel
    requires_confirmation: bool = False
    requires_internet: bool = False
    required_permissions: list[str] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = 20
    category: str = "general"
    display_name: str = ""
    output_schema: dict[str, Any] = Field(default_factory=dict)
    confirmation_policy: str = "none"
    local_execution_allowed: bool = True
    remote_execution_allowed: bool = False
    required_os_features: list[str] = Field(default_factory=list)
    required_hardware: list[str] = Field(default_factory=list)
    availability_probe: str = "always"
    verification_handler: str = ""
    cancellation_supported: bool = False
    idempotent: bool = False
    activity_event_type: str = "capability"


class IpcV2Request(BaseModel):
    version: str = "2.0"
    id: str
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class IpcV2Event(BaseModel):
    version: str = "2.0"
    type: str = "event"
    event: str
    payload: dict[str, Any] = Field(default_factory=dict)
