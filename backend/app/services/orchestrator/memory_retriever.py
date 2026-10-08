from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.memory import Memory
from app.repositories.memory_repository import MemoryRepository

TYPE_WEIGHTS = {
    "project": 8,
    "decision": 7,
    "goal": 6,
    "research": 5,
    "conversation": 4,
    "file": 3,
}


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) > 2}


class MemoryRetriever:
    def __init__(self, db: Session):
        self.memories = MemoryRepository(db)

    def retrieve_relevant_memories(self, user_id: str, query: str, limit: int = 8) -> list[dict]:
        candidates = self.get_recent_memories(user_id, limit=50)
        query_tokens = _tokens(query)
        ranked = [self._rank_memory(memory, query_tokens) for memory in candidates]
        ranked = [memory for memory in ranked if memory["matched_terms"] > 0 and memory["metadata"].get("status", "active") == "active" and not self._expired(memory["metadata"])]
        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked[:limit]

    def search_memories(self, user_id: str, query: str, limit: int = 8) -> list[dict]:
        query_tokens = _tokens(query)
        ranked = [self._rank_memory(memory, query_tokens) for memory in self.memories.search(query=query, user_id=user_id)]
        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked[:limit]

    def get_recent_memories(self, user_id: str, limit: int = 10) -> list[Memory]:
        return self.memories.list(user_id=user_id, limit=limit)

    def get_project_memories(self, user_id: str, limit: int = 10) -> list[dict]:
        memories = self.memories.list(user_id=user_id, limit=200)
        project_memories = [memory for memory in memories if memory.memory_type == "project"]
        return [self._rank_memory(memory, set()) for memory in project_memories[:limit]]

    def _rank_memory(self, memory: Memory, query_tokens: set[str]) -> dict:
        memory_tokens = _tokens(memory.content)
        matched_terms = len(query_tokens & memory_tokens)
        keyword_score = matched_terms * 10
        type_score = TYPE_WEIGHTS.get(memory.memory_type, 1)
        recency_score = self._recency_score(memory.created_at)
        metadata = memory.extra_metadata
        score = keyword_score + type_score + recency_score + float(metadata.get("importance") or 0) + float(metadata.get("confidence_score") or 0)
        return {
            "id": memory.id,
            "user_id": memory.user_id,
            "memory_type": memory.memory_type,
            "content": memory.content,
            "metadata": metadata,
            "created_at": memory.created_at.isoformat(),
            "score": score,
            "matched_terms": matched_terms,
        }

    def _recency_score(self, created_at: datetime) -> float:
        now = datetime.now(timezone.utc)
        value = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
        age_days = max((now - value).days, 0)
        return max(0.0, 5.0 - min(age_days, 5))

    @staticmethod
    def _expired(metadata: dict) -> bool:
        value = metadata.get("expires_at")
        if not value:
            return False
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")) <= datetime.now(timezone.utc)
        except ValueError:
            return False
