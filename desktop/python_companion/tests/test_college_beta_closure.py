from pathlib import Path

from conversation.response_composer import ResponseComposer
from core.schemas import ActionResult
from voice.engine import VoiceEngine


DESKTOP_ROOT = Path(__file__).resolve().parents[2]


def test_wake_disabled_never_initializes_wake_detector(monkeypatch):
    monkeypatch.setenv("CEASER_WAKE_WORD_ENABLED", "false")
    monkeypatch.setenv("CEASER_WAKE_MODE", "porcupine")
    initialized = []
    monkeypatch.setattr("voice.engine.MicrophoneService.open", lambda _self: None)
    monkeypatch.setattr("voice.engine.PorcupineWakeDetector.initialize", lambda _self: initialized.append(True))
    monkeypatch.setattr("voice.engine.PorcupineWakeDetector.log_runtime_audio_details", lambda *_args: None)

    engine = VoiceEngine(str(DESKTOP_ROOT / "python_companion"))
    engine.start()

    assert engine.wake_enabled is False
    assert engine.config.wake_mode == "hotkey"
    assert initialized == []
    assert engine.state.state == "COMMAND_LISTENING"
    assert engine.wait_for_wake_and_capture().error_code == "wake_disabled"


def test_renderer_and_server_keep_disabled_wake_in_command_mode():
    renderer = (DESKTOP_ROOT / "src" / "renderer" / "app.js").read_text(encoding="utf-8")
    server = (DESKTOP_ROOT / "python_companion" / "desktop_voice_server.py").read_text(encoding="utf-8")
    assert "const WAKE_WORD_LISTENING_ENABLED = false" in renderer
    assert "if (!WAKE_WORD_LISTENING_ENABLED) return" in renderer
    assert 'force_command_listening or not WAKE_WORD_ENABLED' in server


def test_friendly_failure_keeps_status_and_verification_truth():
    result = ActionResult(
        status="failed",
        capability="media.next",
        summary="raw failure",
        verified=False,
        error_code="verification_failed",
    )
    adapted = ResponseComposer._friendly_failure(result)
    assert adapted.status == "failed"
    assert adapted.verified is False
    assert "could not verify" in adapted.summary.lower()


def test_no_hardcoded_weather_or_news_credentials_remain():
    source = (DESKTOP_ROOT / "python_companion" / "features" / "ceaser" / "integrations.py").read_text(encoding="utf-8")
    assert "984304e51432fa8d2faa56a69acc1553" not in source
    assert "f39e105bfd3673d17d665867f26c2c2d" not in source


def test_production_shell_defaults_to_current_console():
    shell = (DESKTOP_ROOT / "src" / "main" / "app-shell.js").read_text(encoding="utf-8")
    assert "https://heyceaser.in/console" in shell
