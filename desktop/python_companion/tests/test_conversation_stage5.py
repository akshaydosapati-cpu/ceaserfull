from core.command_service import CommandService
from core.schemas import CommandRequest
from conversation.context_resolver import WorldContextResolver


def test_session_tracks_recent_turns_and_follow_up_reference():
    resolver = WorldContextResolver()
    service = CommandService(
        lambda text: {"status": "completed", "message": f"ok:{text}", "verified": True},
        context_resolver=resolver,
    )
    first = CommandRequest(request_id="1", session_id="s1", source="typed", raw_text="explain quantum computing", normalized_text="explain quantum computing")
    first_result = service.execute(first)
    assert first_result.status == "completed"

    second = CommandRequest(request_id="2", session_id="s1", source="typed", raw_text="summarize it", normalized_text="summarize it")
    context = resolver.resolve(second)
    assert context["references"]["follow_up_detected"] is True
    assert context["references"]["resolved_reference"]["last_summary"] == "ok:explain quantum computing"


def test_relationship_model_detects_developer_mode():
    resolver = WorldContextResolver()
    request = CommandRequest(request_id="1", session_id="dev", source="typed", raw_text="show GitHub commits", normalized_text="show GitHub commits")
    context = resolver.resolve(request)
    assert context["relationship"]["observed_domain"] == "developer"


def test_follow_up_command_is_rewritten_with_previous_result():
    resolver = WorldContextResolver()
    seen = []

    def handler(text):
        seen.append(text)
        return {"status": "completed", "message": f"handled:{text[:40]}", "verified": True}

    service = CommandService(handler, context_resolver=resolver)
    service.execute(CommandRequest(request_id="1", session_id="s2", source="typed", raw_text="explain Ramayana", normalized_text="explain Ramayana"))
    result = service.execute(CommandRequest(request_id="2", session_id="s2", source="typed", raw_text="continue", normalized_text="continue"))

    assert result.capability == "ai.answer"
    assert result.evidence["context_rewritten"] is True
    assert "Previous CEASER result" in seen[-1]
    assert "continue" in seen[-1].lower()


def test_summarize_it_uses_previous_result():
    resolver = WorldContextResolver()
    seen = []

    def handler(text):
        seen.append(text)
        return {"status": "completed", "message": "summary", "verified": True}

    service = CommandService(handler, context_resolver=resolver)
    service.execute(CommandRequest(request_id="1", session_id="s3", source="voice", raw_text="explain quantum computing", normalized_text="explain quantum computing"))
    service.execute(CommandRequest(request_id="2", session_id="s3", source="voice", raw_text="summarize it", normalized_text="summarize it"))

    assert seen[-1].startswith("Summarize the previous CEASER result")
