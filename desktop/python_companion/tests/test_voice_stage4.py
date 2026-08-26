import pytest

from core.command_service import CommandService
from core.schemas import CommandRequest
from voice.engine import VoiceEngine
from voice.microphone import MicrophoneService
from voice.models import AudioCapture, TranscriptResult
from voice.state_machine import VoiceStateMachine
from voice.stt import SttService
from voice.wake_aliases import extract_wake_command, strip_wake_prefix


def test_voice_state_valid_and_invalid_transitions():
    events = []
    machine = VoiceStateMachine("test", emit=lambda event, payload: events.append((event, payload)))
    machine.transition("STARTING")
    machine.transition("WAKE_LISTENING")
    machine.transition("WAKE_DETECTED")
    machine.transition("COMMAND_LISTENING")
    machine.transition("TRANSCRIBING")
    machine.transition("ROUTING")
    machine.transition("EXECUTING")
    machine.transition("COMPLETED")
    machine.transition("WAKE_LISTENING")
    assert events[-1][1]["state"] == "wake_listening"
    with pytest.raises(ValueError):
        machine.transition("SPEAKING")


def test_stt_does_not_transcribe_silence():
    stt = SttService(provider="google")
    result = stt.transcribe(AudioCapture(b"", 16000, 2, 1000, False, error_code="no_speech"))
    assert result.transcript == ""
    assert result.error_code == "no_speech"


def test_typed_voice_parity_uses_same_brain():
    def handler(text):
        if text == "unsupported nonsense command":
            return {"status": "error", "message": "unsupported"}
        return {"status": "completed", "message": f"ok:{text}", "verified": True}

    service = CommandService(handler)
    commands = [
        "open Chrome",
        "open Calculator",
        "open Downloads",
        "take a screenshot",
        "set volume to 50%",
        "pause music",
        "open https://github.com",
        "explain quantum computing",
        "unsupported nonsense command",
    ]
    for command in commands:
        typed = CommandRequest(request_id="typed", session_id="s", source="typed", raw_text=command, normalized_text=command)
        voice = CommandRequest(request_id="voice", session_id="s", source="voice", raw_text=command, normalized_text=command)
        typed_intent = service.intent_router.resolve(typed.normalized_text, {})
        voice_intent = service.intent_router.resolve(voice.normalized_text, {})
        typed_result = service.execute(typed)
        voice_result = service.execute(voice)
        assert typed_intent.intent == voice_intent.intent
        assert typed_intent.capability == voice_intent.capability
        assert typed_intent.route == voice_intent.route
        assert typed_result.status == voice_result.status
        assert typed_result.verified == voice_result.verified


class FakeRecorder:
    def __init__(self, capture):
        self.capture = capture

    def capture_command(self):
        return self.capture


class FakeStt:
    provider = "google"

    def __init__(self, result):
        self.result = result

    def transcribe(self, _capture):
        return self.result


def engine_for_capture(capture, result=None):
    engine = VoiceEngine.__new__(VoiceEngine)
    engine.started = True
    engine.state = VoiceStateMachine("wake-test")
    engine.state.transition("STARTING")
    engine.state.transition("WAKE_LISTENING")
    engine.recorder = FakeRecorder(capture)
    engine.stt = FakeStt(result or TranscriptResult("", "google", error_code="stt_failed"))
    engine.emit_event = None
    engine.active_wake_mode = lambda: "transcript_degraded"
    return engine


def test_transcript_wake_no_speech_recovers_to_wake_listening():
    capture = AudioCapture(b"", 16000, 2, 500, False, error_code="no_speech")
    engine = engine_for_capture(capture)

    result = engine._capture_and_transcribe("transcript_wake")

    assert result.error_code == "no_speech"
    assert result.metadata["recoverable"] is True
    assert engine.state.state == "WAKE_LISTENING"


def test_transcript_wake_background_speech_does_not_route_command():
    capture = AudioCapture(b"abc", 16000, 2, 700, True)
    stt_result = TranscriptResult("background music playing", "google")
    engine = engine_for_capture(capture, stt_result)

    result = engine._capture_and_transcribe("transcript_wake")

    assert result.transcript == "background music playing"
    assert engine.state.state == "WAKE_LISTENING"


