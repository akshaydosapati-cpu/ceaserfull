from __future__ import annotations

from capabilities.registry import build_default_registry
from core.command_service import CommandService
from core.schemas import CapabilityDefinition, CommandRequest, CortexDecision, IntentResult
from conversation.context_resolver import WorldContextResolver
from long_term_memory.memory_manager import LongTermMemoryManager
from long_term_memory.memory_store import LocalJsonMemoryStore
from planning.models import WorkflowPlan, WorkflowStep
from reasoning.reasoning_cortex import ReasoningCortex


def make_request(text: str, *, context: dict | None = None) -> CommandRequest:
    return CommandRequest(
        request_id=f"req-{abs(hash(text)) % 999999}",
        user_id="user-a",
        session_id="stage12",
        source="typed",
        raw_text=text,
        normalized_text=text,
        context=context or {},
    )


def make_decision(intent: IntentResult, reason: str = "test") -> CortexDecision:
    return CortexDecision(destination=intent.route, intent=intent, reason=reason, signals={})


def evaluate(text: str, intent: IntentResult, context: dict | None = None, capability=None, plan=None):
    registry = build_default_registry()
    cap = capability if capability is not None else registry.get(intent.capability)
    return ReasoningCortex().evaluate(make_request(text, context=context), make_decision(intent), intent, context or {}, cap, plan)


def test_ambiguous_open_my_project_needs_clarification():
    intent = IntentResult(intent="open_application", capability="desktop.open_application", confidence=0.86, route="desktop")

    decision = evaluate("Open my project", intent)

    assert decision.decision == "clarify"
    assert "project" in decision.missing_information


def test_stale_memory_conflict_is_detected_but_current_context_stays_primary(tmp_path):
    manager = LongTermMemoryManager(LocalJsonMemoryStore(tmp_path / "memory.json"))
    manager.handle_command(make_request("Remember that CliniLocker is my healthcare project."))
    resolver = WorldContextResolver(long_term_memory=manager)
    context = resolver.resolve(make_request("Open my healthcare project", context={"active_project": "CEASER"}))
    intent = IntentResult(intent="general_ai", capability="ai.answer", confidence=0.76, route="backend_ai")

    decision = evaluate("Open my healthcare project", intent, context)

    assert decision.allowed_to_execute is True
    assert "current_context_differs_from_long_term_memory" in decision.conflicts
    assert context["working_memory"]["current_project"] == "CEASER"


def test_destructive_file_delete_requests_confirmation():
    intent = IntentResult(intent="delete_file", capability="desktop.delete_file", confidence=0.82, route="desktop")
    context = {"working_memory": {"active_resource": {"type": "file", "path": "report.pdf"}}}

    decision = evaluate("Delete this file", intent, context)

    assert decision.decision == "request_confirmation"
    assert decision.allowed_to_execute is False
    assert "Recycle Bin" in decision.safer_alternative


def test_safer_archive_alternative_for_delete_project_folder():
    intent = IntentResult(intent="delete_file", capability="desktop.delete_file", confidence=0.9, route="desktop")
    context = {"working_memory": {"active_resource": {"type": "folder", "path": "CliniLocker"}}}

    decision = evaluate("Delete this project folder", intent, context)

    assert "Archive" in decision.safer_alternative


def test_protected_branch_push_suggests_pull_request():
    intent = IntentResult(intent="github_push", capability="github.list_repositories", confidence=0.82, route="integration")
    context = {"working_memory": {"repository": "CliniLocker", "branch": "main", "protected_branch": True}}

    decision = evaluate("Push it", intent, context)

    assert decision.decision == "suggest_alternative"
    assert "pull request" in decision.safer_alternative.lower()


def test_missing_repository_for_commits_needs_clarification():
    intent = IntentResult(intent="github_list_commits", capability="github.list_commits", confidence=0.86, route="integration")
    context = {"working_memory": {"current_project": "CliniLocker"}}

    decision = evaluate("Show commits for this project", intent, context)

    assert decision.decision == "clarify"
    assert "repository" in decision.missing_information


def test_workflow_plan_drift_is_blocked():
    intent = IntentResult(intent="workflow_request", capability="workflow.plan", confidence=0.9, route="workflow")
    plan = WorkflowPlan(
        workflow_id="wf_drift",
        request_id="req",
        session_id="stage12",
        goal="Save CliniLocker notes to Notion",
        summary="Save notes",
        steps=[WorkflowStep(step_id="save", capability="notion.create_page", arguments={"title": "CEASER Notes"}, risk_level="medium", requires_confirmation=True)],
        risk_level="medium",
        requires_confirmation=True,
    )

    decision = evaluate("Save CliniLocker notes to Notion", intent, {}, plan=plan)

    assert decision.decision == "block"
    assert "workflow_plan_drift" in decision.conflicts


def test_low_risk_command_uses_fast_path():
    intent = IntentResult(intent="open_application", capability="desktop.open_application", confidence=0.96, route="desktop")

    decision = evaluate("Open Chrome", intent)

    assert decision.decision == "proceed"
    assert decision.reason == "low_risk_fast_path"


def test_hard_security_rule_cannot_be_overridden():
    intent = IntentResult(intent="blocked_action", capability="dangerous.format_disk", confidence=0.99, route="desktop")
    capability = CapabilityDefinition(name="dangerous.format_disk", description="Format disk", handler="none", route="desktop", risk_level="blocked")

    decision = evaluate("Format my disk", intent, capability=capability)

    assert decision.decision == "block"
    assert decision.allowed_to_execute is False
    assert decision.reason == "hard_security_block"


def test_explicit_current_input_outranks_memory(tmp_path):
    manager = LongTermMemoryManager(LocalJsonMemoryStore(tmp_path / "memory.json"))
    manager.handle_command(make_request("Remember that CliniLocker is my healthcare project."))
    resolver = WorldContextResolver(long_term_memory=manager)
    context = resolver.resolve(make_request("Use CEASER project", context={"active_project": "CEASER"}))
    intent = IntentResult(intent="general_ai", capability="ai.answer", confidence=0.8, route="backend_ai")

    decision = evaluate("Use CEASER project", intent, context)

    assert decision.allowed_to_execute is True
    assert decision.evidence["active_project"] == "CEASER"


def test_low_confidence_unsupported_action_is_not_executed():
    called = {"legacy": False}

    def legacy_handler(_text: str):
        called["legacy"] = True
        return {"status": "completed", "message": "should not run"}

    service = CommandService(legacy_handler, context_resolver=WorldContextResolver())
    result = service.execute(make_request("flarble the current thing"))

    assert result.status == "failed"
    assert called["legacy"] is False
