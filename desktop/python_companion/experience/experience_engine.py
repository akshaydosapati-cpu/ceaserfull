from __future__ import annotations

import hashlib
import time
from typing import Any

from core.schemas import ActionResult, CommandRequest, IntentResult
from experience.experience_store import ExperienceStore
from experience.models import ExperienceContext, ExperienceOutcome
from experience.pattern_extractor import ExperiencePatternExtractor


class ExperienceEngine:
    """Learns from outcomes, not conversations.

    It records operational experience for later prediction/adaptation without
    storing private content or executing anything.
    """

    def __init__(self, store: ExperienceStore | None = None) -> None:
        self.store = store or ExperienceStore()
        self.patterns = ExperiencePatternExtractor()

    def record_outcome(self, request: CommandRequest, intent: IntentResult, result: ActionResult, *, latency_ms: int, context: dict[str, Any] | None = None) -> ExperienceOutcome:
        context = context or {}
        evidence = result.evidence or {}
        working = context.get("working_memory") or context.get("context_snapshot") or {}
        status = self._status(result)
        outcome = ExperienceOutcome(
            id=self._id(request.request_id, result.capability or intent.capability or ""),
            user_id=request.user_id,
            session_id=request.session_id,
            request_id=request.request_id,
            source=request.source,
            route=intent.route,
            intent=intent.intent,
            capability=result.capability or intent.capability or "unknown",
            command_signature=self.patterns.command_signature(request.normalized_text),
            status=status,
            success=status == "success",
            verified=result.verified,
            latency_ms=latency_ms,
            clarification_needed=result.status == "needs_input",
            confirmation_state=self._confirmation_state(request, result),
            workflow_id=str(evidence.get("workflow_id") or ""),
            workflow_type=str(evidence.get("workflow_type") or ""),
            active_project=str(working.get("current_project") or ""),
            active_app=str(working.get("active_app") or ""),
            hour_of_day=time.localtime().tm_hour,
            evidence=self._safe_evidence(evidence),
        )
        self.store.save_outcome(outcome)
        for pattern in self.patterns.patterns_for(outcome):
            saved = self.store.save_pattern(pattern)
            saved.confidence = min(1.0, max(saved.confidence, saved.count / 5))
        result.evidence.setdefault("experience_outcome_id", outcome.id)
        result.evidence.setdefault("experience_status", outcome.status)
        result.evidence.setdefault("experience_capability_success_rate", self.store.capabilities[outcome.capability].success_rate)
        return outcome

    def as_context(self, limit: int = 6) -> dict[str, Any]:
        capability_success = {name: round(item.success_rate, 3) for name, item in self.store.capabilities.items()}
        repeated_commands = [self._dump(pattern) for pattern in self.store.patterns_by_type("repeated_command", limit) if pattern.count >= 2]
        repeated_workflows = [self._dump(pattern) for pattern in self.store.patterns_by_type("repeated_workflow", limit) if pattern.count >= 2]
        latency_hotspots = [
            {"capability": item.capability, "average_latency_ms": int(item.average_latency_ms), "attempts": item.attempts}
            for item in sorted(self.store.capabilities.values(), key=lambda cap: cap.average_latency_ms, reverse=True)
            if item.average_latency_ms >= 3000
        ][:limit]
        clarification_hotspots = [
            {"capability": item.capability, "clarifications": item.clarification_count, "attempts": item.attempts}
            for item in sorted(self.store.capabilities.values(), key=lambda cap: cap.clarification_count, reverse=True)
            if item.clarification_count
        ][:limit]
        successes = [self._dump(outcome) for outcome in self.store.recent(limit, success=True)]
        failures = [self._dump(outcome) for outcome in self.store.recent(limit, success=False)]
        latest = successes[0]["capability"] if successes else failures[0]["capability"] if failures else ""
        return ExperienceContext(
            capability_success=capability_success,
            repeated_commands=repeated_commands,
            repeated_workflows=repeated_workflows,
            latency_hotspots=latency_hotspots,
            clarification_hotspots=clarification_hotspots,
            recent_successes=successes,
            recent_failures=failures,
            latest_experience_summary=latest,
        ).as_context()

    def _status(self, result: ActionResult):
        if result.status == "completed" and result.verified:
            return "success"
        if result.status == "partial":
            return "partial"
        if result.status == "needs_input":
            return "clarification"
        if result.status == "needs_confirmation":
            return "confirmation"
        if result.status == "cancelled":
            return "cancelled"
        return "failure"

    def _confirmation_state(self, request: CommandRequest, result: ActionResult) -> str:
        text = request.normalized_text.lower().strip()
        if result.status == "needs_confirmation":
            return "requested"
        if text in {"yes", "confirm", "confirmed", "go ahead", "do it", "approve"}:
            return "accepted"
        if text in {"cancel", "no", "not now", "stop", "abort"}:
            return "rejected"
        return ""

    def _safe_evidence(self, evidence: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "workflow_id",
            "workflow_type",
            "planner_selected",
            "cortex_destination",
            "cortex_reason",
            "reasoning_decision",
            "reasoning_confidence",
            "conflicts_detected",
            "clarification_reason",
        }
        return {key: evidence.get(key) for key in allowed if key in evidence}

    def _id(self, request_id: str, capability: str) -> str:
        return "exp_" + hashlib.sha256(f"{request_id}:{capability}:{time.time()}".encode("utf-8")).hexdigest()[:18]

    def _dump(self, item) -> dict[str, Any]:
        return item.model_dump() if hasattr(item, "model_dump") else item.dict()
