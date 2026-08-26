from conversation.context_resolver import WorldContextResolver
from conversation.executive_cortex import ExecutiveCortex
from core.command_service import CommandService
from core.schemas import CommandRequest
from routing.intent_router import IntentRouter


def request(text: str, source: str, session: str = "voice-parity") -> CommandRequest:
    return CommandRequest(
        request_id=f"{source}-{abs(hash((text, session))) % 999999}",
        session_id=session,
        source=source,  # type: ignore[arg-type]
        raw_text=text,
        normalized_text=text,
    )


def route(text: str, source: str, session: str = "voice-parity"):
    resolver = WorldContextResolver()
    current = request(text, source, session)
    return ExecutiveCortex().route(current, resolver.resolve(current), IntentRouter())


def test_typed_and_voice_tell_me_about_ai_have_identical_backend_route():
    typed = route("tell me about artificial intelligence", "typed")
    voice = route("tell me about artificial intelligence", "voice")

    assert (typed.destination, typed.intent.capability, typed.reason) == ("backend_ai", "ai.answer", "ai_signal")
    assert (voice.destination, voice.intent.capability, voice.reason) == ("backend_ai", "ai.answer", "ai_signal")


def test_typed_and_voice_questions_route_to_backend_ai():
    for prompt in (
        "what is quantum computing?",
        "what do you think about adult sites",
        "discuss remote work",
        "Chrome is not opening properly, what could be wrong",
        "explain what GitHub repositories are",
        "tell me why this file format is useful",
        "what role did music play in the film?",
        "explain battery technology",
        "discuss volume in mathematics",
    ):
        for source in ("typed", "voice"):
            decision = route(prompt, source)
            assert decision.destination == "backend_ai"
            assert decision.intent.capability == "ai.answer"


def test_voice_desktop_action_stays_local_and_does_not_call_backend_handler():
    executed: list[str] = []
    service = CommandService(lambda text: executed.append(text) or {"status": "completed", "message": "Calculator opened.", "verified": True})

    result = service.execute(request("open calculator", "voice"))

    assert result.capability == "app.open"
    assert result.evidence["cortex_destination"] == "desktop"
    assert executed == ["open calculator"]

    polite = route("can you open Chrome", "voice")
    assert polite.destination == "desktop"
    assert polite.intent.capability == "app.open"

    polite_result = service.execute(request("can you open Chrome", "voice"))
    assert polite_result.capability == "app.open"
    assert executed[-1] == "open Chrome"

    for prompt, capability in (
        ("what is my battery percentage?", "desktop.get_battery"),
        ("set volume to 50", "audio.volume.set"),
        ("pause music", "media.pause"),
        ("turn on Bluetooth", "bluetooth.enable"),
        ("disable wifi", "wifi.disable"),
    ):
        decision = route(prompt, "voice")
        assert decision.destination == "desktop"
        assert decision.intent.capability == capability


def test_voice_follow_ups_use_previous_assistant_result():
    executed: list[str] = []
    service = CommandService(lambda text: executed.append(text) or {"status": "completed", "message": f"answer:{text}", "verified": True})

    service.execute(request("tell me about artificial intelligence", "voice", "voice-follow-up"))
    for follow_up in ("summarize", "why?", "tell me more", "what about India?"):
        result = service.execute(request(follow_up, "voice", "voice-follow-up"))
        assert result.capability == "ai.answer"
        assert result.evidence.get("context_rewritten") is True


def test_genuinely_invalid_action_remains_unsupported():
    decision = route("xyzabc", "voice")

    assert decision.destination == "unsupported"
    assert decision.intent.capability == "unsupported"
