from __future__ import annotations

import contextlib
import audioop
import os
import sys
import threading
import time

import pyaudio

from voice.models import VoiceConfig


class MicrophoneService:
    def __init__(self, config: VoiceConfig):
        self.config = config
        self._pa: pyaudio.PyAudio | None = None
        self._stream = None
        self._lock = threading.RLock()
        self.device_info: dict = {}
        self.last_frame_at = 0.0
        self.stream_sample_rate = int(config.sample_rate)
        self.stream_frame_length = int(config.frame_length)
        self.open_count = 0
        self.close_count = 0
        self._ratecv_state = None

    def open(self) -> None:
        with self._lock:
            if self._stream is not None:
                return
            self._pa = pyaudio.PyAudio()
            device_index = self.config.microphone_device_index
            with contextlib.suppress(Exception):
                if device_index is None:
                    device_index = int(self._pa.get_default_input_device_info().get("index"))
                self.device_info = self._pa.get_device_info_by_index(int(device_index))
            default_rate = int(float(self.device_info.get("defaultSampleRate") or self.config.sample_rate))
            requested_rate = int(self.config.sample_rate)
            stream_rate = requested_rate
            with contextlib.suppress(Exception):
                supported = self._pa.is_format_supported(
                    requested_rate,
                    input_device=device_index,
                    input_channels=self.config.channels,
                    input_format=pyaudio.paInt16,
                )
                if not supported:
                    stream_rate = default_rate
            self.stream_sample_rate = int(stream_rate)
            self.stream_frame_length = max(1, int(round(self.config.frame_length * (self.stream_sample_rate / requested_rate))))
            kwargs = {
                "format": pyaudio.paInt16,
                "channels": self.config.channels,
                "rate": self.stream_sample_rate,
                "input": True,
                "frames_per_buffer": self.stream_frame_length,
            }
            if device_index is not None:
                kwargs["input_device_index"] = device_index
            self._stream = self._pa.open(**kwargs)
            self.last_frame_at = time.time()
            self.open_count += 1
            name = self.device_info.get("name") or "default microphone"
            sys.stderr.write(
                "[CEASER Voice] microphone_opened "
                f"name={name!r} requested_sample_rate={requested_rate} device_default_rate={default_rate} "
                f"stream_sample_rate={self.stream_sample_rate} target_frame_length={self.config.frame_length} "
                f"stream_frame_length={self.stream_frame_length} open_count={self.open_count}\n"
            )
            sys.stderr.flush()

    def read_frame(self) -> bytes:
        with self._lock:
            if self._stream is None:
                self.open()
            try:
                frame = self._stream.read(self.stream_frame_length, exception_on_overflow=False)
            except OSError as exc:
                sys.stderr.write(f"[CEASER Voice] microphone_read_failed reason={type(exc).__name__}; reopening stream\n")
                sys.stderr.flush()
                self.reopen()
                frame = self._stream.read(self.stream_frame_length, exception_on_overflow=False)
            self.last_frame_at = time.time()
            return self._to_target_audio_frame(frame)

    def _to_target_audio_frame(self, frame: bytes) -> bytes:
        target_bytes = int(self.config.frame_length) * int(self.config.sample_width)
        if self.stream_sample_rate != int(self.config.sample_rate):
            try:
                frame, self._ratecv_state = audioop.ratecv(
                    frame,
                    int(self.config.sample_width),
                    int(self.config.channels),
                    int(self.stream_sample_rate),
                    int(self.config.sample_rate),
                    self._ratecv_state,
                )
            except Exception as exc:  # noqa: BLE001 - keep wake degraded, not crashed.
                sys.stderr.write(f"[CEASER Voice] microphone_resample_failed reason={type(exc).__name__}\n")
                sys.stderr.flush()
        if len(frame) < target_bytes:
            frame += b"\x00" * (target_bytes - len(frame))
        elif len(frame) > target_bytes:
            frame = frame[:target_bytes]
        return frame

    def healthy(self) -> bool:
        return self._stream is not None and (time.time() - self.last_frame_at) < 8

    def reopen(self) -> None:
        self.close()
        self.open()

    def close(self) -> None:
        with self._lock:
            if self._stream is not None:
                with contextlib.suppress(Exception):
                    self._stream.stop_stream()
                with contextlib.suppress(Exception):
                    self._stream.close()
            self._stream = None
            if self._pa is not None:
                with contextlib.suppress(Exception):
                    self._pa.terminate()
            self._pa = None
            self.close_count += 1
            self._ratecv_state = None
            sys.stderr.write(f"[CEASER Voice] microphone_closed close_count={self.close_count}\n")
            sys.stderr.flush()


def configured_device_index() -> int | None:
    raw = os.getenv("CEASER_MIC_DEVICE_INDEX")
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except ValueError:
        return None
