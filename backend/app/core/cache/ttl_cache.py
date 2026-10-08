from __future__ import annotations

import time
import threading
from typing import Any


class TTLCache:
    def __init__(self, max_items: int = 512) -> None:
        self._items: dict[str, tuple[float, Any]] = {}
        self._max_items = max_items
        self._lock = threading.RLock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._items.get(key)
            if not item:
                return None
            expires_at, value = item
            if expires_at <= time.time():
                self._items.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        now = time.time()
        with self._lock:
            expired = [item_key for item_key, (expires_at, _) in self._items.items() if expires_at <= now]
            for item_key in expired:
                self._items.pop(item_key, None)
            if key not in self._items and len(self._items) >= self._max_items:
                oldest_key = min(self._items, key=lambda item_key: self._items[item_key][0])
                self._items.pop(oldest_key, None)
            self._items[key] = (now + ttl_seconds, value)


ttl_cache = TTLCache()
