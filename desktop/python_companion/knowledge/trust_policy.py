from __future__ import annotations

import re

from knowledge.models import KnowledgeItem


SECRET_PATTERN = re.compile(
    r"(api[_-]?key|access[_-]?token|refresh[_-]?token|private[_-]?key|password|secret|bearer\s+[a-z0-9._-]+|sk-[a-z0-9]{8,})",
    re.IGNORECASE,
)


class TrustPolicy:
    def is_safe_content(self, content: str) -> bool:
        return not SECRET_PATTERN.search(str(content or ""))

    def allow_item(self, item: KnowledgeItem) -> bool:
        return self.is_safe_content(item.title) and self.is_safe_content(item.content) and self.is_safe_content(str(item.metadata))

    def trust_weight(self, item: KnowledgeItem) -> float:
        return {
            "authoritative": 1.0,
            "trusted": 0.82,
            "informational": 0.62,
            "deprecated": 0.25,
        }.get(item.trust_level, 0.5)
