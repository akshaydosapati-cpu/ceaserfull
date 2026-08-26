from __future__ import annotations

import time
from typing import Any

from working_memory.models import MemoryCategory, MemoryItem


class MemoryStore:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], MemoryItem] = {}

    def set(self, category: MemoryCategory, key: str, value: Any, ttl_seconds: float | None = None, source: str = "") -> None:
        now = time.time()
        self._items[(category, key)] = MemoryItem(
            category=category,
            key=key,
            value=value,
            timestamp=now,
            expires_at=now + ttl_seconds if ttl_seconds else None,
            source=source,
        )

    def get(self, category: MemoryCategory, key: str, default: Any = None) -> Any:
        self.expire()
        item = self._items.get((category, key))
        return item.value if item else default

    def category(self, category: MemoryCategory) -> dict[str, Any]:
        self.expire()
        return {key: item.value for (item_category, key), item in self._items.items() if item_category == category}

    def expire(self) -> None:
        now = time.time()
        expired = [key for key, item in self._items.items() if item.expires_at is not None and item.expires_at <= now]
        for key in expired:
            self._items.pop(key, None)

    def clear(self) -> None:
        self._items.clear()
