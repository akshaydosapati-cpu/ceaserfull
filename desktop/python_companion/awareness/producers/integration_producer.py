from __future__ import annotations

from typing import Callable

from awareness.event_sources import EventFactory
from awareness.models import AwarenessEvent
from awareness.producers.base import EventProducer


class IntegrationProducer(EventProducer):
    name = "integration"
    poll_interval_seconds = 60.0

    def __init__(self, emit=None, status_probe: Callable[[], list[dict]] | None = None) -> None:
        super().__init__(emit)
        self.status_probe = status_probe or (lambda: [])
        self.factory = EventFactory()
        self._last_status: dict[str, str] = {}

    def normalize_event(self, raw: dict) -> AwarenessEvent | None:
        provider = str(raw.get("provider") or "integration")
        status = str(raw.get("status") or "")
        if not provider or not status:
            return None
        event_type = self._event_type(provider, status)
        return self.factory.integration(event_type, raw.get("title", f"{provider.title()} {status}"), raw.get("summary", ""), {"provider": provider, "status": status})

    def _poll(self, context: dict) -> list[AwarenessEvent]:
        events: list[AwarenessEvent] = []
        for item in self.status_probe():
            provider = str(item.get("provider") or "")
            status = str(item.get("status") or "")
            if not provider or not status:
                continue
            previous = self._last_status.get(provider)
            if previous == status:
                continue
            self._last_status[provider] = status
            event_type = self._event_type(provider, status)
            title = f"{provider.title()} sync failed" if "failed" in status else f"{provider.title()} sync complete" if "synced" in status or "complete" in status else f"{provider.title()} disconnected"
            events.append(self.factory.integration(event_type, title, item.get("summary", title), {"provider": provider, "status": status, "error": item.get("error", "")}))
        return events

    def _event_type(self, provider: str, status: str) -> str:
        lowered = status.lower()
        if "token" in lowered:
            return "token_refresh_failure"
        if "disconnect" in lowered:
            return "integration_disconnected"
        if "failed" in lowered or "error" in lowered:
            return f"{provider.lower()}_sync_failed"
        return f"{provider.lower()}_sync_complete"
