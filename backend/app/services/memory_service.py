from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.memory import Memory
from app.repositories.memory_repository import MemoryRepository


class MemoryService:
    def __init__(self, db: Session):
        self.memories = MemoryRepository(db)
        self.db = db

    def list(self, user_id: str | None = None) -> list[Memory]:
        return self.memories.list(user_id=user_id)

    def get(self, memory_id: str) -> Memory | None:
        return self.memories.get(memory_id)

    def create(self, user_id: str, memory_type: str, content: str, metadata: dict, *, commit: bool = True) -> Memory:
        now = datetime.now(timezone.utc).isoformat()
        metadata = {
            "source": "user",
            "confidence_score": 1.0,
            "importance": 0.8,
            "reinforcement_count": 1,
            "access_count": 0,
            "status": "active",
            **dict(metadata or {}),
        }
        existing = self.memories.find_exact(user_id=user_id, memory_type=memory_type, content=content)
        if existing:
            current = dict(existing.extra_metadata or {})
            current.update({key: value for key, value in metadata.items() if key not in {"reinforcement_count", "confidence_score"}})
            current["reinforcement_count"] = int(current.get("reinforcement_count") or 1) + 1
            current["confidence_score"] = min(1.0, max(float(current.get("confidence_score") or 0), float(metadata.get("confidence_score") or 0)) + 0.02)
            current["last_reinforced_at"] = now
            existing.extra_metadata = current
            memory = existing
        else:
            identity = self._identity(memory_type, content, metadata)
            memory = self.memories.create(user_id=user_id, memory_type=memory_type, content=content, metadata=metadata)
            if identity:
                for current in self.memories.list(user_id=user_id):
                    if current.id == memory.id or self._identity(current.memory_type, current.content, current.extra_metadata) != identity:
                        continue
                    current_metadata = dict(current.extra_metadata or {})
                    current_metadata.update({"status": "superseded", "superseded_by": memory.id, "superseded_at": now})
                    current.extra_metadata = current_metadata
        if commit:
            self.db.commit()
            self.db.refresh(memory)
        return memory

    def search(self, query: str, user_id: str | None = None) -> list[Memory]:
        return self.memories.search(query=query, user_id=user_id)

    def delete(self, memory: Memory) -> None:
        self.memories.delete(memory)
        self.db.commit()

    @staticmethod
    def _identity(memory_type: str, content: str, metadata: dict) -> tuple[str, str, str] | None:
        entity = str(metadata.get("entity") or "").strip().lower()
        relation = str(metadata.get("relation") or "").strip().lower()
        if not entity and memory_type == "file":
            match = re.match(r"(.+?)\s+is\s+in\s+(.+)", content, re.IGNORECASE)
            if match:
                entity, relation = match.group(1).strip().lower(), "location"
        return (memory_type, entity, relation) if entity and relation else None
