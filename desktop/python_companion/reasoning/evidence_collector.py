from __future__ import annotations

from typing import Any

from core.schemas import CapabilityDefinition, CommandRequest, CortexDecision, IntentResult


class EvidenceCollector:
    def collect(
        self,
        request: CommandRequest,
        decision: CortexDecision | None,
        intent: IntentResult,
        context: dict[str, Any],
        capability: CapabilityDefinition | None,
        workflow_plan=None,
    ) -> dict[str, Any]:
        working = context.get("working_memory") or context.get("context_snapshot") or {}
        world = context.get("world_model") or {}
        long_term = context.get("long_term_memory") or {}
        references = context.get("references") or {}
        workflow = {}
        if workflow_plan is not None:
            workflow = workflow_plan.model_dump() if hasattr(workflow_plan, "model_dump") else workflow_plan.dict()
        return {
            "request_id": request.request_id,
            "session_id": request.session_id,
            "route": intent.route,
            "intent": intent.intent,
            "capability": intent.capability,
            "decision_reason": decision.reason if decision else "",
            "active_project": working.get("current_project", ""),
            "active_file": working.get("selected_file", ""),
            "active_resource": working.get("active_resource", {}),
            "repository": working.get("repository") or working.get("github_repository") or "",
            "branch": working.get("branch", ""),
            "unsaved_document": bool(working.get("unsaved_document") or (working.get("active_resource") or {}).get("unsaved")),
            "world_current_project": (world.get("current_project") or {}).get("name", ""),
            "world_current_repository": (world.get("current_repository") or {}).get("name", ""),
            "world_ambiguity_candidates": intent.entities.get("ambiguity_candidates") or [],
            "resolved_reference": references.get("resolved_reference") or intent.entities.get("resolved_reference"),
            "follow_up_detected": bool(references.get("follow_up_detected")),
            "long_term_memories": long_term.get("memories", []),
            "capability_risk_level": capability.risk_level if capability else "low",
            "capability_requires_confirmation": capability.requires_confirmation if capability else False,
            "protected_branch": bool((request.context or {}).get("protected_branch") or working.get("protected_branch")),
            "preview_resource": (request.context or {}).get("preview_resource") or working.get("preview_resource") or {},
            "workflow_plan": workflow,
            "reasoning_confirmation_approved": bool(context.get("reasoning_confirmation_approved")),
            "approved_workflow_step_id": context.get("approved_workflow_step_id", ""),
        }
