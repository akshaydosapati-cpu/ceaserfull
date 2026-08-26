from core.media_state import MediaStateTracker
from capabilities.windows_runtime import WindowsCapabilityRuntime
from routing.intent_router import IntentRouter


def test_pause_then_play_music_resumes_current_media():
    state = MediaStateTracker()
    state.record("generic_play")
    assert state.resolve("pause music").action == "pause"
    state.record("pause")
    assert state.status == "paused"
    assert state.resolve("play music").action == "resume"


def test_paused_resume_and_continue_are_resume_intents():
    state = MediaStateTracker()
    state.record("pause")
    assert state.resolve("resume music").action == "resume"
    assert state.resolve("continue").action == "resume"
    assert state.normalize_for_routing("continue") == "resume music"


def test_paused_determiner_phrases_resume_current_media():
    state = MediaStateTracker()
    state.record("pause")
    for phrase in ("play the song", "play the music", "play it", "resume the song", "continue the music"):
        assert state.resolve(phrase).action == "resume"


def test_explicit_target_is_new_playback_even_when_paused():
    state = MediaStateTracker()
    state.record("pause")
    result = state.resolve("play Believer")
    assert result.action == "new_playback"
    assert result.query == "Believer"


def test_no_active_media_keeps_existing_generic_play_behavior():
    state = MediaStateTracker()
    assert state.resolve("play music").action == "generic_play"


def test_stop_semantics_and_state_are_preserved():
    state = MediaStateTracker()
    assert state.resolve("stop music").action == "stop"
    state.record("stop")
    assert state.status == "stopped"


def test_verified_windows_media_controls_and_routing(monkeypatch):
    monkeypatch.setattr("capabilities.windows_runtime.platform.system", lambda: "Windows")
    states = iter(("Playing", "Paused"))
    monkeypatch.setattr(WindowsCapabilityRuntime, "_media_playback_state", staticmethod(lambda: next(states)))
    monkeypatch.setattr(WindowsCapabilityRuntime, "_send_virtual_key", staticmethod(lambda _key: True))
    result = WindowsCapabilityRuntime(lambda _text: {}).execute("media.pause", {}, "pause music")
    assert result["status"] == "completed" and result["verified"] is True
    assert result["dispatch"] == "windows_media_key"
    router = IntentRouter()
    assert router.resolve("resume music").capability == "media.play"
    assert router.resolve("forward").capability == "media.seek_forward"
    assert router.resolve("rewind").capability == "media.seek_backward"
    assert router.resolve("set brightness to 40%").capability == "display.brightness.set"
    assert router.resolve("turn Wi-Fi off").capability == "wifi.disable"
    assert router.resolve("enable Bluetooth").capability == "bluetooth.enable"
