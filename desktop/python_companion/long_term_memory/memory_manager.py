from __future__ import annotations

import hashlib
import re
import time
from typing import Any

from core.schemas import ActionResult, CommandRequest, IntentResult
from long_term_memory.memory_extractor import MemoryExtractor
from long_term_memory.memory_policy import MemoryPolicy
from long_term_memory.memory_retriever import MemoryRetriever
from long_term_memory.memory_store import LocalJsonMemoryStore, MemoryStoreAdapter
from long_term_memory.models import LongTermMemoryItem, MemoryCandidate, MemoryQuery
from conversation.companion_models import CompanionPreferences


class LongTermMemoryManager:
    def __init__(self, store: MemoryStoreAdapter | None = None) -> None:
        self.store = store or LocalJsonMemoryStore()
        self.policy = MemoryPolicy()
        self.extractor = MemoryExtractor()
        self.retriever = MemoryRetriever(self.store)
        self.disabled_sessions: set[str] = set()
        self.pending_confirmations: dict[str, MemoryCandidate] = {}

    def save_companion_preferences(self, user_id: str, preferences: dict[str, Any]) -> CompanionPreferences:
        if not user_id:
            raise ValueError("authenticated user required")
        validated = CompanionPreferences.model_validate(preferences)
        now = time.time()
        memory_id = "companion_preferences_" + hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:16]
        existing = next((item for item in self.store.list(user_id) if item.id == memory_id), None)
        self.store.save(LongTermMemoryItem(
            id=memory_id,
            user_id=user_id,
            type="preference",
            content="CEASER companion preferences",
            structured_data={"companion_preferences": validated.model_dump()},
            source="user_settings",
            confidence=1.0,
            importance=0.8,
            created_at=existing.created_at if existing else now,
            updated_at=now,
            user_confirmed=True,
        ))
        return validated

    def companion_preferences(self, user_id: str) -> dict[str, Any]:
        if not user_id:
            return {}
        for item in reversed(self.store.list(user_id)):
            preferences = item.structured_data.get("companion_preferences")
            if preferences:
                return CompanionPreferences.model_validate(preferences).model_dump()
        return {}

    def handle_command(self, request: CommandRequest) -> ActionResult | None:
        text = request.normalized_text.strip()
        lowered = text.lower()
        if re.search(r"\b(do not remember this session|disable memory for this session)\b", lowered):
            self.disabled_sessions.add(request.session_id)
            return ActionResult(status="completed", capability="memory.disable_session", summary="I will not remember anything from this session.", spoken_response="Memory is off for this session.", verified=True, evidence={"memory_reason": "session_disabled"})
        if lowered.startswith("remember that ") or lowered.startswith("remember "):
            return self._remember(request)
        if re.search(r"\bwhat do you remember about me\b|\blist memories\b|\bshow my memories\b", lowered):
            return self._list(request)
        if lowered.startswith("forget") or lowered.startswith("clear my"):
            return self._forget(request)
        return None

    def retrieve(self, request: CommandRequest) -> dict[str, Any]:
        if not request.user_id or request.session_id in self.disabled_sessions:
            return {"memories": [], "confidence": 0.0, "memory_reason": "disabled_or_anonymous"}
        result = self.retriever.retrieve(MemoryQuery(user_id=request.user_id, text=request.normalized_text, limit=5))
        return {
            "memories": [self._dump(item) for item in result.memories],
            "confidence": result.confidence,
            "memory_reason": result.reason,
        }

    def after_result(self, request: CommandRequest, intent: IntentResult, result: ActionResult) -> dict[str, Any]:
        if request.session_id in self.disabled_sessions or not request.user_id:
            return {"memories_created": [], "memories_updated": [], "memory_reason": "session_disabled_or_anonymous"}
        if result.status != "completed" or not result.verified:
            return {"memories_created": [], "memories_updated": [], "memory_reason": "unverified_result"}
        candidates = self.extractor.extract_from_text(request.normalized_text)
        created = []
        updated = []
        for candidate in candidates:
            allowed, candidate, reason = self.policy.evaluate(candidate, explicit_remember="remember" in request.normalized_text.lower(), session_disabled=False)
            if not allowed:
                continue
            item, was_update = self._persist(request.user_id, candidate, confirmed=True)
            (updated if was_update else created).append(self._dump(item))
        return {"memories_created": created, "memories_updated": updated, "memory_reason": "post_result_extraction"}

    def _remember(self, request: CommandRequest) -> ActionResult:
        if not request.user_id:
            return ActionResult(status="failed", capability="memory.remember", summary="Sign in before saving long-term memory.", verified=True, error_code="memory_requires_user")
        candidates = self.extractor.extract_from_text(request.normalized_text)
        if not candidates:
            return ActionResult(status="needs_input", capability="memory.remember", summary="Tell me exactly what you want me to remember.", verified=True)
        created = []
        pending = []
        for candidate in candidates:
            allowed, candidate, reason = self.policy.evaluate(candidate, explicit_remember=True, session_disabled=request.session_id in self.disabled_sessions)
            if not allowed:
                if reason == "sensitive_requires_confirmation":
                    confirmation_id = self._candidate_id(request.user_id, candidate)
                    self.pending_confirmations[confirmation_id] = candidate
                    pending.append({"confirmation_id": confirmation_id, "content": candidate.content})
                    continue
                return ActionResult(status="failed", capability="memory.remember", summary="I cannot store that in memory.", verified=True, error_code=reason, evidence={"memory_reason": reason})
            item, _ = self._persist(request.user_id, candidate, confirmed=True)
            created.append(self._dump(item))
        if pending and not created:
            return ActionResult(status="needs_confirmation", capability="memory.remember", summary="That may be sensitive. Please confirm before I remember it.", verified=True, data={"pending_memory_confirmation": pending}, evidence={"memory_reason": "sensitive_requires_confirmation"})
        return ActionResult(status="completed", capability="memory.remember", summary="Remembered.", spoken_response="Remembered.", data={"memories_created": created}, evidence={"memories_created": [item["id"] for item in created], "memory_reason": "explicit_remember"}, verified=True)

    def _list(self, request: CommandRequest) -> ActionResult:
        memories = [self._dump(item) for item in self.store.list(request.user_id)]
        if not memories:
            return ActionResult(status="completed", capability="memory.list", summary="I do not have any long-term memories saved for you yet.", verified=True, data={"memories": []})
        summary = "I remember: " + "; ".join(item["content"] for item in memories[:5])
        return ActionResult(status="completed", capability="memory.list", summary=summary, spoken_response=summary[:180], verified=True, data={"memories": memories}, evidence={"memories_used": [item["id"] for item in memories]})

    def _forget(self, request: CommandRequest) -> ActionResult:
        lowered = request.normalized_text.lower()
        if "study preference" in lowered:
            deleted = self.store.delete_by_type(request.user_id, "preference")
        elif "ceaser project memory" in lowered or "project memory" in lowered:
            deleted = self.store.delete_by_type(request.user_id, "project")
        elif "that" in lowered:
            memories = self.store.list(request.user_id)
            deleted = self.store.delete(request.user_id, memories[-1].id) if memories else 0
        else:
            deleted = 0
            for memory_type in ["preference", "project", "goal", "episodic", "relationship", "workflow_preference"]:
                if memory_type.replace("_", " ") in lowered:
                    deleted += self.store.delete_by_type(request.user_id, memory_type)
        return ActionResult(status="completed", capability="memory.forget", summary=f"Forgot {deleted} matching memory item(s).", spoken_response="Forgot it." if deleted else "I did not find a matching memory.", verified=True, evidence={"memories_deleted": deleted, "memory_reason": "forget_command"})

    def _persist(self, user_id: str, candidate: MemoryCandidate, confirmed: bool) -> tuple[LongTermMemoryItem, bool]:
        memory_id = self._candidate_id(user_id, candidate)
        existing = next((item for item in self.store.list(user_id) if item.id == memory_id), None)
        now = time.time()
        item = LongTermMemoryItem(
            id=memory_id,
            user_id=user_id,
            type=candidate.type,
            content=candidate.content,
            structured_data=candidate.structured_data,
            source=candidate.source,
            confidence=candidate.confidence,
            importance=candidate.importance,
            created_at=existing.created_at if existing else now,
            updated_at=now,
            user_confirmed=confirmed,
            sensitive=candidate.sensitive,
            status="active",
        )
        self.store.save(item)
        return item, existing is not None

    def _candidate_id(self, user_id: str, candidate: MemoryCandidate) -> str:
        key = f"{user_id}:{candidate.type}:{candidate.structured_data or candidate.content}".lower()
        return "mem_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]

    def _dump(self, item: LongTermMemoryItem) -> dict[str, Any]:
        return item.model_dump() if hasattr(item, "model_dump") else item.dict()
