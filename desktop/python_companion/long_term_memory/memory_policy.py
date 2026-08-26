from __future__ import annotations

import re

from long_term_memory.models import MemoryCandidate


SECRET_PATTERN = re.compile(
    r"(api[_-]?key|access[_-]?token|refresh[_-]?token|private[_-]?key|password|secret|bearer\s+[a-z0-9._-]+|sk-[a-z0-9]{8,}|payment|card number|cvv)",
    re.IGNORECASE,
)
SENSITIVE_PATTERN = re.compile(r"\b(medical|diagnosis|disease|treatment|legal|lawyer|salary|address|phone|relationship|family)\b", re.IGNORECASE)


class MemoryPolicy:
    def is_secret(self, text: str) -> bool:
        return bool(SECRET_PATTERN.search(str(text or "")))

    def is_sensitive(self, text: str) -> bool:
        return bool(SENSITIVE_PATTERN.search(str(text or "")))

    def evaluate(self, candidate: MemoryCandidate, *, explicit_remember: bool, session_disabled: bool = False) -> tuple[bool, MemoryCandidate, str]:
        if session_disabled:
            return False, candidate, "session_memory_disabled"
        if self.is_secret(candidate.content) or self.is_secret(str(candidate.structured_data)):
            candidate.sensitive = True
            return False, candidate, "secret_rejected"
        if self.is_sensitive(candidate.content):
            candidate.sensitive = True
            candidate.requires_confirmation = True
            return False, candidate, "sensitive_requires_confirmation"
        if candidate.requires_confirmation and not explicit_remember:
            return False, candidate, "confirmation_required"
        if explicit_remember:
            return True, candidate, "explicit_user_request"
        if candidate.type in {"preference", "project", "goal", "workflow_preference"} and candidate.confidence >= 0.8:
            return True, candidate, "allowed_stable_memory"
        return False, candidate, "not_eligible"
