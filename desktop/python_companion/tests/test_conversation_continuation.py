from core.command_service import CommandService
from core.schemas import CommandRequest
from conversation.context_resolver import WorldContextResolver


def request(text: str, request_id: str, session_id: str = "continuation") -> CommandRequest:
    return CommandRequest(request_id=request_id, session_id=session_id, source="typed", raw_text=text, normalized_text=text)


def test_short_follow_ups_use_previous_result_and_explicit_commands_do_not():
    seen = []
    resolver = WorldContextResolver()
    service = CommandService(lambda text: seen.append(text) or {"status": "completed", "message": f"result:{text}", "verified": True}, context_resolver=resolver)
    service.execute(request("Explain quantum computing.", "1"))

    for index, text in enumerate(("summarize", "make it shorter", "why?", "what about government response?", "continue"), start=2):
        result = service.execute(request(text, str(index)))
        assert result.evidence.get("context_rewritten") is True
        assert "Previous CEASER result" in seen[-1]

    result = service.execute(request("open Chrome", "8"))
    assert result.evidence.get("context_rewritten") is not True
    assert seen[-1] == "open Chrome"


def test_ambiguous_follow_up_without_current_context_clarifies():
    service = CommandService(lambda text: {"status": "completed", "message": text, "verified": True}, context_resolver=WorldContextResolver())

    result = service.execute(request("summarize", "empty", "empty-session"))

    assert result.status == "needs_input"
    assert "continue" in result.summary.lower()


def test_session_context_is_bounded_and_outranks_long_term_memory():
    resolver = WorldContextResolver()
    service = CommandService(lambda text: {"status": "completed", "message": f"current:{text}", "verified": True}, context_resolver=resolver)
    for index in range(20):
        service.execute(request(f"Explain current topic {index}", str(index), "bounded"))

    context = resolver.resolve(request("summarize", "next", "bounded"))

    assert context["references"]["follow_up_detected"] is True
    assert len(context["session"]["recent_turns"]) == 16
    assert context["references"]["resolved_reference"]["last_summary"].startswith("current:Explain current topic 19")
