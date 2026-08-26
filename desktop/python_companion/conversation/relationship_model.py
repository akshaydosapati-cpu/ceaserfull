from __future__ import annotations

import re
from collections import Counter, deque


class RelationshipModel:
    def __init__(self) -> None:
        self._recent_domains: deque[str] = deque(maxlen=30)

    def observe(self, text: str) -> str:
        lowered = str(text or "").lower()
        domain = "general"
        if re.search(r"\b(pdf|exam|study|notes|question|lecture|syllabus|viva)\b", lowered):
            domain = "student"
        elif re.search(r"\b(vs code|github|repo|commit|bug|python|react|api|class|function)\b", lowered):
            domain = "developer"
        elif re.search(r"\b(startup|pitch|marketing|meeting|launch|product|strategy|investor)\b", lowered):
            domain = "founder"
        self._recent_domains.append(domain)
        return domain

    def profile(self) -> dict:
        counts = Counter(self._recent_domains)
        primary = counts.most_common(1)[0][0] if counts else "general"
        return {"primary_mode": primary, "recent_domains": dict(counts)}
