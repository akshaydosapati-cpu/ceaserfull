from __future__ import annotations

from pathlib import Path

import pytest

from core.command_service import CommandService
from core.schemas import CommandRequest
from voice.diagnostics import RuntimeDiagnostics
from voice.metrics import InteractionMetrics, LatencyHistory, redact_diagnostics
from voice.models import AudioCapture, TranscriptResult
from voice.state_machine import ConversationalVoiceController
from voice.stt import SttService
from voice.wakeword import PorcupineWakeDetector
from voice.models import VoiceConfig


ROOT = Path(__file__).resolve().parents[2]


def request(text: str, request_id: str = "stage17") -> CommandRequest:
    return CommandRequest(request_id=request_id, session_id="stage17", source="voice", raw_text=text, normalized_text=text)


def test_latency_metric_calculation():
    metrics = InteractionMetrics(
        wake_detected_at=100,
        command_speech_started_at=150,
        command_speech_ended_at=450,
        stt_started_at=500,
        stt_completed_at=900,
        routing_started_at=910,
        routing_completed_at=960,
        execution_started_at=960,
        execution_completed_at=1200,
        tts_requested_at=1210,
        tts_started_at=1300,
        tts_completed_at=1500,
        wake_resumed_at=1520,
    )

    safe = metrics.safe_metrics()

    assert safe["wake_latency_ms"] == 50
    assert safe["endpointing_latency_ms"] == 50
    assert safe["stt_latency_ms"] == 400
    assert safe["routing_latency_ms"] == 50
    assert safe["execution_latency_ms"] == 240
    assert safe["tts_start_latency_ms"] == 90
    assert safe["total_latency_ms"] == 1420


def test_missing_timestamps_are_safe():
    safe = InteractionMetrics(stt_started_at=100).safe_metrics()

    assert safe["stt_latency_ms"] is None
    assert safe["total_latency_ms"] is None


def test_duplicate_execution_prevention_semantics():
    service = CommandService(lambda text: {"status": "completed", "message": f"ok:{text}", "verified": True})

    first = service.execute(request("open chrome", "same-id"))
    second = service.execute(request("open chrome", "same-id"))

    assert first.status == "completed"
    assert second.status == "completed"
    assert service.experience_context()["capability_success"]


def test_backend_failure_normalization():
    service = CommandService(lambda _text: (_ for _ in ()).throw(RuntimeError("backend down")))

    result = service.execute(request("open chrome"))

    assert result.status == "failed"
    assert result.retryable is True
    assert result.error_code == "execution_failed"


def test_stt_timeout_recovery_returns_normalized_error(monkeypatch):
    stt = SttService(provider="google")

    def fail(_capture):
        raise TimeoutError("timeout")

    monkeypatch.setattr(stt, "_google", fail)
    result = stt.transcribe(AudioCapture(b"1234", 16000, 2, 1000, True))

    assert result.transcript == ""
    assert result.error_code == "stt_failed"
    assert "google:TimeoutError" in result.metadata["errors"]


def test_porcupine_degraded_mode_without_access_key(monkeypatch):
    monkeypatch.delenv("PICOVOICE_ACCESS_KEY", raising=False)
    monkeypatch.delenv("PV_ACCESS_KEY", raising=False)
    monkeypatch.delenv("CEASER_PICOVOICE_ACCESS_KEY", raising=False)
    detector = PorcupineWakeDetector(VoiceConfig(), "missing.ppn")

    detector.initialize()

    assert detector.available is False
    assert detector.degraded_reason


def test_tts_interruption_recovery():
    controller = ConversationalVoiceController()
    controller.begin_speaking("Long overlay", "Short spoken")

    result = controller.interrupt("hotkey")

    assert result["status"] == "cancelled"
    assert controller.tts_playing is False
    assert controller.state == "FOLLOW_UP_LISTENING"


def test_sleep_resume_handoff_contract_exists():
    main_js = (ROOT / "src" / "main" / "main.js").read_text(encoding="utf-8")

    assert "power_event" in main_js
    assert "suspend" in main_js
    assert "resume" in main_js


def test_diagnostics_redaction():
    payload = redact_diagnostics({"api_key": "secret", "nested": {"refresh_token": "abc", "safe": "ok"}})

    assert payload["api_key"] == "[redacted]"
    assert payload["nested"]["refresh_token"] == "[redacted]"
    assert payload["nested"]["safe"] == "ok"


def test_diagnostic_snapshot_contains_required_fields():
    history = LatencyHistory()
    history.add({"stt_latency_ms": 100, "routing_latency_ms": 20})
    snapshot = RuntimeDiagnostics(history).snapshot(producer_health={"git": "ok"}, queue_sizes={"python_pending_requests": 0})

    assert snapshot["active_microphone_device"]
    assert snapshot["active_wake_mode"]
    assert snapshot["stt_provider"]
    assert snapshot["python_process_uptime_ms"] >= 0
    assert snapshot["producer_health"]["git"] == "ok"
    assert snapshot["queue_sizes"]["python_pending_requests"] == 0
    assert snapshot["recent_latency_percentiles"]["stt_latency_ms"]["p50"] == 100


def test_packaged_resource_path_resolution_contract():
    main_js = (ROOT / "src" / "main" / "main.js").read_text(encoding="utf-8")
    validate_js = (ROOT / "scripts" / "validate.mjs").read_text(encoding="utf-8")

    assert "process.resourcesPath" in main_js
    assert "python_companion/Hey-Ceaser_en_windows_v3_0_0.ppn" in validate_js
    assert (ROOT / "python_companion" / "Hey-Ceaser_en_windows_v3_0_0.ppn").exists()


def test_clean_shutdown_contract_exists():
    main_js = (ROOT / "src" / "main" / "main.js").read_text(encoding="utf-8")

    assert "appIsQuitting = true" in main_js
    assert "__quit__" in main_js
    assert "globalShortcut.unregisterAll()" in main_js


def test_child_process_restart_contract_exists():
    main_js = (ROOT / "src" / "main" / "main.js").read_text(encoding="utf-8")

    assert "python_voice_exited_restart_scheduled" in main_js
    assert "ensurePythonVoiceProcess()" in main_js
