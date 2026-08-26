from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from awareness.event_sources import EventFactory
from awareness.models import AwarenessEvent
from awareness.producers.base import EventProducer


TEMP_DOWNLOAD_SUFFIXES = (".crdownload", ".tmp", ".part", ".download")


class FilesystemProducer(EventProducer):
    name = "filesystem"
    poll_interval_seconds = 5.0

    def __init__(self, emit=None, watched_folders: list[str] | None = None, lister: Callable[[Path], list[dict]] | None = None) -> None:
        super().__init__(emit)
        self.factory = EventFactory()
        self.watched_folders = [Path(folder) for folder in (watched_folders or [str(Path.home() / "Downloads")])]
        self.lister = lister or self._list_folder
        self._snapshots: dict[str, dict[str, dict]] = {}

    def normalize_event(self, raw: dict) -> AwarenessEvent | None:
        path = str(raw.get("path") or "")
        if self._temporary(path):
            return None
        return self.factory.desktop(raw.get("type", "file_created"), raw.get("title", "File changed"), raw.get("summary", ""), {"path": path, "size": raw.get("size", 0)})

    def _poll(self, context: dict) -> list[AwarenessEvent]:
        folders = self._folders(context)
        events: list[AwarenessEvent] = []
        for folder in folders:
            current = {item["path"]: item for item in self.lister(folder) if not self._temporary(item.get("path", ""))}
            snapshot_key = str(folder)
            if snapshot_key not in self._snapshots:
                self._snapshots[snapshot_key] = current
                continue
            previous = self._snapshots.get(snapshot_key, {})
            for path, item in current.items():
                if path not in previous:
                    size = int(item.get("size") or 0)
                    event_type = "large_file_added" if size >= 25 * 1024 * 1024 else "download_completed" if str(folder).lower().endswith("downloads") else "file_created"
                    events.append(self.factory.system(event_type, "Download complete" if event_type == "download_completed" else "File added", Path(path).name, {"path": path, "size": size}))
            for path in previous:
                if path not in current:
                    events.append(self.factory.desktop("file_deleted", "File deleted", Path(path).name, {"path": path}))
            self._snapshots[snapshot_key] = current
        return events

    def _folders(self, context: dict) -> list[Path]:
        folders = list(self.watched_folders)
        active = ((context.get("working_memory") or {}).get("current_folder") or (context.get("context_snapshot") or {}).get("current_folder") or "")
        if active:
            folders.append(Path(active))
        return list(dict.fromkeys(folder for folder in folders if folder.exists()))

    def _list_folder(self, folder: Path) -> list[dict]:
        try:
            return [{"path": str(item), "size": item.stat().st_size, "mtime": item.stat().st_mtime} for item in folder.iterdir() if item.is_file()]
        except OSError:
            return []

    def _temporary(self, path: str) -> bool:
        return str(path).lower().endswith(TEMP_DOWNLOAD_SUFFIXES) or os.path.basename(str(path)).startswith("~$")
