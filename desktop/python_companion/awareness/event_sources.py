from __future__ import annotations

import hashlib
import time
from typing import Any

from awareness.models import AwarenessEvent


class EventFactory:
    def create(self, *, category: str, event_type: str, source: str, title: str, summary: str = "", payload: dict[str, Any] | None = None, dedupe_key: str = "") -> AwarenessEvent:
        payload = payload or {}
        key = dedupe_key or f"{category}:{event_type}:{source}:{title}:{payload.get('path') or payload.get('repository') or payload.get('id') or ''}"
        event_id = "evt_" + hashlib.sha256(f"{key}:{time.time()}".encode("utf-8")).hexdigest()[:18]
        return AwarenessEvent(
            id=event_id,
            category=category,  # type: ignore[arg-type]
            type=event_type,
            source=source,
            title=title,
            summary=summary,
            payload=payload,
            dedupe_key=key,
        )

    def desktop(self, event_type: str, title: str, summary: str = "", payload: dict[str, Any] | None = None) -> AwarenessEvent:
        return self.create(category="desktop", event_type=event_type, source="desktop", title=title, summary=summary, payload=payload)

    def development(self, event_type: str, title: str, summary: str = "", payload: dict[str, Any] | None = None) -> AwarenessEvent:
        return self.create(category="development", event_type=event_type, source="development", title=title, summary=summary, payload=payload)

    def integration(self, event_type: str, title: str, summary: str = "", payload: dict[str, Any] | None = None) -> AwarenessEvent:
        provider = str((payload or {}).get("provider") or "integration")
        return self.create(category="integration", event_type=event_type, source=provider, title=title, summary=summary, payload=payload)

    def system(self, event_type: str, title: str, summary: str = "", payload: dict[str, Any] | None = None) -> AwarenessEvent:
        return self.create(category="system", event_type=event_type, source="system", title=title, summary=summary, payload=payload)
