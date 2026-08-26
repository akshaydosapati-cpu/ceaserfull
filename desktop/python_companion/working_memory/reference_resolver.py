from __future__ import annotations

import re
from typing import Any

from working_memory.models import ContextSnapshot


REFERENCE_PATTERN = re.compile(r"\b(it|this|that|those|continue|again|same|previous|last one)\b", re.IGNORECASE)


class WorkingReferenceResolver:
    def is_reference(self, text: str) -> bool:
        return bool(REFERENCE_PATTERN.search(str(text or "")))

    def resolve(self, text: str, snapshot: ContextSnapshot) -> dict[str, Any]:
        if not self.is_reference(text):
            return {"follow_up_detected": False, "resolved_reference": None}
        active_resource = snapshot.active_resource or {}
        if active_resource:
            target = {"kind": "resource", **active_resource}
        elif snapshot.previous_response:
            target = {"kind": "conversation", "summary": snapshot.previous_response}
        elif snapshot.selected_file:
            target = {"kind": "file", "path": snapshot.selected_file}
        else:
            target = None
        return {
            "follow_up_detected": True,
            "resolved_reference": {
                "target": target,
                "last_command": snapshot.last_command,
                "last_capability": snapshot.last_capability,
                "last_summary": snapshot.previous_response,
                "active_resource": active_resource,
                "repository": snapshot.repository or snapshot.github_repository,
                "notion_page": snapshot.notion_page,
            },
        }
