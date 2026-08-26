from __future__ import annotations

import re


class EntityExtractor:
    _ORDINALS = {
        "first": 1, "1st": 1, "one": 1,
        "second": 2, "2nd": 2, "two": 2,
        "third": 3, "3rd": 3, "three": 3,
        "fourth": 4, "4th": 4, "four": 4,
    }

    def extract(self, text: str) -> dict:
        lowered = str(text or "").lower().strip()
        entities: dict = {}
        level = re.search(r"\b(\d{1,3})\s*(?:%|percent)?\b", lowered)
        if level:
            entities["level"] = max(0, min(100, int(level.group(1))))
        duration = re.search(r"\b(\d+)\s*(seconds?|secs?|minutes?|mins?)\b", lowered)
        if duration:
            seconds = int(duration.group(1)) * (60 if duration.group(2).startswith(("min", "minute")) else 1)
            entities["seconds"] = seconds
        ordinal = next((index for word, index in self._ORDINALS.items() if re.search(rf"\b{re.escape(word)}\b", lowered)), None)
        if ordinal:
            entities["index"] = ordinal
        if re.search(r"\b(this|current|active)\s+(tab|page)\b", lowered):
            entities.update({"object_type": "browser_tab", "target": "active_tab"})
        tab = re.search(r"(?:close|switch to|go to|find)\s+(?:the\s+)?(.+?)\s+(?:browser\s+)?(?:tab|page)\b", lowered)
        if tab and not entities.get("target"):
            target = tab.group(1).strip()
            entities.update({"object_type": "browser_tab", "target": target})
        return entities

