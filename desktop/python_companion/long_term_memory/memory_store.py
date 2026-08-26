from __future__ import annotations

import json
import time
from pathlib import Path

from long_term_memory.models import LongTermMemoryItem


class MemoryStoreAdapter:
    def save(self, item: LongTermMemoryItem) -> LongTermMemoryItem:
        raise NotImplementedError

    def list(self, user_id: str) -> list[LongTermMemoryItem]:
        raise NotImplementedError

    def delete(self, user_id: str, memory_id: str) -> int:
        raise NotImplementedError

    def delete_by_type(self, user_id: str, memory_type: str) -> int:
        raise NotImplementedError


class LocalJsonMemoryStore(MemoryStoreAdapter):
    """Temporary local development adapter until backend memory API is connected."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else Path.home() / ".ceaser" / "long_term_memory.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, item: LongTermMemoryItem) -> LongTermMemoryItem:
        items = self._load()
        existing = next((current for current in items if current.id == item.id), None)
        if existing:
            item.created_at = existing.created_at
            item.updated_at = time.time()
            items = [item if current.id == item.id else current for current in items]
        else:
            items.append(item)
        self._write(items)
        return item

    def list(self, user_id: str) -> list[LongTermMemoryItem]:
        now = time.time()
        return [
            item
            for item in self._load()
            if item.user_id == user_id and item.status == "active" and (item.expires_at is None or item.expires_at > now)
        ]

    def delete(self, user_id: str, memory_id: str) -> int:
        items = self._load()
        count = 0
        for item in items:
            if item.user_id == user_id and item.id == memory_id and item.status == "active":
                item.status = "deleted"
                item.updated_at = time.time()
                count += 1
        self._write(items)
        return count

    def delete_by_type(self, user_id: str, memory_type: str) -> int:
        items = self._load()
        count = 0
        for item in items:
            if item.user_id == user_id and item.type == memory_type and item.status == "active":
                item.status = "deleted"
                item.updated_at = time.time()
                count += 1
        self._write(items)
        return count

    def _load(self) -> list[LongTermMemoryItem]:
        if not self.path.exists():
            return []
        raw = json.loads(self.path.read_text(encoding="utf-8") or "[]")
        return [LongTermMemoryItem(**item) for item in raw]

    def _write(self, items: list[LongTermMemoryItem]) -> None:
        payload = [item.model_dump() if hasattr(item, "model_dump") else item.dict() for item in items]
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
