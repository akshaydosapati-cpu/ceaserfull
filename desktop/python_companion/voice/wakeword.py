from __future__ import annotations

import os
import platform
import sys
import contextlib
from importlib import metadata
from pathlib import Path

from voice.microphone import MicrophoneService
from voice.models import VoiceConfig


class PorcupineWakeDetector:
    def __init__(self, config: VoiceConfig, model_path: str):
        self.config = config
        self.model_path = model_path
        self.porcupine = None
        self.available = False
        self.degraded_reason = ""
        self.required_sample_rate = int(config.sample_rate)
        self.required_frame_length = int(config.frame_length)

    def _access_key(self) -> str:
        return (
            os.getenv("PICOVOICE_ACCESS_KEY")
            or os.getenv("PICOVOICE_KEY")
            or os.getenv("PV_ACCESS_KEY")
            or os.getenv("PV_PORCUPINE_ACCESS_KEY")
            or os.getenv("CEASER_PICOVOICE_ACCESS_KEY")
            or ""
        )

    def initialize(self) -> None:
        model_path = Path(self.model_path).expanduser().resolve()
        self.model_path = str(model_path)
        model_exists = model_path.exists()
        porcupine_version = "unknown"
        access_key = self._access_key()
        base = (
            f"key_exists={bool(access_key)} resolved_model_path={str(model_path)!r} model_exists={model_exists} "
            f"platform={platform.system()}-{platform.release()} arch={platform.machine()} "
        )
        try:
            import pvporcupine
            porcupine_version = getattr(pvporcupine, "__version__", "") or porcupine_version
            with contextlib.suppress(Exception):
                porcupine_version = metadata.version("pvporcupine")

            if not access_key:
                raise RuntimeError("Picovoice access key missing from supported environment variables")
            self.porcupine = pvporcupine.create(
                access_key=access_key,
                keyword_paths=[self.model_path],
                sensitivities=[self.config.wake_sensitivity],
            )
            expected_sample_rate = int(self.porcupine.sample_rate)
            expected_frame_length = int(self.porcupine.frame_length)
            self.required_sample_rate = expected_sample_rate
            self.required_frame_length = expected_frame_length
            self.config.sample_rate = expected_sample_rate
            self.config.frame_length = expected_frame_length
            self.available = True
            sys.stderr.write(
                "[CEASER Voice] porcupine_ready "
                f"{base}version={porcupine_version} "
                f"required_sample_rate={expected_sample_rate} required_frame_length={expected_frame_length}\n"
            )
            sys.stderr.flush()
        except Exception as exc:  # noqa: BLE001 - degraded mode is intentional.
            self.available = False
            self.degraded_reason = f"{type(exc).__name__}: {str(exc)[:180]}"
            sys.stderr.write(
                "[CEASER Voice] porcupine_degraded "
                f"{base}exception_type={type(exc).__name__} exception_message={str(exc)[:220]!r} "
                f"version={porcupine_version} required_sample_rate={self.required_sample_rate} "
                f"required_frame_length={self.required_frame_length} microphone_sample_rate=unopened microphone_frame_length=unopened\n"
            )
            sys.stderr.flush()

    def log_runtime_audio_details(self, microphone: MicrophoneService) -> None:
        sys.stderr.write(
            "[CEASER Voice] porcupine_audio_runtime "
            f"available={self.available} required_sample_rate={self.required_sample_rate} "
            f"required_frame_length={self.required_frame_length} "
            f"microphone_sample_rate={getattr(microphone, 'stream_sample_rate', '')} "
            f"microphone_frame_length={getattr(microphone, 'stream_frame_length', '')}\n"
        )
        sys.stderr.flush()

    def wait_for_wake(self, microphone: MicrophoneService, timeout_seconds: float | None = None) -> bool:
        if not self.available or self.porcupine is None:
            return False
        import struct
        import time

        started = time.perf_counter()
        while True:
            pcm = microphone.read_frame()
            expected_bytes = int(self.required_frame_length) * int(self.config.sample_width)
            if len(pcm) != expected_bytes:
                sys.stderr.write(
                    "[CEASER Voice] porcupine_frame_mismatch "
                    f"expected_bytes={expected_bytes} actual_bytes={len(pcm)} "
                    f"expected_sample_rate={self.required_sample_rate} expected_frame_length={self.required_frame_length} "
                    f"actual_sample_rate={getattr(microphone, 'stream_sample_rate', '')} "
                    f"actual_frame_length={getattr(microphone, 'stream_frame_length', '')}\n"
                )
                sys.stderr.flush()
                if len(pcm) < expected_bytes:
                    pcm += b"\x00" * (expected_bytes - len(pcm))
                else:
                    pcm = pcm[:expected_bytes]
            frame = struct.unpack_from("h" * self.required_frame_length, pcm)
            if self.porcupine.process(frame) >= 0:
                return True
            if timeout_seconds and time.perf_counter() - started >= timeout_seconds:
                return False
