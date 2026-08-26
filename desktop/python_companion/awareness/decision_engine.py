from __future__ import annotations

from awareness.models import AwarenessDecision, AwarenessEvent


class AwarenessDecisionEngine:
    def decide(self, event: AwarenessEvent, context: dict | None = None) -> AwarenessDecision:
        context = context or {}
        idle = bool((context.get("working_memory") or {}).get("user_idle"))
        if event.importance >= 0.75:
            return AwarenessDecision(
                event_id=event.id,
                action="notify",
                importance=event.importance,
                reason="high_importance_event",
                notification_title=event.title,
                notification_summary=event.summary,
                should_speak=False if not idle else bool(event.payload.get("allow_spoken_notice", False)),
                evidence={"idle": idle, "category": event.category, "type": event.type},
            )
        if event.importance >= 0.45:
            return AwarenessDecision(
                event_id=event.id,
                action="delay",
                importance=event.importance,
                reason="medium_importance_delay",
                notification_title=event.title,
                notification_summary=event.summary,
                delay_seconds=300,
                evidence={"category": event.category, "type": event.type},
            )
        return AwarenessDecision(
            event_id=event.id,
            action="ignore",
            importance=event.importance,
            reason="low_importance_quietly_recorded",
            evidence={"category": event.category, "type": event.type},
        )
