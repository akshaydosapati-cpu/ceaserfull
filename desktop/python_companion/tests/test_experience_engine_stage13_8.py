from __future__ import annotations

from core.command_service import CommandService
from core.schemas import ActionResult, CommandRequest, IntentResult
from experience.experience_engine import ExperienceEngine


def make_request(text: str, *, session: str = "stage13_8", context: dict | None = None) -> CommandRequest:
    return CommandRequest(
        request_id=f"req-{abs(hash((text, session))) % 999999}",
        user_id="user-a",
        session_id=session,
        source="typed",
        raw_text=text,
        normalized_text=text,
        context=context or {},
    )


def test_records_success_and_capability_rate():
    engine = ExperienceEngine()
    request = make_request("Open Chrome")
    intent = IntentResult(intent="open_application", capability="desktop.open_application", confidence=0.95, route="desktop")
    result = ActionResult(status="completed", capability="desktop.open_application", summary="Opened Chrome", verified=True)

    outcome = engine.record_outcome(request, intent, result, latency_ms=120, context={})

    assert outcome.success is True
    assert engine.as_context()["capability_success"]["desktop.open_application"] == 1.0
    assert result.evidence["experience_status"] == "success"


def test_records_failure_and_latency_hotspot():
    engine = ExperienceEngine()
    request = make_request("Summarize GitHub")
    intent = IntentResult(intent="github_list_repositories", capability="github.list_repositories", confidence=0.8, route="integration")
    result = ActionResult(status="failed", capability="github.list_repositories", summary="GitHub failed", verified=False)

    engine.record_outcome(request, intent, result, latency_ms=5500, context={})
    context = engine.as_context()

    assert context["capability_success"]["github.list_repositories"] == 0.0
    assert context["latency_hotspots"][0]["capability"] == "github.list_repositories"
    assert context["recent_failures"][0]["status"] == "failure"


def test_repeated_command_pattern_is_learned():
    engine = ExperienceEngine()
    intent = IntentResult(intent="open_application", capability="desktop.open_application", confidence=0.95, route="desktop")
    for index in range(3):
        request = make_request("Open Chrome", session=f"s{index}")
        result = ActionResult(status="completed", capability="desktop.open_application", summary="Opened Chrome", verified=True)
        engine.record_outcome(request, intent, result, latency_ms=100, context={})

    repeated = engine.as_context()["repeated_commands"]

    assert repeated
    assert repeated[0]["count"] == 3
    assert "open chrome" in repeated[0]["label"]


def test_repeated_workflow_pattern_is_learned():
    engine = ExperienceEngine()
    intent = IntentResult(intent="workflow_request", capability="workflow.plan", confidence=0.9, route="workflow")
    for index in range(2):
        request = make_request("Save today work to Notion", session=f"wf{index}", context={"active_project": "CEASER"})
        result = ActionResult(status="completed", capability="workflow.plan", summary="Done", verified=True, evidence={"workflow_id": "wf", "workflow_type": "github_activity_summary"})
        engine.record_outcome(request, intent, result, latency_ms=800, context={"working_memory": {"current_project": "CEASER"}})

    workflows = engine.as_context()["repeated_workflows"]

    assert workflows
    assert workflows[0]["metadata"]["workflow_type"] == "github_activity_summary"


def test_clarification_and_confirmation_are_tracked():
    engine = ExperienceEngine()
    intent = IntentResult(intent="follow_up", capability="ai.answer", confidence=0.6, route="backend_ai")
    clarification = ActionResult(status="needs_input", capability="ai.answer", summary="Which file?", verified=True)
    confirmation = ActionResult(status="needs_confirmation", capability="workflow.plan", summary="Confirm save", verified=True)

    engine.record_outcome(make_request("Open it"), intent, clarification, latency_ms=300, context={})
    engine.record_outcome(make_request("Save it"), intent, confirmation, latency_ms=300, context={})
    context = engine.as_context()

    assert context["clarification_hotspots"][0]["clarifications"] == 1
    assert engine.store.capabilities["workflow.plan"].confirmation_count == 1


def test_confirmation_acceptance_is_recorded():
    engine = ExperienceEngine()
    intent = IntentResult(intent="workflow_confirmation_reply", capability="workflow.plan", confidence=0.96, route="workflow")
    result = ActionResult(status="completed", capability="workflow.plan", summary="Workflow completed", verified=True)

    outcome = engine.record_outcome(make_request("yes"), intent, result, latency_ms=600, context={})

    assert outcome.confirmation_state == "accepted"


def test_command_signature_redacts_secrets():
    engine = ExperienceEngine()
    request = make_request("Remember API key sk-1234567890abcdef")
    intent = IntentResult(intent="memory_command", capability="memory.remember", confidence=0.9, route="memory")
    result = ActionResult(status="failed", capability="memory.remember", summary="Rejected", verified=True)

    outcome = engine.record_outcome(request, intent, result, latency_ms=100, context={})

    assert "sk-1234567890abcdef" not in outcome.command_signature
    assert "redacted" in outcome.command_signature


def test_command_service_records_experience_in_finally():
    service = CommandService(lambda text: {"status": "completed", "message": "Chrome opened", "verified": True})

    result = service.execute(make_request("Open Chrome"))

    assert result.evidence["experience_status"] == "success"
    assert service.experience_context()["capability_success"]["app.open"] == 1.0


def test_command_service_records_failed_unsupported_without_execution():
    called = {"legacy": False}

    def legacy(_text):
        called["legacy"] = True
        return {"status": "completed", "message": "bad", "verified": True}

    service = CommandService(legacy)
    result = service.execute(make_request("flarble the thing"))

    assert called["legacy"] is False
    assert result.evidence["experience_status"] == "failure"
    assert service.experience_context()["recent_failures"]
