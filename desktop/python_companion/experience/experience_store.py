from __future__ import annotations

from experience.models import CapabilityExperience, ExperienceOutcome, ExperiencePattern


class ExperienceStore:
    def __init__(self, max_outcomes: int = 1000) -> None:
        self.max_outcomes = max_outcomes
        self.outcomes: list[ExperienceOutcome] = []
        self.capabilities: dict[str, CapabilityExperience] = {}
        self.patterns: dict[str, ExperiencePattern] = {}

    def save_outcome(self, outcome: ExperienceOutcome) -> ExperienceOutcome:
        self.outcomes.append(outcome)
        self.outcomes = self.outcomes[-self.max_outcomes :]
        self._update_capability(outcome)
        return outcome

    def save_pattern(self, pattern: ExperiencePattern) -> ExperiencePattern:
        existing = self.patterns.get(pattern.key)
        if existing:
            existing.count += pattern.count
            existing.confidence = max(existing.confidence, pattern.confidence)
            existing.last_seen_at = pattern.last_seen_at
            existing.metadata.update(pattern.metadata)
            return existing
        self.patterns[pattern.key] = pattern
        return pattern

    def recent(self, limit: int = 20, *, success: bool | None = None) -> list[ExperienceOutcome]:
        items = self.outcomes
        if success is not None:
            items = [item for item in items if item.success is success]
        return sorted(items, key=lambda item: item.created_at, reverse=True)[:limit]

    def patterns_by_type(self, pattern_type: str, limit: int = 10) -> list[ExperiencePattern]:
        items = [item for item in self.patterns.values() if item.type == pattern_type]
        return sorted(items, key=lambda item: (item.count, item.confidence, item.last_seen_at), reverse=True)[:limit]

    def _update_capability(self, outcome: ExperienceOutcome) -> None:
        capability = outcome.capability or "unknown"
        current = self.capabilities.get(capability) or CapabilityExperience(capability=capability)
        current.attempts += 1
        current.successes += 1 if outcome.success else 0
        current.failures += 0 if outcome.success else 1
        current.clarification_count += 1 if outcome.clarification_needed else 0
        current.confirmation_count += 1 if outcome.confirmation_state else 0
        current.average_latency_ms = ((current.average_latency_ms * (current.attempts - 1)) + outcome.latency_ms) / current.attempts
        current.last_used_at = outcome.created_at
        self.capabilities[capability] = current
