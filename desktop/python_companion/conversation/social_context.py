from __future__ import annotations

import hashlib
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Literal

from conversation.companion_models import CompanionPreferences


logger = logging.getLogger("ceaser.social")

SocialDelivery = Literal["skip", "visual", "speak", "interrupt"]


@dataclass
class SocialOpportunity:
    eligible: bool
    trigger: str = ""
    delivery: SocialDelivery = "skip"
    score: float = 0.0
    confidence: float = 0.0
    reason: str = ""
    topic_fingerprint: str = ""
    grounded_context: dict[str, Any] = field(default_factory=dict)


@dataclass
class _UserSocialState:
    delivered: deque[float] = field(default_factory=lambda: deque(maxlen=24))
    social_delivered: deque[float] = field(default_factory=lambda: deque(maxlen=16))
    recent_topics: dict[str, float] = field(default_factory=dict)
    ignored: int = 0
    dismissed: int = 0
    negative: int = 0
    positive: int = 0
    active_topic: dict[str, Any] = field(default_factory=dict)


class SocialContextEngine:
    """Cheap, user-scoped social opportunity policy for the existing runtime."""

    SOCIAL_TRIGGERS = frozenset({
        "returned_after_absence",
        "long_active_session",
        "recent_success",
        "recent_failure",
        "unfinished_user_goal",
        "conversation_callback",
        "casual_interaction_gap",
        "celebration_context",
        "user_idle_then_returns",
        "interesting_recent_context",
    })
    EVENT_TRIGGER = {
        "user_returned": "returned_after_absence",
        "follow_up_relevant": "conversation_callback",
        "recent_success": "recent_success",
        "recent_failure": "recent_failure",
        "unfinished_user_goal": "unfinished_user_goal",
        "long_active_session": "long_active_session",
        "casual_interaction_gap": "casual_interaction_gap",
        "celebration_context": "celebration_context",
        "user_idle_then_returns": "user_idle_then_returns",
        "interesting_recent_context": "interesting_recent_context",
    }

    def __init__(self, *, now=None) -> None:
        self._now = now or time.time
        self._users: dict[str, _UserSocialState] = defaultdict(_UserSocialState)

    def evaluate(self, user_id: str, event: dict[str, Any], preferences: CompanionPreferences, context: dict[str, Any]) -> SocialOpportunity:
        trigger = str(event.get("social_trigger") or self.EVENT_TRIGGER.get(str(event.get("event") or "")) or "")
        if trigger not in self.SOCIAL_TRIGGERS:
            return self._skip("not_social")
        if not user_id:
            return self._skip("anonymous_session")
        if not preferences.social_proactivity or preferences.proactive_mode in {"off", "important_only"}:
            return self._skip("social_preference_off")

        mode = str(context.get("session_mode") or (context.get("conversation_state") or {}).get("conversation_mode") or "").lower()
        if mode in {"focus", "focused", "serious", "sensitive", "urgent"}:
            return self._skip(f"mode_{mode}")
        if context.get("do_not_disturb") or context.get("active_meeting") or context.get("active_voice_conversation"):
            return self._skip("user_unavailable")
        if not self._grounded(trigger, event, context):
            return self._skip("missing_grounded_context")

        now = self._now()
        state = self._users[user_id]
        self._prune(state, now)
        limit = {"balanced": 3, "companion": 6}.get(preferences.proactive_mode, 2)
        tolerance = max(0.25, min(1.0, preferences.social_interruption_tolerance))
        limit = max(1, round(limit * tolerance))
        if len(state.social_delivered) >= limit:
            return self._skip("interruption_budget")
        if state.negative >= 2 or state.dismissed >= 3:
            return self._skip("negative_reaction_budget")

        fingerprint = self._fingerprint(trigger, event)
        if fingerprint in state.recent_topics and now - state.recent_topics[fingerprint] < 6 * 3600:
            return self._skip("duplicate_topic")

        relevance = float(event.get("relevance") or event.get("importance") or 0.6)
        confidence = float(event.get("confidence") or 0.0)
        novelty = 1.0 if fingerprint not in state.recent_topics else 0.25
        timing = float(event.get("timing") or 0.7)
        reaction_penalty = min(0.45, state.dismissed * 0.12 + state.negative * 0.2 + state.ignored * 0.05)
        intensity_bonus = 0.12 if preferences.proactive_mode == "companion" else 0.0
        score = relevance * 0.32 + confidence * 0.28 + novelty * 0.2 + timing * 0.2 + intensity_bonus - reaction_penalty
        threshold = 0.61 if preferences.proactive_mode == "companion" else 0.72
        if score < threshold:
            return self._skip("low_social_opportunity", score)

        allow_speech = bool(event.get("allow_spoken_notice")) and preferences.proactive_mode == "companion"
        delivery: SocialDelivery = "speak" if allow_speech and score >= 0.82 else "visual"
        grounded = {
            "trigger": trigger,
            "title": str(event.get("title") or "")[:160],
            "summary": str(event.get("summary") or "")[:500],
            "recent_topic": str(context.get("recent_topic") or "")[:200],
            "unfinished_goal": str(event.get("unfinished_goal") or "")[:240],
            "absence_seconds": int(event.get("absence_seconds") or 0),
            "conversation_mode": mode or "casual",
        }
        logger.info("social.opportunity_detected trigger=%s delivery=%s score=%.2f", trigger, delivery, score)
        return SocialOpportunity(True, trigger, delivery, score, confidence, "eligible", fingerprint, grounded)

    def delivered(self, user_id: str, opportunity: SocialOpportunity, message: str) -> None:
        now = self._now()
        state = self._users[user_id]
        state.delivered.append(now)
        state.social_delivered.append(now)
        state.recent_topics[opportunity.topic_fingerprint] = now
        state.active_topic = {
            "trigger": opportunity.trigger,
            "reason": opportunity.reason,
            "grounded_context": opportunity.grounded_context,
            "message": message[:500],
            "created_at": now,
            "responded": False,
        }
        logger.info("social.proactive_delivered trigger=%s", opportunity.trigger)

    def reaction(self, user_id: str, reaction: str) -> None:
        state = self._users[user_id]
        normalized = reaction.lower()
        if normalized == "engaged":
            state.positive += 1
            if state.active_topic:
                state.active_topic["responded"] = True
        elif normalized == "dismissed":
            state.dismissed += 1
        elif normalized in {"negative", "stop_requested"}:
            state.negative += 2 if normalized == "stop_requested" else 1
        elif normalized == "ignored":
            state.ignored += 1
        elif normalized == "positive":
            state.positive += 1
        logger.info("social.proactive_%s", normalized)

    def active_thread(self, user_id: str) -> dict[str, Any]:
        return dict(self._users[user_id].active_topic)

    def _grounded(self, trigger: str, event: dict[str, Any], context: dict[str, Any]) -> bool:
        if trigger in {"returned_after_absence", "user_idle_then_returns"}:
            return float(event.get("absence_seconds") or 0) >= 900
        if trigger == "unfinished_user_goal":
            return bool(event.get("unfinished_goal") and event.get("memory_id"))
        if trigger == "conversation_callback":
            return bool(event.get("callback_text") or context.get("recent_topic"))
        if trigger in {"recent_success", "recent_failure", "celebration_context"}:
            return bool(event.get("title") or event.get("summary"))
        return bool(event.get("title") or event.get("summary") or context.get("recent_topic"))

    def _fingerprint(self, trigger: str, event: dict[str, Any]) -> str:
        identity = str(event.get("correlation_id") or event.get("memory_id") or event.get("topic") or event.get("title") or trigger)
        return hashlib.sha256(f"{trigger}:{identity.lower().strip()}".encode("utf-8")).hexdigest()[:20]

    def _prune(self, state: _UserSocialState, now: float) -> None:
        while state.delivered and now - state.delivered[0] > 3600:
            state.delivered.popleft()
        while state.social_delivered and now - state.social_delivered[0] > 3600:
            state.social_delivered.popleft()
        state.recent_topics = {key: value for key, value in state.recent_topics.items() if now - value < 24 * 3600}

    @staticmethod
    def _skip(reason: str, score: float = 0.0) -> SocialOpportunity:
        logger.info("social.opportunity_skipped reason=%s", reason)
        return SocialOpportunity(False, reason=reason, score=score)
