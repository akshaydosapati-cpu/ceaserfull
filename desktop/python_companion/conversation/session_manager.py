from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from core.schemas import ActionResult, CommandRequest, IntentResult
from conversation.companion_models import ConversationState
from conversation.language_analyzer import LanguageAnalyzer


@dataclass
class DesktopSession:
    session_id: str
    user_id: str = ""
    active: bool = True
    active_project: str = ""
    active_resource: dict[str, Any] = field(default_factory=dict)
    last_intent: str = ""
    last_capability: str = ""
    last_result: dict[str, Any] = field(default_factory=dict)
    recent_turns: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=16))
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    conversation_state: ConversationState | None = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "active": self.active,
            "active_project": self.active_project,
            "active_resource": self.active_resource,
            "last_intent": self.last_intent,
            "last_capability": self.last_capability,
            "last_result": self.last_result,
            "recent_turns": list(self.recent_turns),
            "updated_at": self.updated_at,
            "conversation_state": self.conversation_state.model_dump() if self.conversation_state else {},
        }


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, DesktopSession] = {}
        self._language = LanguageAnalyzer()

    def get(self, session_id: str, user_id: str = "") -> DesktopSession:
        raw_session_id = session_id or "desktop_session"
        key = f"{user_id}:{raw_session_id}" if user_id else raw_session_id
        session = self._sessions.get(key)
        if not session:
            session = DesktopSession(session_id=raw_session_id, user_id=user_id or "")
            session.conversation_state = ConversationState(conversation_id=raw_session_id)
            self._sessions[key] = session
        session.updated_at = time.time()
        return session

    def record(self, request: CommandRequest, intent: IntentResult, result: ActionResult) -> DesktopSession:
        session = self.get(request.session_id, request.user_id)
        stt = dict(request.context.get("stt") or request.metadata.get("stt") or {})
        language = self._language.analyze_provider(
            str(stt.get("original_transcript") or request.raw_text),
            str(stt.get("detected_language") or stt.get("language") or ""),
        )
        if session.conversation_state:
            session.conversation_state.detected_language = language.primary_language
            session.conversation_state.code_switch_languages = language.secondary_languages
            session.conversation_state.last_interaction_at = time.time()
            session.conversation_state.familiarity = min(1.0, session.conversation_state.familiarity + 0.02)
            session.conversation_state.active_project = session.active_project
        session.last_intent = intent.intent
        session.last_capability = intent.capability or ""
        session.last_result = {
            "status": result.status,
            "summary": result.summary,
            "capability": result.capability,
            "verified": result.verified,
            "data": result.data,
        }
        if result.data.get("path"):
            session.active_resource = {"type": "file", "path": result.data.get("path")}
        session.recent_turns.append(
            {
                "source": request.source,
                "raw_text": request.raw_text,
                "normalized_text": request.normalized_text,
                "intent": intent.intent,
                "capability": intent.capability,
                "status": result.status,
                "summary": result.summary[:500],
                "timestamp": time.time(),
            }
        )
        session.updated_at = time.time()
        return session
