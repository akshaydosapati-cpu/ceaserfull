from __future__ import annotations

from core.schemas import ActionResult, CommandRequest, IntentResult
from working_memory.context_snapshot import build_context_snapshot
from working_memory.memory_sources import ClipboardSource, ConversationSource, DesktopSource, IntegrationSource, ProjectSource, ResourceSource
from working_memory.memory_store import MemoryStore
from working_memory.models import ContextSnapshot
from working_memory.reference_resolver import WorkingReferenceResolver


class WorkingMemoryManager:
    def __init__(self, store: MemoryStore | None = None) -> None:
        self.store = store or MemoryStore()
        self.desktop = DesktopSource()
        self.project = ProjectSource()
        self.conversation = ConversationSource()
        self.clipboard = ClipboardSource()
        self.resource = ResourceSource()
        self.integration = IntegrationSource()
        self.reference_resolver = WorkingReferenceResolver()

    def update_before_request(self, request: CommandRequest) -> None:
        self.store.expire()
        self.desktop.update(self.store, request)
        self.project.update(self.store, request)
        self.clipboard.update(self.store, request)
        self.resource.update(self.store, request)
        self.integration.update(self.store, request)
        self.conversation.update_before(self.store, request)

    def update_after_result(self, request: CommandRequest, intent: IntentResult, result: ActionResult) -> None:
        self.store.expire()
        self.resource.update(self.store, request, result)
        self.integration.update(self.store, request, result)
        self.conversation.update_after(self.store, request, intent, result)

    def snapshot(self) -> ContextSnapshot:
        self.store.expire()
        return build_context_snapshot(self.store)

    def resolve_reference(self, text: str) -> dict:
        return self.reference_resolver.resolve(text, self.snapshot())
