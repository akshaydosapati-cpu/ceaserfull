from __future__ import annotations

import re
from typing import Any

from core.schemas import CapabilityDefinition, CommandRequest, CortexDecision, IntentResult, RiskLevel
from planning.models import WorkflowPlan
from reasoning.alternative_generator import AlternativeGenerator
from reasoning.conflict_detector import ConflictDetector
from reasoning.evidence_collector import EvidenceCollector
from reasoning.models import ReasoningDecision
from reasoning.sufficiency_checker import SufficiencyChecker


class ReasoningCortex:
    """Evidence-aware deterministic judgment layer.

    This component decides whether to proceed, clarify, suggest an alternative,
    block, or request confirmation. It does not execute capabilities.
    """

    def __init__(self) -> None:
        self.evidence_collector = EvidenceCollector()
        self.conflicts = ConflictDetector()
        self.sufficiency = SufficiencyChecker()
        self.alternatives = AlternativeGenerator()

    def evaluate(
        self,
        request: CommandRequest,
        decision: CortexDecision | None,
        intent: IntentResult,
        context: dict[str, Any],
        capability: CapabilityDefinition | None,
        workflow_plan: WorkflowPlan | None = None,
    ) -> ReasoningDecision:
        text = request.normalized_text or request.raw_text or ""
        evidence = self.evidence_collector.collect(request, decision, intent, context, capability, workflow_plan)
        risk = self._risk(capability, workflow_plan)
        evidence["recommended_risk_level"] = risk

        if capability and capability.risk_level == "blocked":
            return self._block("hard_security_block", evidence, risk, "That action is blocked for safety.")

        missing = self.sufficiency.missing_information(text, evidence)
        conflicts = self.conflicts.detect(text, evidence)
        if evidence.get("protected_branch") and "push" in text.lower():
            conflicts.append("protected_branch")
        if evidence.get("unsaved_document") and re.search(r"\b(close|quit|exit)\b", text.lower()):
            conflicts.append("unsaved_document")

        if intent.confidence < 0.55 or intent.route == "unsupported":
            return self._clarify("low_confidence_resolution", evidence, conflicts, missing or ["clear_command"], "I am not confident enough to execute that. What should I do exactly?", risk)

        if self._workflow_drift(text, evidence, workflow_plan):
            return self._block("workflow_plan_drift", evidence, risk, "The workflow plan no longer matches the requested target.", conflicts + ["workflow_plan_drift"])

        if missing:
            question = self._question_for_missing(missing)
            alternative = self.alternatives.safer_alternative(text, conflicts, missing)
            return self._clarify("missing_required_information", evidence, conflicts, missing, question, risk, alternative)

        if self._destructive(text, capability):
            alternative = self.alternatives.safer_alternative(text, conflicts, missing)
            return ReasoningDecision(
                decision="request_confirmation",
                confidence=0.9,
                reason="destructive_action_requires_confirmation",
                evidence=evidence,
                conflicts=conflicts,
                safer_alternative=alternative,
                recommended_risk_level="high",
                allowed_to_execute=False,
                clarification_question="Please confirm before I make this destructive change.",
            )

        alternative = self.alternatives.safer_alternative(text, conflicts, missing)
        if "protected_branch" in conflicts or "user_requested_no_save_but_plan_contains_save" in conflicts:
            return ReasoningDecision(
                decision="suggest_alternative",
                confidence=0.88,
                reason="safer_alternative_available",
                evidence=evidence,
                conflicts=conflicts,
                safer_alternative=alternative,
                recommended_risk_level=risk,
                allowed_to_execute=False,
            )

        if capability and (capability.requires_confirmation or capability.risk_level in {"medium", "high"}) and not evidence.get("reasoning_confirmation_approved"):
            return ReasoningDecision(
                decision="request_confirmation",
                confidence=0.86,
                reason="capability_requires_confirmation",
                evidence=evidence,
                conflicts=conflicts,
                safer_alternative=alternative,
                recommended_risk_level=risk,
                allowed_to_execute=False,
                clarification_question="Please confirm before I continue.",
            )

        return ReasoningDecision(
            decision="proceed",
            confidence=0.94 if self._fast_path(intent, capability, text) else 0.82,
            reason="low_risk_fast_path" if self._fast_path(intent, capability, text) else "sufficient_evidence",
            evidence=evidence,
            conflicts=conflicts,
            safer_alternative=alternative,
            recommended_risk_level=risk,
            allowed_to_execute=True,
        )

    def _fast_path(self, intent: IntentResult, capability: CapabilityDefinition | None, text: str) -> bool:
        if not capability or capability.risk_level != "low" or capability.requires_confirmation:
            return False
        return bool(intent.confidence >= 0.85 and not re.search(r"\b(it|this|that|delete|remove|push|overwrite)\b", text.lower()))

    def _risk(self, capability: CapabilityDefinition | None, workflow_plan: WorkflowPlan | None) -> RiskLevel:
        if workflow_plan and workflow_plan.risk_level != "low":
            return workflow_plan.risk_level
        return capability.risk_level if capability else "low"

    def _destructive(self, text: str, capability: CapabilityDefinition | None) -> bool:
        lowered = text.lower()
        if capability and capability.risk_level == "high":
            return True
        return bool(re.search(r"\b(delete|remove|wipe|erase|overwrite|format)\b", lowered))

    def _workflow_drift(self, text: str, evidence: dict[str, Any], workflow_plan: WorkflowPlan | None) -> bool:
        if not workflow_plan:
            return False
        lowered = text.lower()
        if "clinilocker" in lowered:
            step_text = " ".join(str(step.arguments) for step in workflow_plan.steps).lower()
            return bool(step_text and "clinilocker" not in step_text)
        return False

    def _question_for_missing(self, missing: list[str]) -> str:
        if "repository" in missing:
            return "Which repository should I use?"
        if "active_resource" in missing:
            return "Which file or resource do you mean?"
        if "project" in missing:
            return "Which project should I use?"
        return "What information should I use?"

    def _clarify(self, reason: str, evidence: dict[str, Any], conflicts: list[str], missing: list[str], question: str, risk: RiskLevel, alternative: str = "") -> ReasoningDecision:
        return ReasoningDecision(
            decision="clarify",
            confidence=0.84,
            reason=reason,
            evidence=evidence,
            conflicts=conflicts,
            missing_information=missing,
            safer_alternative=alternative,
            requires_clarification=True,
            clarification_question=question,
            recommended_risk_level=risk,
            allowed_to_execute=False,
        )

    def _block(self, reason: str, evidence: dict[str, Any], risk: RiskLevel, summary: str, conflicts: list[str] | None = None) -> ReasoningDecision:
        return ReasoningDecision(
            decision="block",
            confidence=0.96,
            reason=reason,
            evidence=evidence,
            conflicts=conflicts or [reason],
            safer_alternative="",
            recommended_risk_level=risk,
            allowed_to_execute=False,
            clarification_question=summary,
        )
