from __future__ import annotations

import re
from typing import Any


class SufficiencyChecker:
    def missing_information(self, text: str, evidence: dict[str, Any]) -> list[str]:
        lowered = text.lower().strip()
        missing: list[str] = []
        vague_resource = bool(re.search(r"\b(it|this|that|current file|selected file)\b", lowered))
        has_resource = bool(evidence.get("active_resource") or evidence.get("active_file") or evidence.get("resolved_reference"))
        # A planned workflow can produce the thing being saved. For example,
        # "prepare a viva pack and save it to Notion" is self-contained and
        # must reach the workflow's protected confirmation step.
        workflow_produces_output = bool((evidence.get("workflow_plan") or {}).get("steps"))
        if vague_resource and not has_resource and not workflow_produces_output and re.search(r"\b(open|delete|close|summarize|summarise|explain|save|move|copy)\b", lowered):
            missing.append("active_resource")
        if re.search(r"\b(open|show|summarize|summarise|explain)\s+my\s+project\b", lowered):
            if not (evidence.get("active_project") or evidence.get("world_current_project") or evidence.get("long_term_memories")):
                missing.append("project")
        if re.search(r"\b(commit|commits|pull request|pull requests|issue|issues)\b", lowered):
            if re.search(r"\b(this|current|my)\s+project\b", lowered) and not (evidence.get("repository") or evidence.get("world_current_repository")):
                missing.append("repository")
        if re.search(r"\bpush\b", lowered) and not (evidence.get("repository") or evidence.get("world_current_repository")):
            missing.append("repository")
        return missing
