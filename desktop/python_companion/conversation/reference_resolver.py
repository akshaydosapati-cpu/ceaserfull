from __future__ import annotations

import re
from typing import Any


FOLLOW_UP_PATTERN = re.compile(
    r"\b(this|that|it|them|him|her|previous|last|continue|again|summarize it|explain it|save it|open it|send it|make it|fix it)\b",
    re.IGNORECASE,
)


class ReferenceResolver:
    def is_follow_up(self, text: str) -> bool:
        return bool(FOLLOW_UP_PATTERN.search(str(text or "")))

    def resolve(self, text: str, session_snapshot: dict[str, Any]) -> dict[str, Any]:
        if not self.is_follow_up(text):
            return {"follow_up_detected": False, "resolved_reference": None}
        last = session_snapshot.get("last_result") or {}
        resource = session_snapshot.get("active_resource") or {}
        return {
            "follow_up_detected": True,
            "resolved_reference": {
                "last_intent": session_snapshot.get("last_intent"),
                "last_capability": session_snapshot.get("last_capability"),
                "last_summary": last.get("summary"),
                "active_resource": resource,
            },
        }
