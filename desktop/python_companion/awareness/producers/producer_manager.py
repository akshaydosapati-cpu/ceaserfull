from __future__ import annotations

import time
from typing import Any

from awareness.awareness_engine import AwarenessEngine
from awareness.models import AwarenessDecision, AwarenessEvent
from awareness.producers.base import EventProducer


class ProducerManager:
    def __init__(self, awareness_engine: AwarenessEngine, producers: list[EventProducer] | None = None) -> None:
        self.awareness_engine = awareness_engine
        self.producers: dict[str, EventProducer] = {}
        self.backoff_until: dict[str, float] = {}
        self.restarts: dict[str, int] = {}
        self.started = False
        for producer in producers or []:
            self.add(producer)

    def add(self, producer: EventProducer) -> None:
        if producer.name in self.producers:
            return
        producer.emit = self.awareness_engine.observe
        self.producers[producer.name] = producer

    def start(self) -> None:
        self.started = True
        for producer in self.producers.values():
            producer.start()
        self.awareness_engine.observe(self.awareness_engine.factory.system("producer_manager_started", "Awareness producers started", "Local awareness producers are active."))

    def stop(self) -> None:
        for producer in self.producers.values():
            producer.stop()
        self.started = False
        self.awareness_engine.observe(self.awareness_engine.factory.system("producer_manager_stopped", "Awareness producers stopped", "Local awareness producers shut down cleanly."))

    def poll_once(self, context: dict[str, Any] | None = None) -> list[AwarenessDecision]:
        decisions: list[AwarenessDecision] = []
        now = time.time()
        for producer in self.producers.values():
            if not producer.running:
                continue
            if now < self.backoff_until.get(producer.name, 0):
                continue
            before = len(self.awareness_engine.queue.recent(300))
            events = producer.poll_or_watch(context or {})
            after_events = self.awareness_engine.queue.recent(300)
            if producer.last_error:
                self._handle_failure(producer)
            elif events:
                for event in after_events[: max(0, len(after_events) - before)]:
                    decisions.append(self.awareness_engine.decisions.decide(event, context or {}))
        return decisions

    def health(self) -> dict[str, Any]:
        return {
            "started": self.started,
            "producer_count": len(self.producers),
            "producers": {name: producer.health() for name, producer in self.producers.items()},
            "restarts": dict(self.restarts),
            "estimated_idle_polling": self.estimated_overhead(),
        }

    def estimated_overhead(self) -> dict[str, Any]:
        intervals = [producer.poll_interval_seconds for producer in self.producers.values() if producer.running]
        return {
            "polls_per_minute": round(sum(60 / max(interval, 0.1) for interval in intervals), 2),
            "cpu_target": "under 1-2% while idle",
            "memory_target": "small in-memory queue, capped at 300 events",
        }

    def _handle_failure(self, producer: EventProducer) -> None:
        self.restarts[producer.name] = self.restarts.get(producer.name, 0) + 1
        delay = min(60, 2 ** min(self.restarts[producer.name], 5))
        self.backoff_until[producer.name] = time.time() + delay
        producer.stop()
        producer.start()
        self.awareness_engine.observe(
            self.awareness_engine.factory.system(
                "producer_recovered",
                f"{producer.name} producer recovered",
                f"{producer.name} producer failed and was restarted with bounded backoff.",
                {"producer": producer.name, "error": producer.last_error, "backoff_seconds": delay},
            )
        )
