from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class VoiceConfig:
    wake_mode: str = "porcupine"
    wake_fallback: str = "transcript"
    wake_sensitivity: float = 0.65
    sample_rate: int = 16000
    sample_width: int = 2
    channels: int = 1
    frame_length: int = 512
    speech_start_timeout: float = 4.0
    end_silence_ms: int = 1500
    max_command_seconds: float = 20.0
    preroll_ms: int = 350
    rms_threshold: int = 180
    microphone_device_index: int | None = None


@dataclass
class AudioCapture:
    pcm: bytes
    sample_rate: int
    sample_width: int
    duration_ms: int
    speech_detected: bool
    rms_peak: int = 0
    error_code: str | None = None


@dataclass
class TranscriptResult:
    transcript: str
    provider: str
    confidence: float | None = None
    duration_ms: int = 0
    error_code: str | None = None
    language: str = "English"
    secondary_languages: list[str] = field(default_factory=list)
    code_switched: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
