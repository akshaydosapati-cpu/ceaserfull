from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
import time
from typing import Callable


VALID_TRANSITIONS = {
    "STOPPED": {"STARTING"},
    "STARTING": {"WAKE_LISTENING", "COMMAND_LISTENING", "DEGRADED", "RECOVERING", "STOPPED"},
    "WAKE_LISTENING": {"WAKE_DETECTED", "COMMAND_LISTENING", "TRANSCRIBING", "RECOVERING", "DEGRADED", "STOPPED"},
    "WAKE_DETECTED": {"COMMAND_LISTENING", "TRANSCRIBING", "RECOVERING", "STOPPED"},
    "COMMAND_LISTENING": {"TRANSCRIBING", "FAILED", "RECOVERING", "WAKE_LISTENING", "FOLLOW_UP_LISTENING", "STOPPED"},
    "TRANSCRIBING": {"WAKE_DETECTED", "ROUTING", "FAILED", "RECOVERING", "WAKE_LISTENING", "COMMAND_LISTENING", "STOPPED"},
    "ROUTING": {"EXECUTING", "COMMAND_LISTENING", "WAKE_LISTENING", "FAILED", "RECOVERING", "STOPPED"},
    "EXECUTING": {"SPEAKING", "WAKE_LISTENING", "FAILED", "COMPLETED", "RECOVERING", "STOPPED"},
    "SPEAKING": {"INTERRUPTED", "FOLLOW_UP_LISTENING", "WAKE_LISTENING", "STOPPED", "RECOVERING"},
    "INTERRUPTED": {"FOLLOW_UP_LISTENING", "COMMAND_LISTENING", "WAKE_LISTENING", "STOPPED"},
    "FOLLOW_UP_LISTENING": {"COMMAND_LISTENING", "TRANSCRIBING", "ROUTING", "FAILED", "WAKE_LISTENING", "STOPPED"},
    "COMPLETED": {"FOLLOW_UP_LISTENING", "WAKE_LISTENING", "STOPPED"},
    "FAILED": {"WAKE_LISTENING", "COMMAND_LISTENING", "RECOVERING", "STOPPED"},
    "RECOVERING": {"WAKE_LISTENING", "DEGRADED", "STOPPED"},
    "DEGRADED": {"WAKE_LISTENING", "COMMAND_LISTENING", "RECOVERING", "STOPPED"},
}


@dataclass
class VoiceStateMachine:
    session_id: str
    emit: Callable[[str, dict], None] | None = None
    state: str = "STOPPED"
    history: list[dict] = field(default_factory=list)

    def transition(self, state: str, reason: str = "", **payload) -> dict:
        allowed = VALID_TRANSITIONS.get(self.state, set())
        if state not in allowed and state != self.state:
            raise ValueError(f"invalid voice transition {self.state}->{state}")
        self.state = state
        event = {
            "state": state.lower(),
            "reason": reason,
            "session_id": self.session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **payload,
        }
        self.history.append(event)
        if self.emit:
            self.emit("voice_state", event)
        return event


CONTROL_PATTERN = re.compile(r"^\s*(stop|cancel|wait|never mind|nevermind)\s*[.!?]?\s*$", re.IGNORECASE)
REPEAT_PATTERN = re.compile(r"^\s*(repeat|say that again|say it again)\s*[.!?]?\s*$", re.IGNORECASE)
CONTINUE_PATTERN = re.compile(r"^\s*(continue|go on|keep going)\s*[.!?]?\s*$", re.IGNORECASE)
CORRECTION_PATTERN = re.compile(r"^\s*(actually|no[, ]+|not that one|use .* instead|the previous project)\b", re.IGNORECASE)


@dataclass
class ConversationalVoiceController:
    follow_up_seconds: float = 35.0
    now: Callable[[], float] = time.time
    state: str = "IDLE"
    tts_playing: bool = False
    capture_active: bool = False
    follow_up_until: float = 0.0
    last_command: str = ""
    last_overlay_response: str = ""
    last_spoken_response: str = ""
    pending_command: str = ""
    execution_count: int = 0

    def begin_speaking(self, overlay_response: str, spoken_response: str | None = None) -> None:
        self.tts_playing = True
        self.capture_active = False
        self.state = "SPEAKING"
        self.last_overlay_response = str(overlay_response or "")
        self.last_spoken_response = str(spoken_response or overlay_response or "")

    def end_speaking(self) -> None:
        self.tts_playing = False
        self.open_follow_up_window()

    def interrupt(self, command: str = "") -> dict:
        self.tts_playing = False
        self.capture_active = False
        self.state = "INTERRUPTED"
        self.open_follow_up_window()
        return {"status": "cancelled", "message": "Stopped.", "transcript": command, "voice_control": "interrupt"}

    def open_follow_up_window(self) -> None:
        self.follow_up_until = self.now() + self.follow_up_seconds
        self.state = "FOLLOW_UP_LISTENING"

    def expire_follow_up_if_needed(self) -> bool:
        if self.state == "FOLLOW_UP_LISTENING" and self.now() > self.follow_up_until:
            self.state = "IDLE"
            self.follow_up_until = 0.0
            return True
        return False

    def should_accept_without_wake(self) -> bool:
        self.expire_follow_up_if_needed()
        return self.state == "FOLLOW_UP_LISTENING" and self.now() <= self.follow_up_until

    def begin_capture(self) -> bool:
        if self.tts_playing or self.capture_active:
            return False
        self.capture_active = True
        self.state = "COMMAND_LISTENING"
        return True

    def end_capture(self) -> None:
        self.capture_active = False

    def handle_control(self, command: str) -> dict | None:
        text = str(command or "").strip()
        if not text:
            return None
        if CONTROL_PATTERN.match(text):
            self.pending_command = ""
            self.open_follow_up_window()
            return {"status": "cancelled", "message": "Cancelled.", "transcript": text, "voice_control": "cancel"}
        if REPEAT_PATTERN.match(text):
            message = self.last_overlay_response or self.last_spoken_response or "I do not have anything to repeat yet."
            self.open_follow_up_window()
            return {"status": "completed", "message": message, "spoken_response": self.last_spoken_response or message, "transcript": text, "voice_control": "repeat"}
        if CONTINUE_PATTERN.match(text):
            return {"status": "continue", "message": "continue", "transcript": text, "voice_control": "continue"}
        return None

    def normalize_correction(self, command: str) -> tuple[str, bool]:
        text = str(command or "").strip()
        if not CORRECTION_PATTERN.search(text):
            return text, False
        cleaned = re.sub(r"^\s*(actually|no[, ]+)\s*", "", text, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"^\s*not that one[, ]*", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"\bthe previous project\b", "previous project", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"\s+instead\s*$", "", cleaned, flags=re.IGNORECASE).strip()
        if not cleaned and self.pending_command:
            cleaned = self.pending_command
        return cleaned or text, True

    def record_execution(self, command: str, response: dict) -> dict:
        self.execution_count += 1
        self.last_command = str(command or "").strip()
        self.pending_command = ""
        self.last_overlay_response = str(response.get("message") or self.last_overlay_response or "")
        self.last_spoken_response = str(response.get("spoken_response") or response.get("message") or self.last_spoken_response or "")
        self.open_follow_up_window()
        return response

    def mark_pending(self, command: str) -> None:
        self.pending_command = str(command or "").strip()
