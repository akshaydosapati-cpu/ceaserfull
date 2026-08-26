from __future__ import annotations

import time

from awareness.models import AwarenessEvent


class EventQueue:
    def __init__(self, max_events: int = 300) -> None:
        self.max_events = max_events
        self._events: list[AwarenessEvent] = []

    def enqueue(self, event: AwarenessEvent) -> AwarenessEvent:
        self.expire()
        duplicate = self._find_duplicate(event)
        if duplicate:
            duplicate.payload.update(event.payload)
            duplicate.summary = event.summary or duplicate.summary
            duplicate.importance = max(duplicate.importance, event.importance)
            duplicate.status = "queued"
            return duplicate
        self._events.append(event)
        self._events = self._events[-self.max_events :]
        return event

    def recent(self, limit: int = 20, *, status: str | None = None) -> list[AwarenessEvent]:
        self.expire()
        items = [event for event in self._events if status is None or event.status == status]
        return sorted(items, key=lambda item: item.created_at, reverse=True)[:limit]

    def mark(self, event_id: str, status: str) -> None:
        for event in self._events:
            if event.id == event_id:
                event.status = status  # type: ignore[assignment]
                return

    def expire(self) -> None:
        now = time.time()
        self._events = [event for event in self._events if event.expires_at is None or event.expires_at > now]

    def _find_duplicate(self, event: AwarenessEvent) -> AwarenessEvent | None:
        if not event.dedupe_key:
            return None
        for current in reversed(self._events):
            if current.dedupe_key == event.dedupe_key and time.time() - current.created_at < 300:
                return current
        return None
