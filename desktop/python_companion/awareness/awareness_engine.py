from __future__ import annotations

from typing import Any

from awareness.decision_engine import AwarenessDecisionEngine
from awareness.event_queue import EventQueue
from awareness.event_sources import EventFactory
from awareness.importance_scorer import ImportanceScorer
from awareness.models import AwarenessContext, AwarenessDecision, AwarenessEvent


class AwarenessEngine:
    def __init__(self, queue: EventQueue | None = None) -> None:
        self.queue = queue or EventQueue()
        self.scorer = ImportanceScorer()
        self.decisions = AwarenessDecisionEngine()
        self.factory = EventFactory()
        self.notification_cards: list[dict[str, Any]] = []
        self.delayed_events: list[dict[str, Any]] = []
        self.ignored_count = 0
        self.listeners = []

    def subscribe(self, listener) -> None:
        if listener not in self.listeners:
            self.listeners.append(listener)

    def observe(self, event: AwarenessEvent, context: dict | None = None) -> AwarenessDecision:
        event.importance = self.scorer.score(event, context)
        queued = self.queue.enqueue(event)
        decision = self.decisions.decide(queued, context)
        if decision.action == "notify":
            self.queue.mark(queued.id, "notified")
            self._upsert_card(self.notification_cards, self._card(queued, decision))
            self.notification_cards = self.notification_cards[:12]
        elif decision.action == "delay":
            self.queue.mark(queued.id, "delayed")
            self._upsert_card(self.delayed_events, self._card(queued, decision))
            self.delayed_events = self.delayed_events[:12]
        else:
            self.queue.mark(queued.id, "ignored")
            self.ignored_count += 1
        for listener in tuple(self.listeners):
            try:
                listener(queued, decision)
            except Exception:
                continue
        return decision

    def observe_payload(self, *, category: str, event_type: str, source: str, title: str, summary: str = "", payload: dict[str, Any] | None = None, context: dict | None = None) -> AwarenessDecision:
        event = self.factory.create(category=category, event_type=event_type, source=source, title=title, summary=summary, payload=payload)
        return self.observe(event, context)

    def as_context(self, limit: int = 8) -> dict[str, Any]:
        recent = [self._dump(event) for event in self.queue.recent(limit)]
        high = [event for event in recent if event.get("importance", 0) >= 0.75]
        latest = recent[0]["summary"] if recent and recent[0].get("summary") else recent[0]["title"] if recent else ""
        return AwarenessContext(
            recent_events=recent,
            notification_cards=self.notification_cards[:limit],
            delayed_events=self.delayed_events[:limit],
            ignored_count=self.ignored_count,
            high_importance_count=len(high),
            latest_event_summary=latest,
        ).as_context()

    def _card(self, event: AwarenessEvent, decision: AwarenessDecision) -> dict[str, Any]:
        return {
            "event_id": event.id,
            "category": event.category,
            "title": decision.notification_title or event.title,
            "short_message": decision.notification_summary or event.summary,
            "summary": decision.notification_summary or event.summary,
            "type": event.type,
            "importance": decision.importance,
            "timestamp": event.created_at,
            "reason": decision.reason,
            "should_speak": decision.should_speak,
            "suggested_action_label": self._suggested_action(event),
        }

    def _dump(self, event: AwarenessEvent) -> dict[str, Any]:
        return event.model_dump() if hasattr(event, "model_dump") else event.dict()

    def _upsert_card(self, cards: list[dict[str, Any]], card: dict[str, Any]) -> None:
        cards[:] = [item for item in cards if item.get("event_id") != card.get("event_id")]
        cards.insert(0, card)

    def _suggested_action(self, event: AwarenessEvent) -> str:
        if event.type in {"build_failed", "tests_failed"}:
            return "Review failure"
        if event.type in {"download_completed", "large_file_added"}:
            return "Open file"
        if event.type in {"github_sync_failed", "notion_sync_failed", "token_refresh_failure"}:
            return "Reconnect"
        if event.type in {"battery_low", "network_down"}:
            return "Check system"
        return ""
