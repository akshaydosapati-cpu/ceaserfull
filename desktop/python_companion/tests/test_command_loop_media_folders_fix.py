from unittest.mock import Mock
from pathlib import Path

from capabilities.windows_runtime import WindowsCapabilityRuntime
from cloud.capabilities import is_cloud_resource_command
from routing.intent_router import IntentRouter


def test_local_shell_folders_never_route_to_cloud():
    for command in (
        "open downloads in file explorer",
        "open documents",
        "open report.pdf in downloads",
        "open recycle bin",
    ):
        assert is_cloud_resource_command(command) is False


def test_seek_and_track_intents_are_distinct():
    router = IntentRouter()
    assert router.resolve("forward").capability == "media.seek_forward"
    assert router.resolve("backward").capability == "media.seek_backward"
    assert router.resolve("next track").capability == "media.next"
    assert router.resolve("previous track").capability == "media.previous"


def test_seek_requires_observed_timeline_change(monkeypatch):
    legacy = Mock(return_value={"status": "completed", "message": "key sent"})
    runtime = WindowsCapabilityRuntime(legacy)
    positions = iter([100, 200])
    monkeypatch.setattr(runtime, "_media_timeline_position", lambda: next(positions))
    result = runtime._media("media.seek_forward", "forward")
    assert result["status"] == "completed"
    assert result["verified"] is True


def test_unchanged_track_is_not_reported_as_success(monkeypatch):
    runtime = WindowsCapabilityRuntime(Mock())
    monkeypatch.setattr(runtime, "_media_playback_state", lambda: "Playing")
    monkeypatch.setattr(runtime, "_media_identity", lambda: "browser|same title|artist")
    monkeypatch.setattr(runtime, "_send_virtual_key", lambda _key: True)
    monkeypatch.setattr("capabilities.windows_runtime.time.sleep", lambda _seconds: None)
    times = iter([0.0, 3.0])
    monkeypatch.setattr("capabilities.windows_runtime.time.time", lambda: next(times, 3.0))
    result = runtime._media("media.next", "next track")
    assert result["status"] == "error"
    assert result["verified"] is False
    assert result["error_code"] == "verification_failed"


def test_nested_direct_command_mode_cannot_fall_into_wake_listening():
    desktop_root = Path(__file__).resolve().parents[2]
    server = (desktop_root / "python_companion" / "desktop_voice_server.py").read_text(encoding="utf-8")
    renderer = (desktop_root / "src" / "renderer" / "app.js").read_text(encoding="utf-8")

    assert 'request_body.get("persistent_command_mode", payload.get("persistent_command_mode", False))' in server
    assert 'listen_for_wake_command(force_command_listening=persistent_command_mode)' in server
    assert renderer.count('persistent_command_mode: true') >= 4
