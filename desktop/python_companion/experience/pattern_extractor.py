from __future__ import annotations

import re
import time

from experience.models import ExperienceOutcome, ExperiencePattern


class ExperiencePatternExtractor:
    def patterns_for(self, outcome: ExperienceOutcome) -> list[ExperiencePattern]:
        patterns = [
            ExperiencePattern(
                key=f"command:{outcome.command_signature}",
                type="repeated_command",
                label=outcome.command_signature,
                count=1,
                confidence=0.4,
                last_seen_at=outcome.created_at,
                metadata={"capability": outcome.capability, "route": outcome.route},
            ),
            ExperiencePattern(
                key=f"capability_hour:{outcome.capability}:{outcome.hour_of_day}",
                type="time_usage",
                label=f"{outcome.capability} around {outcome.hour_of_day}:00",
                count=1,
                confidence=0.35,
                last_seen_at=outcome.created_at,
                metadata={"capability": outcome.capability, "hour": outcome.hour_of_day},
            ),
        ]
        if outcome.workflow_type:
            patterns.append(
                ExperiencePattern(
                    key=f"workflow:{outcome.workflow_type}:{outcome.active_project}",
                    type="repeated_workflow",
                    label=outcome.workflow_type,
                    count=1,
                    confidence=0.5,
                    last_seen_at=outcome.created_at,
                    metadata={"workflow_type": outcome.workflow_type, "active_project": outcome.active_project},
                )
            )
        if outcome.active_project:
            patterns.append(
                ExperiencePattern(
                    key=f"project_capability:{outcome.active_project}:{outcome.capability}",
                    type="project_usage",
                    label=f"{outcome.capability} in {outcome.active_project}",
                    count=1,
                    confidence=0.45,
                    last_seen_at=outcome.created_at,
                    metadata={"project": outcome.active_project, "capability": outcome.capability},
                )
            )
        return patterns

    def command_signature(self, text: str) -> str:
        safe = self._redact(text).lower()
        safe = re.sub(r"https?://\S+|\S+@\S+", "", safe)
        terms = re.findall(r"[a-z][a-z0-9_.-]{1,}", safe)
        stop = {"the", "this", "that", "please", "for", "with", "and", "now", "me", "my"}
        return " ".join(term for term in terms if term not in stop)[:120] or "empty"

    def _redact(self, text: str) -> str:
        text = re.sub(r"(api[_-]?key|token|password|secret)\s*[:=]?\s*\S+", r"\1 [redacted]", str(text or ""), flags=re.IGNORECASE)
        text = re.sub(r"sk-[a-zA-Z0-9_-]{8,}", "sk-[redacted]", text)
        return text
