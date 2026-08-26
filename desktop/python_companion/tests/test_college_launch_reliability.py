from core.command_service import CommandService
from core.schemas import CommandRequest
from routing.intent_router import IntentRouter


def test_application_phrase_variants_use_one_fast_capability():
    router = IntentRouter()
    for phrase in ("open chrome", "launch chrome", "start chrome", "bring up chrome please", "I need chrome", "chrome open cheyyi"):
        result = router.resolve(phrase)
        assert result.capability == "app.open", phrase
        assert result.route == "desktop"
        assert result.confidence >= 0.8


def test_tab_close_never_routes_to_window_or_application_close():
    router = IntentRouter()
    for phrase in ("close this tab", "close current page", "close the YouTube tab", "close Gmail tab", "close the first tab"):
        result = router.resolve(phrase)
        assert result.capability == "desktop.close_browser_tab", phrase
        assert result.entities.get("object_type") == "browser_tab"

    assert router.resolve("close Chrome").capability == "app.close"
    assert router.resolve("close the Notepad window").capability == "window.close"


def test_tab_entities_preserve_named_active_and_numbered_targets():
    router = IntentRouter()
    assert router.resolve("close this tab").entities["target"] == "active_tab"
    assert router.resolve("close YouTube tab").entities["target"] == "youtube"
    assert router.resolve("close the second tab").entities["index"] == 2


def test_imperfect_volume_brightness_radio_and_media_phrases():
    router = IntentRouter()
    assert router.resolve("make sound little more").capability == "audio.volume.up"
    assert router.resolve("brightness little low").capability == "display.brightness.down"
    assert router.resolve("screen is too bright").capability == "display.brightness.down"
    brightness = router.resolve("put brightness 40")
    assert brightness.capability == "display.brightness.set" and brightness.entities["level"] == 40
    assert router.resolve("switch off wireless").capability == "wifi.disable"
    assert router.resolve("turn bluetooth on").capability == "bluetooth.enable"
    seek = router.resolve("forward 10 seconds")
    assert seek.capability == "media.seek_forward" and seek.entities["seconds"] == 10
    assert router.resolve("rewind 20 seconds").capability == "media.seek_backward"


def test_files_study_and_lecturer_requests_choose_supported_paths():
    router = IntentRouter()
    assert router.resolve("find my DBMS pdf").capability == "file.search"
    for phrase in ("make notes from this", "explain this", "create assignment", "make lecture ppt", "create questions from this"):
        assert router.resolve(phrase).capability == "ai.answer", phrase


def test_ambiguous_close_requires_clarification():
    result = IntentRouter().resolve("close it", {})
    assert result.requires_clarification is True
    assert result.confidence < 0.55


def test_known_unsupported_actions_are_truthful_and_offer_safe_alternative():
    service = CommandService(lambda _text: {"status": "completed", "message": "must not execute"})
    request = CommandRequest(
        request_id="unsupported-1",
        user_id="student",
        session_id="college",
        source="typed",
        raw_text="increase my laptop RAM",
        normalized_text="increase my laptop RAM",
    )
    result = service.execute(request)
    assert result.status == "failed"
    assert result.verified is True
    assert result.error_code == "unsupported_request"
    assert result.evidence["closest_capability"] == "system.memory_info"
    assert "physical hardware upgrade" in result.summary.lower()
