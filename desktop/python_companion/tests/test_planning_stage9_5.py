import time

from core.command_service import CommandService, ExecutionEngine
from core.schemas import CommandRequest
from capabilities.registry import build_default_registry
from planning.models import WorkflowPlan, WorkflowStep
from planning.plan_validator import PlanValidator
from planning.workflow_runner import WorkflowRunner


def make_request(text, session="resume"):
    return CommandRequest(
        request_id=f"req_{abs(hash((text, session))) % 100000}",
        user_id="user-1",
        session_id=session,
        source="typed",
        raw_text=text,
        normalized_text=text,
    )


def test_workflow_pauses_for_confirmation_then_yes_resumes_exact_step():
    executed = []

    def handler(text):
        executed.append(text)
        return {"status": "completed", "message": f"ok:{text}", "verified": True}

    service = CommandService(handler)
    first = service.execute(make_request("Prepare me for my CliniLocker viva and save it to Notion", session="yes-flow"))
    assert first.status == "needs_confirmation"
    assert first.confirmation["step_id"] == "save_notion"
    assert service.workflow_runner.has_pending("yes-flow") is True

    second = service.execute(make_request("yes", session="yes-flow"))
    assert second.status == "completed"
    assert second.evidence["workflow_resumed"] is True
    assert any("notion.create_page" in item for item in executed)
    assert any("ai.answer" in item for item in executed)
    assert service.workflow_runner.has_pending("yes-flow") is False


def test_cancel_reply_cancels_pending_workflow_without_executing_write():
    executed = []
    service = CommandService(lambda text: executed.append(text) or {"status": "completed", "message": "ok", "verified": True})
    first = service.execute(make_request("Prepare me for my CliniLocker viva and save it to Notion", session="cancel-flow"))
    assert first.status == "needs_confirmation"

    second = service.execute(make_request("cancel", session="cancel-flow"))
    assert second.status == "cancelled"
    assert second.evidence["workflow_resumed"] is False
    assert not any("notion.create_page" in item for item in executed)
    assert service.workflow_runner.has_pending("cancel-flow") is False


def test_expired_confirmation_is_rejected_on_resume():
    service = CommandService(lambda text: {"status": "completed", "message": "ok", "verified": True})
    first = service.execute(make_request("Prepare me for my CliniLocker viva and save it to Notion", session="expired-flow"))
    assert first.status == "needs_confirmation"
    run = service.workflow_runner.store.pending_for_session("expired-flow")
    confirmation = service.workflow_runner.confirmations.pending[run.pending_confirmation_id]
    confirmation.expires_at = time.time() - 1

    second = service.execute(make_request("yes", session="expired-flow"))
    assert second.status == "failed"
    assert second.error_code == "confirmation_rejected"


def test_runner_resume_continues_from_pending_step_not_from_start():
    executed = []
    registry = build_default_registry()
    runner = WorkflowRunner(ExecutionEngine(registry, lambda text: executed.append(text) or {"status": "completed", "message": "ok", "verified": True}), PlanValidator(registry))
    plan = WorkflowPlan(
        workflow_id="wf_resume_exact",
        request_id="r",
        session_id="exact",
        goal="exact",
        summary="exact",
        steps=[
            WorkflowStep(step_id="read", capability="ai.answer"),
            WorkflowStep(step_id="save", capability="notion.create_page", depends_on=["read"], requires_confirmation=True),
            WorkflowStep(step_id="final", capability="ai.answer", depends_on=["save"]),
        ],
    )
    first = runner.run(make_request("start", session="exact"), plan, {})
    assert first.status == "needs_confirmation"
    before = len([item for item in executed if "ai.answer" in item])
    second = runner.resume(make_request("yes", session="exact"), {})
    after = len([item for item in executed if "ai.answer" in item])
    assert second.status == "completed"
    assert after == before + 1
