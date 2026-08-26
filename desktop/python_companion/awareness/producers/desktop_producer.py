from __future__ import annotations

import subprocess
from typing import Any, Callable

from awareness.event_sources import EventFactory
from awareness.models import AwarenessEvent
from awareness.producers.base import EventProducer


class DesktopProducer(EventProducer):
    name = "desktop"
    poll_interval_seconds = 0.75

    def __init__(self, emit=None, probe: Callable[[], dict[str, Any]] | None = None) -> None:
        super().__init__(emit)
        self.probe = probe or self._probe_foreground
        self.factory = EventFactory()
        self._last_app = ""
        self._last_title = ""
        self._overlay_open = False

    def normalize_event(self, raw: dict[str, Any]) -> AwarenessEvent | None:
        return self.factory.desktop(raw["type"], raw["title"], raw.get("summary", ""), raw.get("payload", {})) if raw.get("type") else None

    def overlay_state(self, opened: bool) -> AwarenessEvent | None:
        if opened == self._overlay_open:
            return None
        self._overlay_open = opened
        return self.factory.desktop("ceaser_overlay_opened" if opened else "ceaser_overlay_closed", "CEASER overlay opened" if opened else "CEASER overlay closed", "", {"opened": opened})

    def _poll(self, context: dict) -> list[AwarenessEvent]:
        data = self.probe()
        app = str(data.get("app") or data.get("process") or "")
        title = str(data.get("title") or "")
        events: list[AwarenessEvent] = []
        if app and app != self._last_app:
            events.append(self.factory.desktop("active_application_changed", "Active application changed", f"{app} is active.", {"app": app}))
            self._last_app = app
        if title and title != self._last_title:
            events.append(self.factory.desktop("active_window_changed", "Active window changed", "The foreground window changed.", {"app": app, "title_length": len(title)}))
            self._last_title = title
        return events

    def _probe_foreground(self) -> dict[str, Any]:
        try:
            import win32gui  # type: ignore
            import win32process  # type: ignore

            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd) or ""
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            app = self._process_name(pid)
            return {"app": app, "process": app, "title": title, "pid": pid}
        except Exception:
            return {}

    def _process_name(self, pid: int) -> str:
        try:
            output = subprocess.check_output(["tasklist", "/fi", f"PID eq {pid}", "/fo", "csv", "/nh"], text=True, stderr=subprocess.DEVNULL, timeout=0.5)
            first = output.splitlines()[0] if output.splitlines() else ""
            return first.split(",")[0].strip('" ') if first else str(pid)
        except Exception:
            return str(pid)
