from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from typing import Callable

from voice.microphone import MicrophoneService, configured_device_index
from voice.models import TranscriptResult, VoiceConfig
from voice.state_machine import VoiceStateMachine
from voice.stt import SttService
from voice.vad import VadRecorder
from voice.wakeword import PorcupineWakeDetector
from voice.watchdog import VoiceWatchdog


class VoiceEngine:
    def __init__(
        self,
        base_dir: str,
        emit_event: Callable[[str, dict], None] | None = None,
        transcript_wake_fallback: Callable[[], dict] | None = None,
        wake_extractor: Callable[[str], dict] | None = None,
        session_id: str = "voice_engine",
    ) -> None:
        self.wake_enabled = os.getenv("CEASER_WAKE_WORD_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
        configured_wake_mode = os.getenv("CEASER_WAKE_MODE", "porcupine").lower()
        self.config = VoiceConfig(
            # A disabled wake word is an architectural boundary: Porcupine and
            # transcript wake fallback must never become active implicitly.
            wake_mode=configured_wake_mode if self.wake_enabled else "hotkey",
            wake_fallback=os.getenv("CEASER_WAKE_FALLBACK", "transcript").lower(),
            wake_sensitivity=float(os.getenv("CEASER_WAKE_SENSITIVITY", "0.65")),
            speech_start_timeout=float(os.getenv("CEASER_SPEECH_START_TIMEOUT", "4")),
            end_silence_ms=int(os.getenv("CEASER_END_SILENCE_MS", "750")),
            max_command_seconds=float(os.getenv("CEASER_MAX_COMMAND_SECONDS", "12")),
            rms_threshold=int(os.getenv("CEASER_VAD_RMS_THRESHOLD", "180")),
            microphone_device_index=configured_device_index(),
        )
        self.emit_event = emit_event
        self.state = VoiceStateMachine(session_id=session_id, emit=emit_event)
        self.microphone = MicrophoneService(self.config)
        self.watchdog = VoiceWatchdog(self.microphone)
        self.recorder = VadRecorder(self.microphone, self.config)
        self.stt = SttService(os.getenv("CEASER_STT_PROVIDER", "google"), os.getenv("CEASER_STT_LANGUAGE", "en-IN"))
        model_path = str(Path(base_dir) / "Hey-Ceaser_en_windows_v3_0_0.ppn")
        self.wake = PorcupineWakeDetector(self.config, model_path)
        self.transcript_wake_fallback = transcript_wake_fallback
        self.wake_extractor = wake_extractor
        self.started = False
        self.degraded = False
        self.degraded_reason = ""
        self.wake_request_active = False
        self.wake_session_id = ""

    def start(self) -> None:
        if self.started:
            return
        wake_enabled = getattr(self, "wake_enabled", False)
        self.state.transition("STARTING", reason="voice_engine_start")
        if wake_enabled and self.config.wake_mode == "porcupine":
            self.wake.initialize()
            if not self.wake.available:
                self.degraded = True
                self.degraded_reason = self.wake.degraded_reason or "porcupine_unavailable"
                self.state.transition("DEGRADED", reason=self.degraded_reason, wake_fallback=self.config.wake_fallback)
        self.microphone.open()
        self.wake.log_runtime_audio_details(self.microphone)
        if self.state.state in ("STARTING", "DEGRADED"):
            ready_state = "WAKE_LISTENING" if wake_enabled else "COMMAND_LISTENING"
            self.state.transition(ready_state, reason="voice_engine_ready", wake_mode=self.active_wake_mode())
        self.started = True

    def active_wake_mode(self) -> str:
        if self.config.wake_mode == "hotkey":
            return "hotkey_only"
        if self.config.wake_mode == "porcupine" and self.wake.available:
            return "porcupine"
        if self.config.wake_fallback == "transcript":
            return "transcript_degraded"
        return "hotkey_only"

    def microphone_details(self) -> dict:
        info = self.microphone.device_info or {}
        return {
            "name": info.get("name") or "default microphone",
            "sample_rate": self.config.sample_rate,
            "frame_length": self.config.frame_length,
            "wake_mode": self.active_wake_mode(),
            "degraded": self.degraded,
            "degraded_reason": self.degraded_reason,
        }

    def capture_hotkey_command(self, recoverable_no_speech: bool = False) -> TranscriptResult:
        self.start()
        return self._capture_and_transcribe(activation="hotkey_wait" if recoverable_no_speech else "hotkey")

    def wait_for_wake_and_capture(self) -> TranscriptResult:
        self.start()
        if not getattr(self, "wake_enabled", False):
            return TranscriptResult("", "hotkey_only", error_code="wake_disabled", metadata={"recoverable": True})
        if self.wake_request_active:
            return TranscriptResult("", self.active_wake_mode(), error_code="wake_request_active", metadata={"recoverable": True, "wake_session_id": self.wake_session_id})
        self.wake_request_active = True
        self.wake_session_id = f"wake_{uuid.uuid4().hex[:12]}"
        if self.emit_event:
            self.emit_event("voice_wake_diagnostic", {
                "wake_session_id": self.wake_session_id,
                "wake_mode": self.active_wake_mode(),
                "degraded": self.degraded,
                "degraded_reason": self.degraded_reason,
                "wake_request_active": True,
            })
        try:
            return self._wait_for_wake_and_capture()
        finally:
            self.wake_request_active = False

    def _wait_for_wake_and_capture(self) -> TranscriptResult:
        mode = self.active_wake_mode()
        self.state.transition("WAKE_LISTENING", reason="awaiting_wake", wake_mode=mode)
        if mode == "porcupine":
            if not self.watchdog.ensure_healthy():
                self.state.transition("RECOVERING", reason="microphone_unhealthy")
                self.microphone.reopen()
                self.state.transition("WAKE_LISTENING", reason="microphone_recovered")
            if not self.wake.wait_for_wake(self.microphone):
                return TranscriptResult("", mode, error_code="wake_timeout")
            self.state.transition("WAKE_DETECTED", reason="porcupine")
            return self._capture_and_transcribe(activation="wake")
        if mode == "transcript_degraded" and self.wake_extractor:
            self.state.transition("DEGRADED", reason="transcript_wake_fallback")
            while True:
                heard = self._capture_and_transcribe(activation="transcript_wake")
                if heard.error_code:
                    if heard.error_code in {"no_speech", "stt_failed", "empty_transcript", "wake_request_active"} or heard.metadata.get("recoverable"):
                        if self.emit_event:
                            self.emit_event("voice_wake_diagnostic", {
                                "wake_session_id": self.wake_session_id,
                                "wake_mode": mode,
                                "speech_detected": False,
                                "recoverable": True,
                                "error_code": heard.error_code,
                            })
                        self.state.transition("WAKE_LISTENING", reason="recoverable_wake_miss", wake_mode=mode)
                        continue
                    return heard
                wake = self.wake_extractor(heard.transcript)
                if not wake.get("woke"):
                    if self.emit_event:
                        self.emit_event("voice_wake_diagnostic", {
                            "wake_session_id": self.wake_session_id,
                            "activation_source": "transcript_fallback",
                            "wake_detected": False,
                        })
                    continue
                self.state.transition("WAKE_DETECTED", reason="transcript_degraded", activation_source="transcript_fallback")
                command = str(wake.get("command") or "").strip()
                if not command:
                    active = self._capture_and_transcribe(activation="wake_followup")
                    active.metadata["wake_transcript"] = heard.transcript
                    active.metadata["wake_mode"] = mode
                    return active
                return TranscriptResult(
                    transcript=command,
                    provider=heard.provider,
                    confidence=heard.confidence,
                    duration_ms=heard.duration_ms,
                    metadata={"wake_transcript": heard.transcript, "wake_mode": mode},
                )
        if mode == "transcript_degraded" and self.transcript_wake_fallback:
            self.state.transition("DEGRADED", reason="legacy_transcript_wake_fallback")
            data = self.transcript_wake_fallback()
            return TranscriptResult(str(data.get("transcript") or ""), str(data.get("provider") or "transcript_fallback"), error_code=data.get("error_code"), metadata={"wake_mode": mode, **data})
        return TranscriptResult("", mode, error_code="wake_unavailable")

    def _capture_and_transcribe(self, activation: str) -> TranscriptResult:
        wake_probe = activation == "transcript_wake"
        hotkey_wait = activation == "hotkey_wait"
        recoverable_probe = wake_probe or hotkey_wait
        if wake_probe:
            self.state.transition("WAKE_LISTENING", reason="transcript_fallback_probe", wake_mode=self.active_wake_mode())
        else:
            self.state.transition("COMMAND_LISTENING", reason=activation, activation_source=activation)
        speech_started_at = int(time.perf_counter() * 1000)
        capture = self.recorder.capture_command()
        speech_ended_at = int(time.perf_counter() * 1000)
        if not capture.speech_detected:
            if wake_probe:
                self.state.transition("WAKE_LISTENING", reason=capture.error_code or "no_speech", wake_mode=self.active_wake_mode())
            elif hotkey_wait:
                self.state.transition("COMMAND_LISTENING", reason=capture.error_code or "no_speech", activation_source=activation)
            else:
                self.state.transition("FAILED", reason=capture.error_code or "no_speech")
            return TranscriptResult(
                "",
                self.stt.provider,
                duration_ms=capture.duration_ms,
                error_code=capture.error_code or "no_speech",
                metadata={"command_speech_started_at": speech_started_at, "command_speech_ended_at": speech_ended_at, "recoverable": recoverable_probe},
            )
        self.state.transition("TRANSCRIBING", reason=activation, audio_ms=capture.duration_ms, rms_peak=capture.rms_peak)
        stt_started_at = int(time.perf_counter() * 1000)
        try:
            result = self.stt.transcribe(capture, quiet_failures=recoverable_probe)
        except TypeError as exc:
            # Keep older/custom STT adapters compatible while the common
            # quiet-failure option rolls through every provider implementation.
            if "quiet_failures" not in str(exc):
                raise
            result = self.stt.transcribe(capture)
        result.metadata.setdefault("command_speech_started_at", speech_started_at)
        result.metadata.setdefault("command_speech_ended_at", speech_ended_at)
        result.metadata.setdefault("stt_started_at", stt_started_at)
        result.metadata.setdefault("stt_completed_at", int(time.perf_counter() * 1000))
        if not result.transcript:
            if wake_probe:
                result.error_code = result.error_code or "empty_transcript"
                result.metadata["recoverable"] = True
                self.state.transition("WAKE_LISTENING", reason=result.error_code, wake_mode=self.active_wake_mode())
            elif hotkey_wait:
                result.error_code = result.error_code or "empty_transcript"
                result.metadata["recoverable"] = True
                self.state.transition("COMMAND_LISTENING", reason=result.error_code, activation_source=activation)
            else:
                self.state.transition("FAILED", reason=result.error_code or "empty_transcript")
        else:
            if wake_probe:
                self.state.transition("WAKE_LISTENING", reason="transcript_fallback_probe_complete", wake_mode=self.active_wake_mode())
            else:
                self.state.transition("ROUTING", reason=activation)
        return result

    def close(self) -> None:
        self.microphone.close()
        if self.state.state != "STOPPED":
            with suppress_transition_errors(self.state):
                self.state.transition("STOPPED", reason="voice_engine_closed")


class suppress_transition_errors:
    def __init__(self, state: VoiceStateMachine):
        self.state = state

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return True
