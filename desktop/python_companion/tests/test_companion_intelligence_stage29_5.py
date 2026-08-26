from __future__ import annotations

from conversation.companion_models import CompanionPreferences
from conversation.companion_personality import CompanionPersonalityEngine
from conversation.language_analyzer import LanguageAnalyzer
from conversation.proactive_conversation import ProactiveConversationEngine
from conversation.session_manager import SessionManager
from core.schemas import ActionResult, CommandRequest, IntentResult


def request(text: str, *, user: str = "user-a", session: str = "session") -> CommandRequest:
    return CommandRequest(request_id="req", user_id=user, session_id=session, source="typed", raw_text=text, normalized_text=text.lower())


def test_personality_truth_safety_dynamic_generation_and_fallback():
    calls = []
    engine = CompanionPersonalityEngine(lambda instructions, payload: calls.append((instructions, payload)) or "Spotify is open. Nicely done.")
    original = ActionResult(status="completed", capability="desktop.open_application", summary="Spotify opened successfully.", verified=True)
    result = engine.compose(request("Open Spotify"), IntentResult(intent="open", capability="desktop.open_application", confidence=.9, route="desktop"), {"companion_preferences": {"humor": "high", "roasting": "medium"}}, original)
    assert result.status == "completed" and result.verified is True
    assert calls and result.evidence["companion"]["mode"] == "work"

    serious = ActionResult(status="failed", summary="The security operation failed.", verified=True, evidence={"security_incident": True, "sensitive": True})
    _, plan_language = engine.plan(request("This is serious"), None, {}, serious)
    plan, _ = engine.plan(request("This is serious"), None, {"companion_preferences": {"humor": "high", "roasting": "medium"}}, serious)
    assert plan.humor == 0 and plan.sarcasm == 0 and plan.humor_allowed is False
    assert plan_language.primary_language == "English"

    fallback = CompanionPersonalityEngine(lambda *_: (_ for _ in ()).throw(RuntimeError("down")))
    raw = ActionResult(status="completed", summary="Build completed.", verified=True)
    fallback.compose(request("build it"), None, {}, raw)
    assert raw.summary == "Build completed." and raw.evidence["companion_fallback"] is True


def test_languages_and_code_switch_contracts():
    analyzer = LanguageAnalyzer()
    samples = {
        "English": "Open the project",
        "Telugu": "ప్రాజెక్ట్ తెరువు",
        "Kannada": "ಪ್ರಾಜೆಕ್ಟ್ ತೆರೆಯಿರಿ",
        "Hindi": "प्रोजेक्ट खोलो",
        "Tamil": "திட்டத்தைத் திறக்கவும்",
        "Malayalam": "പ്രോജക്റ്റ് തുറക്കുക",
    }
    for expected, text in samples.items():
        assert analyzer.analyze(text).primary_language == expected
    telugu_english = analyzer.analyze("Chrome ఓపెన్ చెయ్యి")
    kannada_english = analyzer.analyze("Chrome ಓಪನ್ ಮಾಡಿ")
    assert telugu_english.primary_language == "Telugu" and telugu_english.code_switched
    assert kannada_english.primary_language == "Kannada" and kannada_english.code_switched
    preferred = analyzer.analyze("Explain the API", CompanionPreferences(language="Telugu"))
    assert preferred.primary_language == "Telugu" and "English" in preferred.secondary_languages


def test_proactive_policy_and_user_isolation():
    engine = ProactiveConversationEngine(cooldown_seconds=60)
    important = {"event": "build_failed", "importance": .9, "urgency": .8, "confidence": .95, "project": "CEASER"}
    assert engine.evaluate("a", important, CompanionPreferences()).should_initiate
    assert not engine.evaluate("a", important, CompanionPreferences()).should_initiate
    assert engine.evaluate("b", important, CompanionPreferences()).should_initiate
    assert not ProactiveConversationEngine().evaluate("a", important, CompanionPreferences(proactive_mode="off")).should_initiate
    assert not ProactiveConversationEngine().evaluate("a", {"event": "model_invented", "importance": 1, "confidence": 1}, CompanionPreferences(proactive_mode="companion")).should_initiate
    assert not ProactiveConversationEngine().evaluate("a", {"event": "user_returned", "importance": .2, "confidence": .8}, CompanionPreferences(proactive_mode="important_only")).should_initiate

    sessions = SessionManager()
    first = sessions.get("same", "a")
    second = sessions.get("same", "b")
    first.active_project = "private-a"
    assert second.active_project == "" and first is not second
