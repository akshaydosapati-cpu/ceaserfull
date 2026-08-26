from __future__ import annotations

import re

from long_term_memory.models import MemoryCandidate


class MemoryExtractor:
    def extract_from_text(self, text: str) -> list[MemoryCandidate]:
        raw = str(text or "").strip()
        lowered = raw.lower()
        candidates: list[MemoryCandidate] = []
        explicit = re.search(r"\bremember that\s+(.+)", raw, re.IGNORECASE)
        content = explicit.group(1).strip().rstrip(".") if explicit else raw

        if re.search(r"\bprefer (brief|short|concise|detailed|long)\b|\bbe brief\b|\bshort answers\b", lowered):
            value = "brief" if re.search(r"\bbrief|short|concise\b", lowered) else "detailed"
            candidates.append(MemoryCandidate(type="preference", content=f"User prefers {value} answers.", structured_data={"response_length": value}, source="user", confidence=0.92, importance=0.8, reason="explicit_preference"))

        project_match = re.search(r"([A-Z][A-Za-z0-9_.-]{2,})\s+is my\s+(.+?)\s+project", content)
        if project_match:
            name = project_match.group(1)
            domain = project_match.group(2).strip()
            candidates.append(MemoryCandidate(type="project", content=f"{name} is the user's {domain} project.", structured_data={"project": name, "domain": domain}, source="user", confidence=0.94, importance=0.9, reason="explicit_project"))

        goal_match = re.search(r"\bremember that i (need to|want to|am working on|will)\s+(.+)", raw, re.IGNORECASE)
        if goal_match:
            goal = goal_match.group(2).strip().rstrip(".")
            candidates.append(MemoryCandidate(type="goal", content=f"User goal: {goal}", structured_data={"goal": goal}, source="user", confidence=0.86, importance=0.7, reason="explicit_goal"))

        if explicit and not candidates:
            candidates.append(MemoryCandidate(type="episodic", content=content, structured_data={}, source="user", confidence=0.72, importance=0.5, requires_confirmation=True, reason="generic_remember"))

        return candidates
