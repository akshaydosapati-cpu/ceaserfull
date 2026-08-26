import time

from capabilities.registry import build_default_registry
from core.command_service import CommandService, ExecutionEngine
from core.schemas import ActionResult, CommandRequest, IntentResult
from conversation.context_resolver import WorldContextResolver
from planning.confirmation_manager import ConfirmationManager
from planning.models import WorkflowPlan, WorkflowStep
from planning.plan_validator import PlanValidator
from planning.task_planner import TaskPlanner
from planning.workflow_runner import WorkflowRunner


def make_request(text, context=None, session="plan"):
    return CommandRequest(
        request_id=f"req_{abs(hash((text, session))) % 100000}",
        user_id="user-1",
        session_id=session,
        source="typed",
        raw_text=text,
        normalized_text=text,
        context=context or {},
    )


def context(project="CliniLocker"):
    return {
        "active_project": project,
        "active_repository": project,
        "activeWindow": {"process": "Code.exe", "title": f"{project} - Visual Studio Code"},
    }


def planner():
    return TaskPlanner(build_default_registry())


def test_valid_viva_plan_sequence_and_limits():
    request = make_request("Prepare me for my CliniLocker viva and save it to Notion", context())
    ctx = WorldContextResolver().resolve(request)
    plan = planner().plan(request, None, ctx)
    assert plan.planner_evidence["workflow_type"] == "github_project_viva"
    assert len(plan.steps) <= 6
    assert [step.capability for step in plan.steps[:4]] == [
        "github.resolve_repository",
        "github.summarize_repository",
        "study.generate_viva_questions",
        "study.generate_revision_notes",
    ]
    assert any(step.capability == "notion.create_page" and step.requires_confirmation for step in plan.steps)


def test_activity_summary_plan_has_github_reads_and_notion_confirmation():
    request = make_request("Summarize today's work on CEASER and save it to Notion", context("CEASER"))
    ctx = WorldContextResolver().resolve(request)
    plan = planner().plan(request, None, ctx)
    capabilities = [step.capability for step in plan.steps]
    assert capabilities == [
        "github.resolve_repository",
        "github.list_commits",
        "github.list_issues",
        "github.list_pull_requests",
        "ai.summarize_activity",
        "notion.create_page",
    ]
    assert plan.steps[-1].requires_confirmation is True


def test_quiz_plan_has_notion_read_and_no_confirmation():
    request = make_request("Find my Operating Systems notes and quiz me")
    ctx = WorldContextResolver().resolve(request)
    plan = planner().plan(request, None, ctx)
    assert [step.capability for step in plan.steps] == ["notion.search_pages", "notion.get_page", "study.generate_quiz"]
    assert not any(step.requires_confirmation for step in plan.steps)


def test_cycle_rejection():
    registry = build_default_registry()
    plan = WorkflowPlan(
        workflow_id="wf_cycle",
        request_id="r",
        session_id="s",
        goal="cycle",
        summary="cycle",
        steps=[
            WorkflowStep(step_id="a", capability="ai.answer", depends_on=["b"]),
            WorkflowStep(step_id="b", capability="ai.answer", depends_on=["a"]),
        ],
    )
    ok, errors = PlanValidator(registry).validate(plan)
    assert ok is False
    assert "cyclic_dependencies" in errors


def test_unknown_capability_rejection():
    plan = WorkflowPlan(workflow_id="wf_unknown", request_id="r", session_id="s", goal="x", summary="x", steps=[WorkflowStep(step_id="x", capability="missing.capability")])
    ok, errors = PlanValidator(build_default_registry()).validate(plan)
    assert ok is False
    assert "unknown_capability:missing.capability" in errors


def test_confirmation_binding_accepts_current_and_rejects_wrong_or_expired():
    manager = ConfirmationManager()
    step = WorkflowStep(step_id="save", capability="notion.create_page", arguments={"title": "CliniLocker Viva Notes"}, risk_level="medium", requires_confirmation=True)
    confirmation = manager.create("wf1", step)
    assert manager.approve(confirmation.confirmation_id, "wf1", "other") is False
    assert manager.approve(confirmation.confirmation_id, "wf1", "save") is True
    expired = manager.create("wf1", step, ttl_seconds=1)
    expired.expires_at = time.time() - 1
    assert manager.approve(expired.confirmation_id, "wf1", "save") is False


