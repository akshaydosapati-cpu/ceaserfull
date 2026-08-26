"""Small in-process state model for local media intent resolution."""

from dataclasses import dataclass
import re
from typing import Literal


MediaStatus = Literal["playing", "paused", "stopped", "unknown"]
MediaAction = Literal["pause", "resume", "generic_play", "new_playback", "stop", "other"]


@dataclass(frozen=True)
class MediaResolution:
    action: MediaAction
    query: str = ""


class MediaStateTracker:
    _GENERIC_PAUSE = re.compile(r"^(?:pause|pause music|pause song|pause the music)$", re.I)
    _GENERIC_PLAY = re.compile(
        r"^(?:play|play music|play song|play the music|play the song|play it|"
        r"resume|resume music|resume song|resume the music|resume the song|resume it|"
        r"continue|continue music|continue the music|continue the song|continue it)$",
        re.I,
    )
    _STOP = re.compile(r"^(?:stop music|stop playback|stop song)$", re.I)
    _NEW_PLAYBACK = re.compile(r"^play\s+(.+)$", re.I)

    def __init__(self) -> None:
        self.status: MediaStatus = "unknown"
        self.target = ""

    def resolve(self, command: str) -> MediaResolution:
        text = " ".join(str(command or "").strip().split())
        if self._GENERIC_PAUSE.fullmatch(text):
            return MediaResolution("pause")
        if self._STOP.fullmatch(text):
            return MediaResolution("stop")
        if self._GENERIC_PLAY.fullmatch(text):
            return MediaResolution("resume" if self.status == "paused" else "generic_play")
        match = self._NEW_PLAYBACK.fullmatch(text)
        if match:
            return MediaResolution("new_playback", match.group(1).strip())
        return MediaResolution("other")

    def normalize_for_routing(self, command: str) -> str:
        if self.resolve(command).action == "resume":
            return "resume music"
        return command

    def record(self, action: MediaAction, target: str = "") -> None:
        if action in {"resume", "generic_play", "new_playback"}:
            self.status = "playing"
        elif action == "pause":
            self.status = "paused"
        elif action == "stop":
            self.status = "stopped"
        if target:
            self.target = target
