from __future__ import annotations

from awareness.awareness_engine import AwarenessEngine
from awareness.event_sources import EventFactory
from core.command_service import CommandService
from core.schemas import CommandRequest
from conversation.context_resolver import WorldContextResolver


def make_request(text: str = "What changed?") -> CommandRequest:
    return CommandRequest(
        request_id="req-stage13",
        user_id="user-a",
        session_id="stage13",
        source="typed",
        raw_text=text,
        normalized_text=text,
        context={},
    )


def test_low_value_desktop_event_is_quietly_recorded():
    engine = AwarenessEngine()
    event = engine.factory.desktop("active_window_changed", "Active window changed", "Chrome is active")

    decision = engine.observe(event)

    assert decision.action == "ignore"
    assert decision.should_speak is False
    assert engine.as_context()["ignored_count"] == 1


def test_build_failure_becomes_notification_card():
    engine = AwarenessEngine()
    event = engine.factory.development("build_failed", "Build failed", "Desktop validation failed after the last change.", {"failed": True})

    decision = engine.observe(event, {"working_memory": {"active_app": "Visual Studio Code"}})
    context = engine.as_context()

    assert decision.action == "notify"
    assert decision.should_speak is False
    assert context["notification_cards"][0]["title"] == "Build failed"
    assert context["high_importance_count"] == 1


def test_medium_integration_event_is_delayed_not_spoken():
    engine = AwarenessEngine()
    event = engine.factory.integration("github_sync_complete", "GitHub sync complete", "Repository context is ready.", {"provider": "github"})

    decision = engine.observe(event)

    assert decision.action == "delay"
    assert decision.should_speak is False
    assert engine.as_context()["delayed_events"]


def test_event_dedupe_keeps_queue_small():
    engine = AwarenessEngine()
    factory = EventFactory()

    engine.observe(factory.system("download_completed", "Download complete", "Installer downloaded.", {"path": "ceaser.exe"}))
    engine.observe(factory.system("download_completed", "Download complete", "Installer downloaded again.", {"path": "ceaser.exe"}))

    assert len(engine.queue.recent(10)) == 1
    assert engine.queue.recent(1)[0].summary == "Installer downloaded again."


def test_context_resolver_exposes_awareness_context():
    engine = AwarenessEngine()
    engine.observe(engine.factory.development("tests_failed", "Tests failed", "Two tests failed.", {"failed": True}))
    resolver = WorldContextResolver(awareness_engine=engine)

    context = resolver.resolve(make_request())

    assert context["awareness"]["notification_cards"]
    assert context["awareness"]["latest_event_summary"] == "Two tests failed."


def test_command_service_can_ingest_awareness_events():
    service = CommandService(lambda text: {"status": "completed", "message": text, "verified": True})
    event = service.awareness_engine.factory.system("battery_low", "Battery low", "Battery is below 15%.")

    decision = service.observe_event(event)

    assert decision.action == "notify"
    assert service.awareness_context()["notification_cards"][0]["title"] == "Battery low"


def test_awareness_event_does_not_execute_capability_by_itself():
    called = {"legacy": False}

    def legacy_handler(_text: str):
        called["legacy"] = True
        return {"status": "completed", "message": "ran", "verified": True}

    service = CommandService(legacy_handler)
    service.observe_event(service.awareness_engine.factory.development("build_failed", "Build failed", "No execution should happen.", {"failed": True}))

    assert called["legacy"] is False
