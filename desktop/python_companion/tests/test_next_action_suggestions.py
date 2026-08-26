from __future__ import annotations

from capabilities.registry import build_default_registry
from conversation.next_action_policy import NextActionPolicy
from core.command_service import CommandService
from core.schemas import ActionResult, CommandRequest
from conversation.context_resolver import WorldContextResolver


def request(text: str, *, session: str = "next-actions", context: dict | None = None) -> CommandRequest:
    return CommandRequest(request_id=f"next-{abs(hash((text, session))) % 999999}", user_id="user-a", session_id=session, source="typed", raw_text=text, normalized_text=text, context=context or {})


def context() -> dict:
    resolver = WorldContextResolver()
    return resolver.resolve(request("context"))


def test_contextual_github_suggestion_is_capability_backed():
    policy = NextActionPolicy(build_default_registry())
    result = ActionResult(status="completed", capability="github.list_commits", summary="Four commits today.", verified=True)
    suggestion = policy.suggest(result, context())[0]
    assert suggestion.capability == "notion.append_blocks"
    assert suggestion.label == "Save the summary to Notion"


def test_pdf_summary_offers_study_action():
    policy = NextActionPolicy(build_default_registry())
    result = ActionResult(status="completed", capability="cloud.read", summary="Document summary ready.", verified=True)
    assert policy.suggest(result, context())[0].capability == "study.generate_quiz"


def test_screenshot_offers_analysis():
    policy = NextActionPolicy(build_default_registry())
    result = ActionResult(status="completed", capability="desktop.take_screenshot", summary="Screenshot captured.", verified=True)
    assert policy.suggest(result, context())[0].command == "Analyze the screenshot I just took."


def test_high_confidence_prediction_is_preferred_when_capability_exists():
    policy = NextActionPolicy(build_default_registry())
    predicted = {
        **context(),
        "prediction": {"predictions": [{"label": "Show prepared commits", "confidence": 0.88, "likely_capability": "github.list_commits", "likely_command": "Show recent commits for the active repository."}]},
    }
    result = ActionResult(status="completed", capability="desktop.take_screenshot", summary="Captured.", verified=True)
    assert policy.suggest(result, predicted)[0].reason == "high_confidence_prediction"


def test_retryable_failure_gets_one_safe_recovery_suggestion():
    policy = NextActionPolicy(build_default_registry())
    result = ActionResult(status="failed", capability="github.list_commits", summary="GitHub timed out.", verified=False, retryable=True)
    suggestion = policy.suggest(result, {**context(), "last_command": "show recent commits"})[0]
    assert suggestion.label == "Try again"
    assert suggestion.confidence == 0.62


def test_simple_focus_unavailable_and_low_confidence_are_suppressed():
    policy = NextActionPolicy(build_default_registry())
    assert policy.suggest(ActionResult(status="completed", capability="desktop.set_volume", summary="Volume set.", verified=True), context()) == []
    assert policy.suggest(ActionResult(status="completed", capability="desktop.take_screenshot", summary="Captured.", verified=True), {**context(), "response_profile": "focus"}) == []
    low = {**context(), "prediction": {"predictions": [{"confidence": 0.40, "likely_capability": "github.list_commits", "likely_command": "show commits"}]}}
    assert policy.suggest(ActionResult(status="completed", capability="ai.answer", summary="Done.", verified=True), low) == []
    registry = build_default_registry()
    unavailable = NextActionPolicy(registry)
    registry._items.pop("ai.answer")
    assert unavailable.suggest(ActionResult(status="completed", capability="desktop.take_screenshot", summary="Captured.", verified=True), context()) == []


def test_yes_executes_bound_suggestion_and_no_clears_it():
    executed: list[str] = []
    service = CommandService(lambda text: executed.append(text) or {"status": "completed", "message": "Screenshot captured.", "verified": True})
    service.execution_engine.windows_runtime.execute = lambda capability, arguments, text: executed.append(text) or {"status": "completed", "message": "Screenshot captured.", "verified": True}
    first = service.execute(request("take a screenshot", session="bound"))
    assert first.evidence["next_actions"][0]["command"] == "Analyze the screenshot I just took."
    service.execute(request("yes", session="bound"))
    assert executed[-1] == "Analyze the screenshot I just took."
    service.execute(request("take a screenshot", session="decline"))
    declined = service.execute(request("not now", session="decline"))
    assert declined.summary == "Okay, I will leave that aside."


def test_confirmation_outranks_suggestion_and_follow_up_does_not_duplicate():
    policy = NextActionPolicy(build_default_registry())
    pending = {**context(), "working_memory": {"pending_confirmation": {"id": "confirm"}}}
    assert policy.suggest(ActionResult(status="completed", capability="desktop.take_screenshot", summary="Captured.", verified=True), pending) == []
    follow_up = {**context(), "suggestion_follow_up": True}
    assert policy.suggest(ActionResult(status="completed", capability="desktop.take_screenshot", summary="Captured.", verified=True), follow_up) == []


def test_spoken_suggestion_is_shorter_than_overlay():
    policy = NextActionPolicy(build_default_registry())
    result = ActionResult(status="completed", capability="github.list_commits", summary="Four commits today with a detailed repository summary.", spoken_response="Four commits today.", verified=True)
    overlay = policy.attach(result, context())
    assert overlay and result.evidence["spoken_next_action"]
    assert len(result.spoken_response or "") < len(result.summary) + 100


def test_medium_confidence_suggestion_is_overlay_only():
    policy = NextActionPolicy(build_default_registry())
    result = ActionResult(status="completed", capability="cloud.create", summary="File created.", spoken_response="File created.", verified=True)
    policy.attach(result, context())
    assert result.evidence["next_actions"][0]["confidence"] == 0.70
    assert "spoken_next_action" not in result.evidence


def test_suggestion_payload_contains_required_fields():
    policy = NextActionPolicy(build_default_registry())
    result = ActionResult(status="completed", capability="desktop.take_screenshot", summary="Captured.", verified=True)
    payload = policy.attach(result, context())[0]
    assert set(payload) == {"label", "command", "capability", "confidence", "reason"}