def test_required_step_failure_blocks_dependents():
    def handler(text):
        if "github.resolve_repository" in text:
            return {"status": "error", "message": "repo unavailable", "verified": False}
        return {"status": "completed", "message": "ok", "verified": True}

    registry = build_default_registry()
    runner = WorkflowRunner(ExecutionEngine(registry, handler), PlanValidator(registry))
    plan = WorkflowPlan(
        workflow_id="wf_fail",
        request_id="r",
        session_id="s",
        goal="fail",
        summary="fail required",
        steps=[
            WorkflowStep(step_id="resolve", capability="github.resolve_repository"),
            WorkflowStep(step_id="summary", capability="github.summarize_repository", depends_on=["resolve"]),
        ],
    )
    result = runner.run(make_request("run fail"), plan, {})
    assert result.status == "failed"
    workflow = result.data["workflow_result"]
    assert "summary" in workflow["skipped_steps"]


def test_optional_step_failure_completes_partial():
    def handler(text):
        if "notion.create_page" in text:
            return {"status": "error", "message": "notion unavailable", "verified": False}
        return {"status": "completed", "message": "ok", "verified": True}

    registry = build_default_registry()
    runner = WorkflowRunner(ExecutionEngine(registry, handler), PlanValidator(registry))
    plan = WorkflowPlan(
        workflow_id="wf_partial",
        request_id="r",
        session_id="s",
        goal="partial",
        summary="optional partial",
        steps=[
            WorkflowStep(step_id="summary", capability="ai.answer"),
            WorkflowStep(step_id="save", capability="notion.create_page", depends_on=["summary"], optional=True, requires_confirmation=True),
        ],
    )
    result = runner.run(make_request("run partial"), plan, {})
    assert result.status == "needs_confirmation"
    result = runner.resume(make_request("yes", session="s"), {})
    assert result.status == "partial"


def test_cancellation_stops_future_steps():
    registry = build_default_registry()
    runner = WorkflowRunner(ExecutionEngine(registry, lambda text: {"status": "completed", "message": "ok", "verified": True}), PlanValidator(registry))
    plan = WorkflowPlan(workflow_id="wf_cancel", request_id="r", session_id="s", goal="cancel", summary="cancel", steps=[WorkflowStep(step_id="a", capability="ai.answer")])
    runner.cancel("wf_cancel")
    result = runner.run(make_request("run cancel"), plan, {})
    assert result.status == "cancelled"
    assert any(event["event"] == "workflow_cancelled" for event in result.evidence["events"])


def test_unverified_required_step_prevents_completed_status():
    registry = build_default_registry()
    runner = WorkflowRunner(ExecutionEngine(registry, lambda text: {"status": "completed", "message": "unverified", "verified": False}), PlanValidator(registry))
    plan = WorkflowPlan(workflow_id="wf_unverified", request_id="r", session_id="s", goal="x", summary="x", steps=[WorkflowStep(step_id="a", capability="ai.answer")])
    result = runner.run(make_request("run unverified"), plan, {})
    assert result.status == "failed"
    assert result.verified is False


def test_simple_command_bypasses_planner():
    service = CommandService(lambda text: {"status": "completed", "message": "Chrome opened", "verified": True})
    result = service.execute(make_request("open Chrome"))
    assert result.capability == "app.open"
    assert "planner_selected" not in result.evidence


def test_workflow_command_invokes_planner():
    service = CommandService(lambda text: {"status": "completed", "message": "ok", "verified": True})
    result = service.execute(make_request("Find my Operating Systems notes and quiz me"))
    assert result.capability == "workflow.plan"
    assert result.evidence["planner_selected"] is True
    assert result.evidence["workflow_type"] == "notion_study_quiz"
