from __future__ import annotations

import re
import time

from long_term_memory.memory_store import MemoryStoreAdapter
from long_term_memory.models import MemoryQuery, MemoryRetrievalResult


class MemoryRetriever:
    def __init__(self, store: MemoryStoreAdapter) -> None:
        self.store = store

    def retrieve(self, query: MemoryQuery) -> MemoryRetrievalResult:
        memories = self.store.list(query.user_id)
        if query.memory_type:
            memories = [item for item in memories if item.type == query.memory_type]
        terms = self._terms(query.text)
        scored = []
        for item in memories:
            score = self._score(item, terms)
            if score > 0 or not terms:
                item.last_used_at = time.time()
                scored.append((score, item))
        scored.sort(key=lambda pair: (pair[0], pair[1].importance, pair[1].updated_at), reverse=True)
        selected = [item for _, item in scored[: query.limit]]
        return MemoryRetrievalResult(memories=selected, confidence=min(1.0, scored[0][0] / 5.0) if scored else 0.0, reason="lexical_relevance")

    def _terms(self, text: str) -> list[str]:
        stop = {"what", "about", "open", "my", "the", "that", "this", "remember", "forget", "project"}
        return [term for term in re.findall(r"[a-zA-Z][a-zA-Z0-9_.-]{2,}", str(text or "").lower()) if term not in stop]

    def _score(self, item, terms: list[str]) -> float:
        hay = f"{item.content} {item.structured_data}".lower()
        return sum(2 if term in item.content.lower() else 1 for term in terms if term in hay)
