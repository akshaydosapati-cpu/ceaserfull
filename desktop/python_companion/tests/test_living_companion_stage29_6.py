from __future__ import annotations

from awareness.models import AwarenessDecision, AwarenessEvent
from conversation.companion_models import CompanionPreferences
from conversation.companion_personality import CompanionPersonalityEngine
from conversation.continuation_resolver import ConversationContinuationResolver
from conversation.proactive_conversation import ProactiveConversationEngine
from conversation.proactive_runtime import ProactiveRuntimeAdapter
from conversation.session_manager import SessionManager
from conversation.social_context import SocialContextEngine
from core.schemas import ActionResult, CommandRequest, IntentResult


def social_event(event_type="user_returned", **payload):
    return AwarenessEvent(
        id=f"evt-{event_type}", category="desktop", type=event_type, source="desktop",
        title=payload.pop("title", "Meaningful context"), summary=payload.pop("summary", "Verified context is available."),
        payload=payload, importance=0.9,
    )


def awareness(event):
    return AwarenessDecision(event_id=event.id, action="notify", importance=.9, reason="test", should_speak=True)


def adapter(*, mode="companion", generator=lambda *_: "A contextual message.", user="user-a", context=None):
    delivered = []
    runtime = ProactiveRuntimeAdapter(
        ProactiveConversationEngine(cooldown_seconds=60),
        CompanionPersonalityEngine(generator),
        lambda _: CompanionPreferences(proactive_mode=mode),
    )
    runtime.configure(delivery=delivered.append, user_id_provider=lambda: user, context_provider=lambda: context or {})
    return runtime, delivered


def test_return_after_absence_is_social_and_dynamic_generation_runs_once():
    calls = []
    runtime, delivered = adapter(generator=lambda instructions, payload: calls.append((instructions, payload)) or "Generated return greeting.")
    event = social_event(absence_seconds=3600, relevance=.9, confidence=.95, allow_spoken_notice=True)
    result = runtime.receive(event, awareness(event))
    assert result["delivered"] and result["payload"]["proactive_kind"] == "social"
    assert result["payload"]["should_speak"] is True
    assert len(calls) == 1 and delivered[0]["message"] == "Generated return greeting."


def test_casual_checkin_and_companion_mode_eligibility():
    engine = SocialContextEngine()
    event = {"event": "casual_interaction_gap", "title": "Conversation gap", "importance": .7, "confidence": .85, "timing": .9}
    balanced = engine.evaluate("balanced", event, CompanionPreferences(proactive_mode="balanced"), {})
    companion = engine.evaluate("companion", event, CompanionPreferences(proactive_mode="companion"), {})
    assert companion.eligible
    assert companion.score > balanced.score


def test_recent_success_and_serious_mode_humor_suppression():
    opportunity = SocialContextEngine().evaluate(
        "user", {"event": "recent_success", "title": "Tests passed", "importance": .9, "confidence": .95},
        CompanionPreferences(proactive_mode="companion"), {"session_mode": "playful"},
    )
    assert opportunity.eligible
    personality = CompanionPersonalityEngine()
    plan, _ = personality.plan(
        CommandRequest(request_id="r", user_id="user", session_id="s", source="automation", raw_text="Failure", normalized_text="failure"),
        None, {"companion_preferences": {"humor": "high", "roasting": "medium"}},
        ActionResult(status="failed", summary="Critical failure", verified=True, evidence={"urgent": True}),
    )
    assert plan.humor == 0 and plan.sarcasm == 0


def test_unfinished_goal_requires_real_memory_identity():
    engine = SocialContextEngine()
    preferences = CompanionPreferences(proactive_mode="companion")
    fabricated = engine.evaluate("user", {"event": "unfinished_user_goal", "unfinished_goal": "Launch today", "confidence": 1, "importance": 1}, preferences, {})
    grounded = engine.evaluate("user", {"event": "unfinished_user_goal", "unfinished_goal": "Launch today", "memory_id": "mem-user-goal", "confidence": 1, "importance": 1}, preferences, {})
    assert not fabricated.eligible and fabricated.reason == "missing_grounded_context"
    assert grounded.eligible and grounded.grounded_context["unfinished_goal"] == "Launch today"


def test_modes_and_explicit_social_switch_suppress_social_only():
    event = {"event": "user_returned", "absence_seconds": 3600, "title": "Returned", "importance": 1, "confidence": 1}
    for preferences, context, reason in (
        (CompanionPreferences(proactive_mode="off"), {}, "social_preference_off"),
        (CompanionPreferences(proactive_mode="important_only"), {}, "social_preference_off"),
        (CompanionPreferences(proactive_mode="companion", social_proactivity=False), {}, "social_preference_off"),
        (CompanionPreferences(proactive_mode="companion"), {"session_mode": "focus"}, "mode_focus"),
    ):
        result = SocialContextEngine().evaluate("user", event, preferences, context)
        assert not result.eligible and result.reason == reason


