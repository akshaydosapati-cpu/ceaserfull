from __future__ import annotations

import os
import time
from typing import Any

from conversation.companion_models import CompanionPreferences, ProactiveDecision


class ProactiveConversationEngine:
    TRUSTED_EVENTS = frozenset({"task_completed", "task_failed", "build_completed", "build_failed", "download_completed", "meeting_upcoming", "reminder_due", "user_returned", "important_project_change", "workflow_completed", "workflow_finished", "follow_up_relevant", "recent_success", "recent_failure", "unfinished_user_goal", "long_active_session", "casual_interaction_gap", "celebration_context", "user_idle_then_returns", "interesting_recent_context"})

    def __init__(self, cooldown_seconds: int | None = None) -> None:
        self.cooldown_seconds = cooldown_seconds or int(os.getenv("CEASER_PROACTIVE_COOLDOWN_SECONDS", "900"))
        self._last_initiated: dict[str, float] = {}
        self._dismissed_until: dict[str, float] = {}

    def evaluate(self, user_id: str, event: dict[str, Any], preferences: CompanionPreferences, context: dict[str, Any] | None = None) -> ProactiveDecision:
        context = context or {}
        event_type = str(event.get("event") or event.get("type") or "")
        if event_type not in self.TRUSTED_EVENTS:
            return self._no("untrusted_trigger")
        if preferences.proactive_mode == "off":
            return self._no("preference_off")
        now = time.time()
        if now < self._dismissed_until.get(user_id, 0):
            return self._no("recently_dismissed")
        if now - self._last_initiated.get(user_id, 0) < self.cooldown_seconds:
            return self._no("cooldown")
        if context.get("do_not_disturb") or context.get("active_meeting") or context.get("active_voice_conversation"):
            return self._no("user_unavailable")
        importance = float(event.get("importance") or 0.5)
        urgency = float(event.get("urgency") or 0.0)
        confidence = float(event.get("confidence") or 0.0)
        score = importance * 0.45 + urgency * 0.3 + confidence * 0.25
        if preferences.proactive_mode == "important_only" and score < 0.75:
            return self._no("below_important_threshold")
        threshold = 0.5 if preferences.proactive_mode == "companion" else 0.55
        if score < threshold:
            return self._no("low_relevance")
        priority = "urgent" if urgency >= 0.85 else "important" if score >= 0.75 else "normal"
        channel = "notification" if priority in {"important", "urgent"} else "activity"
        self._last_initiated[user_id] = now
        return ProactiveDecision(should_initiate=True, priority=priority, delivery_channel=channel, tone="urgent" if priority == "urgent" else "work", reason="trusted_event_policy", structured_trigger={key: value for key, value in event.items() if key not in {"content", "raw_text"}})

    def dismiss(self, user_id: str) -> None:
        self._dismissed_until[user_id] = time.time() + self.cooldown_seconds

    @staticmethod
    def _no(reason: str) -> ProactiveDecision:
        return ProactiveDecision(should_initiate=False, reason=reason)
