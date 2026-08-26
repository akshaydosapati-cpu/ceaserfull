from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from awareness.models import AwarenessDecision, AwarenessEvent
from conversation.companion_models import CompanionPreferences
from conversation.companion_models import ProactiveDecision
from conversation.companion_personality import CompanionPersonalityEngine
from conversation.proactive_conversation import ProactiveConversationEngine
from conversation.social_context import SocialContextEngine
from core.schemas import ActionResult, CommandRequest, IntentResult


logger = logging.getLogger("ceaser.proactive_runtime")


class ProactiveRuntimeAdapter:
    """Adapts trusted awareness events to the existing companion delivery path."""

    def __init__(
        self,
        policy: ProactiveConversationEngine,
        personality: CompanionPersonalityEngine,
        preference_loader: Callable[[dict[str, Any]], CompanionPreferences],
    ) -> None:
        self.policy = policy
        self.personality = personality
        self.preference_loader = preference_loader
        self.delivery: Callable[[dict[str, Any]], None] | None = None
        self.user_id_provider: Callable[[], str] = lambda: ""
        self.context_provider: Callable[[], dict[str, Any]] = lambda: {}
        self.thread_recorder: Callable[[dict[str, Any]], None] | None = None
        self.social = SocialContextEngine()
        self._recent_correlations: dict[tuple[str, str], tuple[float, str]] = {}

    def configure(
        self,
        *,
        delivery: Callable[[dict[str, Any]], None] | None = None,
        generator: Callable[[str, str], str] | None = None,
        user_id_provider: Callable[[], str] | None = None,
        context_provider: Callable[[], dict[str, Any]] | None = None,
        thread_recorder: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.delivery = delivery or self.delivery
        self.personality.generator = generator or self.personality.generator
        self.user_id_provider = user_id_provider or self.user_id_provider
        self.context_provider = context_provider or self.context_provider
        self.thread_recorder = thread_recorder or self.thread_recorder

    def receive(self, event: AwarenessEvent, awareness: AwarenessDecision) -> dict[str, Any]:
        if event.type not in self.policy.TRUSTED_EVENTS:
            return {"delivered": False, "reason": "untrusted_trigger"}
        user_id = str(self.user_id_provider() or "")
        if not user_id:
            return {"delivered": False, "reason": "anonymous_session"}
        context = dict(self.context_provider() or {})
        preferences = self.preference_loader(context)
        event_payload = {
            "event": event.type,
            "importance": event.importance,
            "urgency": float(event.payload.get("urgency") or (0.9 if event.type in {"task_failed", "build_failed", "meeting_upcoming", "reminder_due"} else 0.0)),
            "confidence": float(event.payload.get("confidence") or 1.0),
            "title": event.title,
            "summary": event.summary,
            "source": event.source,
            **{key: value for key, value in event.payload.items() if key in {"social_trigger", "relevance", "timing", "absence_seconds", "unfinished_goal", "memory_id", "callback_text", "correlation_id", "topic", "allow_spoken_notice"}},
        }
        correlation = str(event_payload.get("correlation_id") or event.dedupe_key or "")
        correlation_key = (user_id, correlation)
        now = time.time()
        previous_correlation = self._recent_correlations.get(correlation_key)
        if correlation and previous_correlation and event.type != previous_correlation[1] and now - previous_correlation[0] < 45:
            logger.info("social.opportunity_skipped reason=event_collapsed event=%s", event.type)
            return {"delivered": False, "reason": "event_collapsed"}
        social = self.social.evaluate(user_id, event_payload, preferences, context)
        is_social = social.eligible or social.reason not in {"not_social"}
        if is_social and not social.eligible:
            return {"delivered": False, "reason": social.reason}
        decision = (
            ProactiveDecision(
                should_initiate=True,
                priority="normal",
                delivery_channel="activity" if social.delivery == "visual" else "notification",
                tone="work",
                reason="social_opportunity_policy",
                structured_trigger=social.grounded_context,
            )
            if social.eligible
            else self.policy.evaluate(user_id, event_payload, preferences, context)
        )
        if not decision.should_initiate:
            logger.info("proactive.suppressed event=%s reason=%s", event.type, decision.reason)
            return {"delivered": False, "reason": decision.reason}

        raw_summary = " ".join(part for part in (event.title, event.summary) if part).strip()
        request = CommandRequest(
            request_id=f"proactive_{event.id}",
            user_id=user_id,
            session_id="desktop_session",
            source="automation",
            raw_text=raw_summary,
            normalized_text=raw_summary,
            context=context,
        )
        intent = IntentResult(intent="proactive_event", capability="conversation.proactive", confidence=0.99, route="conversation")
        result = ActionResult(
            status="completed",
            capability="conversation.proactive",
            summary=raw_summary,
            spoken_response=raw_summary,
            verified=True,
            evidence={"cortex_destination": "conversation", "trusted_event": event.type, "social_trigger": social.trigger if social.eligible else ""},
        )
        composed = self.personality.compose(request, intent, context, result)
        if social.eligible and composed.evidence.get("companion_fallback"):
            logger.info("social.opportunity_skipped reason=provider_failure")
            return {"delivered": False, "reason": "provider_failure"}
        payload = {
            "event_id": event.id,
            "event_type": event.type,
            "message": composed.summary,
            "spoken_response": composed.spoken_response or composed.summary,
            "priority": decision.priority,
            "delivery_channel": decision.delivery_channel,
            "tone": decision.tone,
            "should_speak": bool((social.delivery == "speak" if social.eligible else awareness.should_speak) and not context.get("active_voice_conversation")),
            "verified": True,
            "proactive_kind": "social" if social.eligible else "functional",
            "social_trigger": social.trigger if social.eligible else "",
        }
        if self.delivery:
            self.delivery(payload)
        if correlation:
            self._recent_correlations[correlation_key] = (now, event.type)
        if social.eligible:
            logger.info("social.proactive_generated trigger=%s", social.trigger)
            self.social.delivered(user_id, social, composed.summary)
        if self.thread_recorder:
            self.thread_recorder({**payload, "source_event": event_payload})
        logger.info("proactive.initiated event=%s channel=%s", event.type, decision.delivery_channel)
        return {"delivered": bool(self.delivery), "reason": decision.reason, "payload": payload}

    def dismiss(self) -> None:
        user_id = str(self.user_id_provider() or "")
        if user_id:
            self.policy.dismiss(user_id)
            self.social.reaction(user_id, "dismissed")

    def observe_user_message(self, user_id: str, text: str) -> dict[str, Any]:
        if not user_id:
            return {}
        lowered = str(text or "").strip().lower()
        if any(phrase in lowered for phrase in ("stop interrupting", "stop starting conversations", "leave me alone", "be quiet")):
            self.social.reaction(user_id, "stop_requested")
            return {"social_proactivity": False}
        if any(phrase in lowered for phrase in ("talk to me more", "don't be so quiet", "dont be so quiet")):
            self.social.reaction(user_id, "positive")
            return {"social_proactivity": True, "proactive_mode": "companion", "social_interruption_tolerance": 0.85}
        if not self.social.active_thread(user_id):
            return {}
        self.social.reaction(user_id, "engaged")
        return {}
