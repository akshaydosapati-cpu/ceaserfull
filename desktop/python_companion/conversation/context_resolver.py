from __future__ import annotations

from typing import Any

from awareness.awareness_engine import AwarenessEngine
from core.schemas import CommandRequest
from conversation.reference_resolver import ReferenceResolver
from conversation.continuation_resolver import ConversationContinuationResolver
from conversation.relationship_model import RelationshipModel
from conversation.session_manager import SessionManager
from experience.experience_engine import ExperienceEngine
from prediction.prediction_engine import PredictionEngine
from working_memory.working_memory import WorkingMemoryManager
from world_model.world_model import SemanticWorldModel
from long_term_memory.memory_manager import LongTermMemoryManager


class WorldContextResolver:
    def __init__(
        self,
        session_manager: SessionManager | None = None,
        reference_resolver: ReferenceResolver | None = None,
        relationship_model: RelationshipModel | None = None,
        working_memory: WorkingMemoryManager | None = None,
        world_model: SemanticWorldModel | None = None,
        long_term_memory: LongTermMemoryManager | None = None,
        awareness_engine: AwarenessEngine | None = None,
        experience_engine: ExperienceEngine | None = None,
        prediction_engine: PredictionEngine | None = None,
    ) -> None:
        self.session_manager = session_manager or SessionManager()
        self.reference_resolver = reference_resolver or ReferenceResolver()
        self.continuation_resolver = ConversationContinuationResolver()
        self.relationship_model = relationship_model or RelationshipModel()
        self.working_memory = working_memory or WorkingMemoryManager()
        self.world_model = world_model or SemanticWorldModel()
        self.long_term_memory = long_term_memory
        self.awareness_engine = awareness_engine
        self.experience_engine = experience_engine
        self.prediction_engine = prediction_engine

    def resolve(self, request: CommandRequest, *, fast_local: bool = False) -> dict[str, Any]:
        self.working_memory.update_before_request(request)
        working_snapshot = self.working_memory.snapshot()
        self.world_model.sync_from_working_memory(request, working_snapshot)
        working_context = working_snapshot.as_context()
        world_context = self.world_model.as_context(request.session_id)
        session = self.session_manager.get(request.session_id, request.user_id)
        session_snapshot = session.snapshot()
        relationship_domain = self.relationship_model.observe(request.normalized_text)
        session_references = self.reference_resolver.resolve(request.normalized_text, session_snapshot)
        continuation_references = self.continuation_resolver.resolve(request.normalized_text, session_snapshot, working_context)
        working_references = self.working_memory.resolve_reference(request.normalized_text)
        references = self._merge_references(continuation_references, session_references, working_references)
        desktop_context = {
            "foreground_app": working_snapshot.active_app,
            "window_title": working_snapshot.active_window,
            "current_folder": working_snapshot.current_folder,
            "active_file": working_snapshot.selected_file,
            "active_process": working_snapshot.active_process,
            "current_workspace": working_snapshot.current_workspace,
        }
        long_term_context = self.long_term_memory.retrieve(request) if self.long_term_memory and not fast_local else {"memories": [], "confidence": 0.0, "memory_reason": "fast_local" if fast_local else "not_configured"}
        companion_preferences = self.long_term_memory.companion_preferences(request.user_id) if self.long_term_memory and not fast_local else {}
        awareness_context = self.awareness_engine.as_context() if self.awareness_engine else {"recent_events": [], "notification_cards": [], "delayed_events": []}
        experience_context = self.experience_engine.as_context() if self.experience_engine else {"capability_success": {}, "repeated_commands": [], "repeated_workflows": []}
        prediction_context = (
            self.prediction_engine.as_context(request, working_context, world_context, awareness_context, experience_context)
            if self.prediction_engine and not fast_local
            else {"predictions": [], "preparation": {}, "cache": {}, "summary": "fast_local" if fast_local else "not_configured"}
        )
        return {
            **dict(request.context or {}),
            "working_memory": working_context,
            "context_snapshot": working_context,
            "world_model": world_context,
            "long_term_memory": long_term_context,
            "companion_preferences": companion_preferences,
            "awareness": awareness_context,
            "experience": experience_context,
            "prediction": prediction_context,
            "_working_memory_manager": self.working_memory,
            "_world_model": self.world_model,
            "session": session_snapshot,
            "conversation_state": session_snapshot.get("conversation_state") or {},
            "desktop": desktop_context,
            "relationship": {
                "observed_domain": relationship_domain,
                **self.relationship_model.profile(),
            },
            "references": references,
            "context_source": "working_memory",
        }

    def record_turn(self, request, intent, result):
        turn = self.session_manager.record(request, intent, result)
        self.working_memory.update_after_result(request, intent, result)
        self.world_model.update_after_result(request, intent, result, self.working_memory.snapshot())
        if self.long_term_memory:
            memory_delta = self.long_term_memory.after_result(request, intent, result)
            if memory_delta:
                result.evidence.setdefault("long_term_memory", memory_delta)
        return turn

    def _merge_references(self, continuation: dict[str, Any], session_references: dict[str, Any], working_references: dict[str, Any]) -> dict[str, Any]:
        if continuation.get("clarification_required"):
            return continuation
        if not any(item.get("follow_up_detected") for item in (continuation, session_references, working_references)):
            return session_references
        merged = dict(session_references or {})
        merged.update(working_references or {})
        merged.update(continuation or {})
        resolved = dict((session_references or {}).get("resolved_reference") or {})
        resolved.update(dict((working_references or {}).get("resolved_reference") or {}))
        resolved.update(dict((continuation or {}).get("resolved_reference") or {}))
        merged["follow_up_detected"] = True
        merged["resolved_reference"] = resolved
        return merged
