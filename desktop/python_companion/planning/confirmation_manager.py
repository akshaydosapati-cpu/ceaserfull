from __future__ import annotations

import re
import time
import uuid
from typing import Any

from planning.models import PendingConfirmation, WorkflowStep


SECRET_PATTERN = re.compile(r"(secret|token|password|api[_-]?key|access[_-]?token|refresh[_-]?token|private[_-]?key)", re.IGNORECASE)


class ConfirmationManager:
    def __init__(self) -> None:
        self.pending: dict[str, PendingConfirmation] = {}

    def create(self, workflow_id: str, step: WorkflowStep, preview: str | None = None, ttl_seconds: int = 300) -> PendingConfirmation:
        confirmation = PendingConfirmation(
            confirmation_id=f"confirm_{uuid.uuid4().hex[:12]}",
            workflow_id=workflow_id,
            step_id=step.step_id,
            capability=step.capability,
            arguments=self.redact(step.arguments),
            risk_level=step.risk_level,
            expires_at=time.time() + ttl_seconds,
            preview=preview or self.preview_for(step),
        )
        self.pending[confirmation.confirmation_id] = confirmation
        return confirmation

    def approve(self, confirmation_id: str, workflow_id: str, step_id: str) -> bool:
        confirmation = self.pending.get(confirmation_id)
        if not confirmation:
            return False
        if confirmation.expires_at <= time.time():
            self.pending.pop(confirmation_id, None)
            return False
        if confirmation.workflow_id != workflow_id or confirmation.step_id != step_id:
            return False
        self.pending.pop(confirmation_id, None)
        return True

    def preview_for(self, step: WorkflowStep) -> str:
        title = step.arguments.get("title") or step.arguments.get("name") or step.capability
        if step.capability == "notion.create_page":
            return f"Create '{title}' in your Notion workspace?"
        if step.capability.startswith("github.") and "create" in step.capability:
            return f"Create GitHub item '{title}'?"
        return f"Approve {step.capability}?"

    def redact(self, arguments: dict[str, Any]) -> dict[str, Any]:
        safe = {}
        for key, value in dict(arguments or {}).items():
            if SECRET_PATTERN.search(str(key)):
                safe[key] = "[redacted]"
            else:
                safe[key] = value
        return safe
