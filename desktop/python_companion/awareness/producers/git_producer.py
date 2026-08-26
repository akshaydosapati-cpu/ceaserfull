from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

from awareness.event_sources import EventFactory
from awareness.models import AwarenessEvent
from awareness.producers.base import EventProducer


class GitProducer(EventProducer):
    name = "git"
    poll_interval_seconds = 10.0

    def __init__(self, emit=None, repo_path: str | None = None, status_probe: Callable[[Path], dict] | None = None) -> None:
        super().__init__(emit)
        self.repo_path = Path(repo_path) if repo_path else None
        self.status_probe = status_probe or self._git_status
        self.factory = EventFactory()
        self._last_branch = ""
        self._last_dirty: bool | None = None
        self._last_commit = ""

    def normalize_event(self, raw: dict) -> AwarenessEvent | None:
        return self.factory.development(raw["type"], raw["title"], raw.get("summary", ""), raw.get("payload", {})) if raw.get("type") else None

    def _poll(self, context: dict) -> list[AwarenessEvent]:
        repo = self._repo(context)
        if not repo:
            return []
        status = self.status_probe(repo)
        events: list[AwarenessEvent] = []
        branch = str(status.get("branch") or "")
        dirty = bool(status.get("dirty"))
        commit = str(status.get("commit") or "")
        if branch and self._last_branch and branch != self._last_branch:
            events.append(self.factory.development("git_branch_changed", "Git branch changed", f"Branch changed to {branch}.", {"repository": str(repo), "branch": branch}))
        if self._last_dirty is not None and dirty != self._last_dirty:
            events.append(self.factory.development("git_dirty_state_changed", "Git working tree changed", "Working tree became dirty." if dirty else "Working tree is clean.", {"repository": str(repo), "dirty": dirty}))
        if commit and self._last_commit and commit != self._last_commit:
            events.append(self.factory.development("new_commit", "New local commit", "A new local commit was detected.", {"repository": str(repo), "commit": commit[:12]}))
        self._last_branch = branch
        self._last_dirty = dirty
        self._last_commit = commit
        return events

    def _repo(self, context: dict) -> Path | None:
        candidate = self.repo_path or Path(str((context.get("working_memory") or {}).get("current_folder") or ""))
        if candidate and (candidate / ".git").exists():
            return candidate
        return None

    def _git_status(self, repo: Path) -> dict:
        try:
            branch = subprocess.check_output(["git", "-C", str(repo), "branch", "--show-current"], text=True, stderr=subprocess.DEVNULL, timeout=1).strip()
            dirty = bool(subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain"], text=True, stderr=subprocess.DEVNULL, timeout=1).strip())
            commit = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL, timeout=1).strip()
            merge = (repo / ".git" / "MERGE_HEAD").exists()
            rebase = (repo / ".git" / "rebase-merge").exists() or (repo / ".git" / "rebase-apply").exists()
            return {"branch": branch, "dirty": dirty, "commit": commit, "merge": merge, "rebase": rebase}
        except Exception:
            return {}