def test_cooldown_and_duplicate_topic_suppression_preserve_functional_runtime():
    runtime, delivered = adapter()
    social = social_event(absence_seconds=3600, relevance=1, confidence=1, correlation_id="return-1")
    assert runtime.receive(social, awareness(social))["delivered"]
    assert runtime.receive(social, awareness(social))["reason"] in {"event_collapsed", "duplicate_topic", "cooldown"}

    functional_runtime, functional_delivered = adapter(mode="important_only")
    functional = social_event("build_failed", title="Build failed", summary="A verified build failed.", confidence=1)
    assert functional_runtime.receive(functional, awareness(functional))["delivered"]
    assert functional_delivered[0]["proactive_kind"] == "functional"


def test_interruption_budget_and_negative_reaction_reduce_frequency():
    clock = [1000.0]
    engine = SocialContextEngine(now=lambda: clock[0])
    preferences = CompanionPreferences(proactive_mode="balanced", social_interruption_tolerance=.34)
    first = engine.evaluate("user", {"event": "recent_success", "title": "One", "importance": 1, "confidence": 1}, preferences, {})
    assert first.eligible
    engine.delivered("user", first, "message")
    clock[0] += 60
    blocked = engine.evaluate("user", {"event": "recent_success", "title": "Two", "importance": 1, "confidence": 1}, preferences, {})
    assert not blocked.eligible and blocked.reason == "interruption_budget"

    other = SocialContextEngine()
    other.reaction("user", "negative")
    other.reaction("user", "stop_requested")
    suppressed = other.evaluate("user", {"event": "recent_success", "title": "Three", "importance": 1, "confidence": 1}, CompanionPreferences(proactive_mode="companion"), {})
    assert not suppressed.eligible and suppressed.reason == "negative_reaction_budget"


def test_provider_failure_silently_skips_social_and_low_score_avoids_model_call():
    runtime, delivered = adapter(generator=lambda *_: (_ for _ in ()).throw(RuntimeError("provider down")))
    event = social_event(absence_seconds=3600, relevance=1, confidence=1)
    assert runtime.receive(event, awareness(event))["reason"] == "provider_failure"
    assert delivered == []

    calls = []
    low_runtime, _ = adapter(mode="balanced", generator=lambda *_: calls.append(True) or "must not happen")
    low = social_event("interesting_recent_context", relevance=.1, confidence=.1, timing=.1)
    assert not low_runtime.receive(low, awareness(low))["delivered"]
    assert calls == []


def test_reactions_are_bounded_and_explicit_controls_work_without_active_thread():
    runtime, _ = adapter()
    assert runtime.observe_user_message("user-a", "Stop starting conversations") == {"social_proactivity": False}
    assert runtime.observe_user_message("user-a", "Talk to me more") == {
        "social_proactivity": True, "proactive_mode": "companion", "social_interruption_tolerance": .85,
    }


def test_user_scoping_and_topic_deduplication():
    engine = SocialContextEngine()
    event = {"event": "recent_success", "title": "Build clean", "importance": 1, "confidence": 1}
    preferences = CompanionPreferences(proactive_mode="companion")
    first = engine.evaluate("user-a", event, preferences, {})
    engine.delivered("user-a", first, "done")
    assert engine.evaluate("user-a", event, preferences, {}).reason == "duplicate_topic"
    assert engine.evaluate("user-b", event, preferences, {}).eligible
    assert engine.active_thread("user-b") == {}


def test_proactive_turn_continues_in_normal_session():
    sessions = SessionManager()
    request = CommandRequest(request_id="p", user_id="user", session_id="desktop_session", source="automation", raw_text="Proactive build context", normalized_text="proactive build context")
    intent = IntentResult(intent="proactive_event", capability="conversation.proactive", confidence=.99, route="conversation")
    result = ActionResult(status="completed", capability="conversation.proactive", summary="The build completed successfully.", verified=True)
    session = sessions.record(request, intent, result).snapshot()
    references = ConversationContinuationResolver().resolve("Seriously?", session, {})
    assert references["follow_up_detected"]
    assert references["continuation_kind"] == "proactive_thread"
    assert references["resolved_reference"]["last_summary"] == "The build completed successfully."


def test_thread_recorder_receives_social_context_without_private_payload():
    recorded = []
    runtime, _ = adapter()
    runtime.configure(thread_recorder=recorded.append)
    event = social_event(absence_seconds=3600, relevance=1, confidence=1, correlation_id="safe")
    assert runtime.receive(event, awareness(event))["delivered"]
    assert recorded[0]["social_trigger"] == "returned_after_absence"
    assert "api_key" not in str(recorded[0]).lower()


def test_related_event_correlation_is_collapsed():
    runtime, delivered = adapter()
    first = social_event("build_completed", title="Build and tests clean", correlation_id="job-42", confidence=1)
    second = social_event("workflow_completed", title="Same job completed", correlation_id="job-42", confidence=1)
    assert runtime.receive(first, awareness(first))["delivered"]
    assert runtime.receive(second, awareness(second))["reason"] == "event_collapsed"
    assert len(delivered) == 1
