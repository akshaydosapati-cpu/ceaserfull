from __future__ import annotations

import audioop
import time
from collections import deque

from voice.microphone import MicrophoneService
from voice.models import AudioCapture, VoiceConfig


class VadRecorder:
    def __init__(self, microphone: MicrophoneService, config: VoiceConfig):
        self.microphone = microphone
        self.config = config

    def capture_command(self) -> AudioCapture:
        frame_ms = int((self.config.frame_length / self.config.sample_rate) * 1000)
        preroll_frames = max(1, int(self.config.preroll_ms / max(frame_ms, 1)))
        preroll: deque[bytes] = deque(maxlen=preroll_frames)
        frames: list[bytes] = []
        started = time.perf_counter()
        last_voice_at = started
        speech_started = False
        rms_peak = 0
        read_failures = 0

        while True:
            try:
                frame = self.microphone.read_frame()
            except OSError:
                read_failures += 1
                if read_failures > 2:
                    raise
                time.sleep(0.1)
                continue
            rms = audioop.rms(frame, self.config.sample_width)
            rms_peak = max(rms_peak, rms)
            now = time.perf_counter()
            if not speech_started:
                preroll.append(frame)
                if rms >= self.config.rms_threshold:
                    speech_started = True
                    frames.extend(preroll)
                    frames.append(frame)
                    last_voice_at = now
                elif now - started >= self.config.speech_start_timeout:
                    return AudioCapture(b"", self.config.sample_rate, self.config.sample_width, int((now - started) * 1000), False, rms_peak, "no_speech")
            else:
                frames.append(frame)
                if rms >= self.config.rms_threshold:
                    last_voice_at = now
                if (now - last_voice_at) * 1000 >= self.config.end_silence_ms:
                    break
                if now - started >= self.config.max_command_seconds:
                    # The ceiling is a valid endpoint, not a failed command.
                    # Transcribe the bounded audio instead of discarding speech.
                    break

        return AudioCapture(b"".join(frames), self.config.sample_rate, self.config.sample_width, int((time.perf_counter() - started) * 1000), True, rms_peak)
