from __future__ import annotations

import re


class PhraseNormalizer:
    """Normalize conversational command phrasing without changing named targets."""

    _PREFIXES = (
        r"can you\s+",
        r"could you\s+",
        r"would you\s+",
        r"will you\s+",
        r"please\s+",
        r"hey ceaser[,]?\s+",
        r"ceaser[,]?\s+",
    )
    _ALIASES = (
        (r"^(?:bring up|open up|show me|i need)\b", "open"),
        (r"^(?:quit|exit|shut)\b", "close"),
        (r"^(?:make (?:the )?(?:sound|volume) louder|turn (?:the )?sound up|make sound little more)\b", "volume up"),
        (r"^(?:make (?:the )?(?:sound|volume) quieter|turn (?:the )?sound down|make sound little less)\b", "volume down"),
        (r"^(?:screen is too dark|make (?:the )?screen brighter)\b", "brightness up"),
        (r"^(?:screen is too bright|make (?:the )?screen darker|reduce screen)\b", "brightness down"),
        (r"^(?:skip ahead|move ahead|go forward)\b", "forward"),
        (r"^(?:skip back|go backward|go back in (?:the )?(?:video|music)|rewind)\b", "backward"),
        (r"^(?:switch off|turn off)\s+wireless\b", "turn wifi off"),
        (r"^(?:switch on|turn on)\s+wireless\b", "turn wifi on"),
    )

    def normalize(self, value: str) -> str:
        text = re.sub(r"\s+", " ", str(value or "").strip())
        if not text:
            return ""
        lowered = text.lower().strip(" .,!?")
        changed = True
        while changed:
            changed = False
            for prefix in self._PREFIXES:
                updated = re.sub(rf"^{prefix}", "", lowered, count=1)
                if updated != lowered:
                    lowered = updated.strip()
                    changed = True
        for pattern, replacement in self._ALIASES:
            updated = re.sub(pattern, replacement, lowered, count=1)
            if updated != lowered:
                lowered = updated
                break
        lowered = re.sub(r"\b(open|close|start|launch)\s+(?:cheyyi|chey|karo)\b", r"\1", lowered)
        lowered = re.sub(r"\s+please$", "", lowered).strip()
        return lowered
