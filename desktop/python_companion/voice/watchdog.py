from __future__ import annotations

import time

from voice.microphone import MicrophoneService


class VoiceWatchdog:
    def __init__(self, microphone: MicrophoneService):
        self.microphone = microphone

    def ensure_healthy(self) -> bool:
        if self.microphone.healthy():
            return True
        self.microphone.reopen()
        return self.microphone.healthy()
