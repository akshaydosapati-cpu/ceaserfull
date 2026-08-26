from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from prediction.models import PreparationResult, PreparationTask


class PreparationCache:
    """Small in-memory cache for safe read-only preparation evidence."""

    def __init__(self) -> None:
        self._items: dict[str, tuple[float, dict[str, Any]]] = {}

    def get(self, key: str) -> PreparationResult:
        started = time.perf_counter()
        item = self._items.get(key)
        latency_ms = int((time.perf_counter() - started) * 1000)
        if not item:
            return PreparationResult(key=key, status="cache_miss", latency_ms=latency_ms, cache_hit=False)
        expires_at, data = item
        if expires_at <= time.time():
            self._items.pop(key, None)
            return PreparationResult(key=key, status="expired", latency_ms=latency_ms, cache_hit=False, evidence=["cache_entry_expired"])
        return PreparationResult(
            key=key,
            status="cache_hit",
            latency_ms=latency_ms,
            expires_at=expires_at,
            cache_hit=True,
            data=dict(data),
            evidence=["prepared_context_available"],
        )

    def set(self, key: str, data: dict[str, Any], ttl_seconds: int = 300) -> PreparationResult:
        started = time.perf_counter()
        expires_at = time.time() + max(1, ttl_seconds)
        self._items[key] = (expires_at, dict(data))
        return PreparationResult(
            key=key,
            status="prepared",
            latency_ms=int((time.perf_counter() - started) * 1000),
            expires_at=expires_at,
            cache_hit=False,
            data=dict(data),
            evidence=["read_only_preparation_cached"],
        )

    def prepare(self, task: PreparationTask, loader: Callable[[PreparationTask], dict[str, Any]] | None = None) -> PreparationResult:
        if not task.read_only:
            return PreparationResult(key=task.key, status="skipped", evidence=["preparation_task_not_read_only"])
        cached = self.get(task.key)
        if cached.cache_hit:
            return cached
        started = time.perf_counter()
        data = loader(task) if loader else self._default_payload(task)
        result = self.set(task.key, data, task.ttl_seconds)
        result.latency_ms = int((time.perf_counter() - started) * 1000)
        return result

    def stats(self) -> dict[str, Any]:
        now = time.time()
        active = sum(1 for expires_at, _data in self._items.values() if expires_at > now)
        return {"active_entries": active, "total_entries": len(self._items)}

    def _default_payload(self, task: PreparationTask) -> dict[str, Any]:
        payload = dict(task.payload)
        if task.kind == "git_activity":
            return {
                "prepared": True,
                "provider": task.provider or "github",
                "repository": payload.get("repository", ""),
                "includes": ["git_status", "recent_commits"],
                "read_only": True,
            }
        if task.kind == "repository_activity":
            return {
                "prepared": True,
                "provider": task.provider or "github",
                "repository": payload.get("repository", ""),
                "includes": ["repository_summary", "recent_commits", "open_issues", "pull_requests"],
                "read_only": True,
            }
        if task.kind == "notion_study_metadata":
            return {
                "prepared": True,
                "provider": task.provider or "notion",
                "workspace": payload.get("workspace", ""),
                "includes": ["recent_pages", "study_page_metadata", "database_names"],
                "read_only": True,
            }
        return {"prepared": True, "kind": task.kind, "read_only": True, **payload}