def test_hotkey_activation_still_enters_command_listening_and_fails_visibly():
    capture = AudioCapture(b"", 16000, 2, 500, False, error_code="no_speech")
    engine = engine_for_capture(capture)

    result = engine._capture_and_transcribe("hotkey")

    assert result.error_code == "no_speech"
    assert engine.state.state == "FAILED"


def test_hotkey_wait_no_speech_stays_in_command_listening():
    capture = AudioCapture(b"", 16000, 2, 500, False, error_code="no_speech")
    engine = engine_for_capture(capture)

    result = engine.capture_hotkey_command(recoverable_no_speech=True)

    assert result.error_code == "no_speech"
    assert result.metadata["recoverable"] is True
    assert engine.state.state == "COMMAND_LISTENING"


def test_failed_state_can_recover_to_command_listening_for_hotkey_retry():
    machine = VoiceStateMachine("retry-test")
    machine.transition("STARTING")
    machine.transition("COMMAND_LISTENING")
    machine.transition("FAILED")

    machine.transition("COMMAND_LISTENING", reason="retry_after_recoverable_miss")

    assert machine.state == "COMMAND_LISTENING"


def test_hey_season_normalizes_to_wake_command():
    wake = extract_wake_command("hey season explain Avengers")

    assert wake == {"woke": True, "command": "explain Avengers"}


def test_wake_alias_stripped_only_at_transcript_start():
    assert strip_wake_prefix("Hey CEASER, open Chrome") == "open Chrome"
    assert strip_wake_prefix("please explain the cricket season") == "please explain the cricket season"


def test_genuine_season_at_start_is_preserved():
    assert extract_wake_command("season planning for launch") == {"woke": False, "command": ""}
    assert strip_wake_prefix("season planning for launch") == "season planning for launch"


def test_follow_up_optional_wake_alias_can_be_stripped():
    assert strip_wake_prefix("explain Avengers") == "explain Avengers"
    assert strip_wake_prefix("hey seizure explain Avengers") == "explain Avengers"


def test_porcupine_sample_rate_conversion_returns_exact_frame(monkeypatch):
    config = type("Config", (), {"frame_length": 512, "sample_width": 2, "channels": 1, "sample_rate": 16000})()
    mic = MicrophoneService.__new__(MicrophoneService)
    mic.config = config
    mic.stream_sample_rate = 44100
    mic._ratecv_state = None

    converted = mic._to_target_audio_frame(b"\x01\x00" * 1411)

    assert len(converted) == 1024


def test_duplicate_wake_session_is_suppressed():
    engine = VoiceEngine.__new__(VoiceEngine)
    engine.start = lambda: None
    engine.wake_enabled = True
    engine.wake_request_active = True
    engine.wake_session_id = "wake_existing"
    engine.active_wake_mode = lambda: "transcript_degraded"

    result = engine.wait_for_wake_and_capture()

    assert result.error_code == "wake_request_active"
    assert result.metadata["recoverable"] is True
    assert result.metadata["wake_session_id"] == "wake_existing"


def test_hotkey_wake_mode_does_not_use_transcript_fallback():
    engine = VoiceEngine.__new__(VoiceEngine)
    engine.config = type("Config", (), {"wake_mode": "hotkey", "wake_fallback": "transcript"})()
    engine.wake = type("Wake", (), {"available": False})()

    assert engine.active_wake_mode() == "hotkey_only"


def test_voice_engine_start_initializes_services_once():
    events = []

    class FakeWake:
        available = False
        degraded_reason = "test"

        def __init__(self):
            self.calls = 0

        def initialize(self):
            self.calls += 1

        def log_runtime_audio_details(self, _microphone):
            return None

    class FakeMic:
        device_info = {}

        def __init__(self):
            self.calls = 0

        def open(self):
            self.calls += 1

    engine = VoiceEngine.__new__(VoiceEngine)
    engine.started = False
    engine.wake_enabled = True
    engine.degraded = False
    engine.degraded_reason = ""
    engine.config = type("Config", (), {"wake_mode": "porcupine", "wake_fallback": "transcript"})()
    engine.state = VoiceStateMachine("start-once", emit=lambda event, payload: events.append((event, payload)))
    engine.wake = FakeWake()
    engine.microphone = FakeMic()
    engine.active_wake_mode = lambda: "transcript_degraded"

    VoiceEngine.start(engine)
    VoiceEngine.start(engine)

    assert engine.wake.calls == 1
    assert engine.microphone.calls == 1
