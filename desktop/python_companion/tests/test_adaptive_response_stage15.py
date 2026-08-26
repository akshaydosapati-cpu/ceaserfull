from __future__ import annotations

from conversation.adaptive_response import AdaptiveResponsePolicy
from core.command_service import CommandService
from core.schemas import ActionResult, CommandRequest, IntentResult


def make_request(text: str, *, context: dict | None = None, session: str = "stage15") -> CommandRequest:
    return CommandRequest(
        request_id=f"stage15-{abs(hash((text, session))) % 999999}",
        user_id="user-a",
        session_id=session,
        source="typed",
        raw_text=text,
        normalized_text=text,
        context=context or {},
    )


def make_intent(capability: str = "ai.answer", route: str = "backend_ai") -> IntentResult:
    return IntentResult(intent="general_ai", capability=capability, confidence=0.8, route=route)


def make_result() -> ActionResult:
    return ActionResult(
        status="completed",
        capability="ai.answer",
        summary="Quantum computing uses qubits to represent information. It can explore many possibilities for certain problems.",
        spoken_response="Quantum computing uses qubits to represent information. It can explore many possibilities for certain problems.",
        verified=True,
    )


def test_explicit_brief_preference_selects_focus_profile():
    policy = AdaptiveResponsePolicy()
    result = policy.apply(make_request("be brief and explain quantum computing"), make_intent(), {}, make_result())

    assert result.evidence["adaptive_response_profile"] == "focus"
    assert result.summary == "Quantum computing uses qubits to represent information."
    assert "optional" not in result.summary.lower()


def test_study_profile_uses_simple_structured_response():
    policy = AdaptiveResponsePolicy()
    result = policy.apply(make_request("use simple language to explain this"), make_intent(), {}, make_result())

    assert result.evidence["adaptive_response_profile"] == "study"
    assert "Simple explanation:" in result.summary
    assert "Example:" in result.summary


def test_build_profile_uses_technical_structure():
    policy = AdaptiveResponsePolicy()
    result = policy.apply(make_request("switch to build mode and explain api errors"), make_intent(), {}, make_result())

    assert result.evidence["adaptive_response_profile"] == "build"
    assert "Technical summary:" in result.summary
    assert "Tests or checks:" in result.summary


def test_founder_profile_uses_business_structure():
    policy = AdaptiveResponsePolicy()
    result = policy.apply(make_request("founder mode: explain launch risk"), make_intent(), {}, make_result())

    assert result.evidence["adaptive_response_profile"] == "founder"
    assert "Business impact:" in result.summary
    assert "Next action:" in result.summary


def test_focus_profile_omits_optional_suggestions():
    policy = AdaptiveResponsePolicy()
    result = policy.apply(make_request("switch to focus mode and explain this"), make_intent(), {}, make_result())

    assert result.evidence["adaptive_response_profile"] == "focus"
    assert "suggestion" not in result.summary.lower()
    assert "optional" not in result.summary.lower()


def test_active_vscode_selects_build_when_no_explicit_preference_exists():
    policy = AdaptiveResponsePolicy()
    context = {"working_memory": {"active_app": "Visual Studio Code"}}
    result = policy.apply(make_request("explain this error"), make_intent(), context, make_result())

    assert result.evidence["adaptive_response_profile"] == "build"


def test_explicit_preference_overrides_inferred_mode():
    policy = AdaptiveResponsePolicy()
    context = {"working_memory": {"active_app": "Visual Studio Code"}}
    result = policy.apply(make_request("use simple language for this code error"), make_intent(), context, make_result())

    assert result.evidence["adaptive_response_profile"] == "study"
    assert "Simple explanation:" in result.summary


def test_factual_content_is_preserved():
    policy = AdaptiveResponsePolicy()
    result = policy.apply(make_request("switch to study mode"), make_intent(), {}, make_result())

    assert "Quantum computing uses qubits" in result.summary
    assert "represent information" in result.summary


def test_status_and_verified_are_unchanged():
    policy = AdaptiveResponsePolicy()
    result = ActionResult(status="needs_confirmation", capability="workflow.plan", summary="Confirm this action.", verified=True)

    adapted = policy.apply(make_request("be brief"), make_intent("workflow.plan", "workflow"), {}, result)

    assert adapted.status == "needs_confirmation"
    assert adapted.verified is True


def test_spoken_response_shorter_than_overlay_where_appropriate():
    policy = AdaptiveResponsePolicy()
    result = policy.apply(make_request("switch to study mode"), make_intent(), {}, make_result())

    assert result.spoken_response
    assert len(result.spoken_response) < len(result.summary)


def test_command_service_applies_adaptive_response_after_execution():
    service = CommandService(lambda _text: {"status": "completed", "message": "The API failed because the token expired. Refresh the token and retry.", "verified": True})
    request = make_request("switch to build mode and explain api token error")

    result = service.execute(request)

    assert result.status == "completed"
    assert result.verified is True
    assert result.evidence["adaptive_response_profile"] == "build"
    assert "Technical summary:" in result.summary
