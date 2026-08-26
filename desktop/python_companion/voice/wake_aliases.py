from __future__ import annotations

import re


_WAKE_ALIASES = r"(?:ceaser|cesaer|caesar|cesar|seizure|seizer)"
_WAKE_ALIASES_WITH_SEASON = r"(?:ceaser|cesaer|caesar|cesar|season|seizure|seizer)"
_LEADING_WAKE_WORDS = r"(?:hey|hi|hello|ok|okay|a)"

WAKE_PREFIX_PATTERN = re.compile(
    rf"^\s*(?:(?:{_LEADING_WAKE_WORDS})\s+{_WAKE_ALIASES_WITH_SEASON}|{_WAKE_ALIASES})\b[\s,.:;-]*",
    re.IGNORECASE,
)

IGNORED_COMMAND_PREFIX = re.compile(r"^(?:please|can you|could you|would you)\s+", re.IGNORECASE)


def strip_wake_prefix(transcript: str) -> str:
    source = str(transcript or "").replace("\n", " ").strip()
    if not source:
        return ""
    return WAKE_PREFIX_PATTERN.sub("", source, count=1).strip(" ,.:;-")


def extract_wake_command(transcript: str) -> dict:
    source = str(transcript or "").replace("\n", " ").strip()
    if not source:
        return {"woke": False, "command": ""}
    match = WAKE_PREFIX_PATTERN.match(source)
    if not match:
        return {"woke": False, "command": ""}
    command = source[match.end():].strip(" ,.:;-")
    command = IGNORED_COMMAND_PREFIX.sub("", command).strip()
    return {"woke": True, "command": command}
