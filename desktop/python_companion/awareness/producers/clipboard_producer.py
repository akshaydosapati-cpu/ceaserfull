from __future__ import annotations

from typing import Any, Callable

from awareness.event_sources import EventFactory
from awareness.models import AwarenessEvent
from awareness.producers.base import EventProducer


class ClipboardProducer(EventProducer):
    name = "clipboard"
    poll_interval_seconds = 2.0

    def __init__(self, emit=None, probe: Callable[[], dict[str, Any]] | None = None) -> None:
        super().__init__(emit)
        self.probe = probe or self._probe_clipboard
        self.factory = EventFactory()
        self._last_signature = ""

    def normalize_event(self, raw: dict[str, Any]) -> AwarenessEvent | None:
        payload = self._metadata(raw)
        return self.factory.desktop("clipboard_updated", "Clipboard updated", "Clipboard metadata changed.", payload)

    def _poll(self, context: dict) -> list[AwarenessEvent]:
        raw = self.probe()
        payload = self._metadata(raw)
        signature = f"{payload.get('content_type')}:{payload.get('approx_size')}:{payload.get('item_count')}"
        if signature == self._last_signature:
            return []
        self._last_signature = signature
        return [self.factory.desktop("clipboard_updated", "Clipboard updated", "Clipboard metadata changed.", payload)]

    def _metadata(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "content_type": raw.get("content_type") or raw.get("type") or "unknown",
            "approx_size": int(raw.get("approx_size") or raw.get("size") or 0),
            "item_count": int(raw.get("item_count") or raw.get("count") or 1),
        }

    def _probe_clipboard(self) -> dict[str, Any]:
        try:
            import win32clipboard  # type: ignore

            win32clipboard.OpenClipboard()
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_HDROP):
                    return {"content_type": "file-list", "approx_size": 0, "item_count": 1}
                if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_DIB):
                    return {"content_type": "image", "approx_size": 0, "item_count": 1}
                if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                    return {"content_type": "text", "approx_size": 0, "item_count": 1}
                return {"content_type": "unknown", "approx_size": 0, "item_count": 1}
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            return {}
