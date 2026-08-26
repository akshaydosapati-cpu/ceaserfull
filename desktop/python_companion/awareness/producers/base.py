from __future__ import annotations

import time
from typing import Any, Callable

from awareness.models import AwarenessEvent


class EventProducer:
    name = "base"
    poll_interval_seconds = 10.0

    def __init__(self, emit: Callable[[AwarenessEvent], Any] | None = None) -> None:
        self.emit = emit or (lambda _event: None)
        self.running = False
        self.last_error = ""
        self.last_polled_at = 0.0
        self.events_emitted = 0
        self.failures = 0
        self._last_fingerprint = ""
        self._last_emit_at: dict[str, float] = {}

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def health(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "running": self.running,
            "last_error": self.last_error,
            "last_polled_at": self.last_polled_at,
            "events_emitted": self.events_emitted,
            "failures": self.failures,
            "poll_interval_seconds": self.poll_interval_seconds,
        }

    def poll_or_watch(self, context: dict | None = None) -> list[AwarenessEvent]:
        self.last_polled_at = time.time()
        try:
            events = self._poll(context or {})
            self.last_error = ""
            for event in events:
                if self._allowed(event):
                    self.emit(event)
                    self.events_emitted += 1
            return events
        except Exception as exc:  # noqa: BLE001 - producer failures are isolated.
            self.failures += 1
            self.last_error = type(exc).__name__
            return []

    def normalize_event(self, raw: dict[str, Any]) -> AwarenessEvent | None:
        raise NotImplementedError

    def _poll(self, context: dict) -> list[AwarenessEvent]:
        return []

    def _allowed(self, event: AwarenessEvent, debounce_seconds: float = 2.0) -> bool:
        fingerprint = event.dedupe_key or f"{event.category}:{event.type}:{event.title}:{event.summary}"
        now = time.time()
        if self._last_fingerprint == fingerprint and now - self._last_emit_at.get(fingerprint, 0) < debounce_seconds:
            return False
        self._last_fingerprint = fingerprint
        self._last_emit_at[fingerprint] = now
        event.payload = self._safe_payload(event.payload)
        return True

    def _safe_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        blocked = {"content", "text", "clipboard_text", "document_text", "audio", "screenshot", "token", "password", "secret", "api_key", "private_key"}
        safe = {}
        for key, value in (payload or {}).items():
            lowered = str(key).lower()
            if lowered in blocked or any(marker in lowered for marker in ("token", "password", "secret", "api_key", "private_key")):
                continue
            safe[key] = value
        return safe
