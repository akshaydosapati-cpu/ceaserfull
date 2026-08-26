from __future__ import annotations

from typing import Any

from core.schemas import ActionResult, CommandRequest, IntentResult
from working_memory.models import ContextSnapshot
from world_model.entity_resolver import EntityResolver, resolution_as_context
from world_model.graph_store import GraphStore
from world_model.queries import WorldModelQueries
from world_model.relationship_resolver import RelationshipResolver
from world_model.synchronizer import WorldModelSynchronizer


class SemanticWorldModel:
    def __init__(self, store: GraphStore | None = None) -> None:
        self.store = store or GraphStore()
        self.synchronizer = WorldModelSynchronizer(self.store)
        self.entity_resolver = EntityResolver(self.store)
        self.relationship_resolver = RelationshipResolver(self.store)
        self.queries = WorldModelQueries(self.store)

    def sync_from_working_memory(self, request: CommandRequest, snapshot: ContextSnapshot) -> None:
        self.synchronizer.sync_snapshot(request, snapshot)

    def update_after_result(self, request: CommandRequest, intent: IntentResult, result: ActionResult, snapshot: ContextSnapshot) -> None:
        self.synchronizer.update_after_result(request, intent, result, snapshot)

    def resolve_entity(self, text: str, *, session_id: str | None = None, entity_type=None):
        return self.entity_resolver.resolve(text, session_id=session_id, entity_type=entity_type)

    def as_context(self, session_id: str | None = None) -> dict[str, Any]:
        self.store.expire()
        current_project = self.queries.get_current_project(session_id)
        current_repository = self.queries.get_repository_for_project(current_project.id) if current_project else None
        active_resource = self.queries.get_active_resource(session_id)
        notion_pages = self.queries.get_notion_pages_for_project(current_project.id) if current_project else []
        project_resolution = self.entity_resolver.resolve_project("this project", session_id=session_id)
        repo_resolution = self.entity_resolver.resolve_repository("this repository", session_id=session_id)
        return {
            "entity_count": len(self.store.entities),
            "relationship_count": len(self.store.relationships),
            "current_project": self._dump_entity(current_project),
            "current_repository": self._dump_entity(current_repository),
            "active_resource": self._dump_entity(active_resource),
            "notion_pages_for_project": [self._dump_entity(page) for page in notion_pages],
            "project_resolution": resolution_as_context(project_resolution),
            "repository_resolution": resolution_as_context(repo_resolution),
        }

    def evidence_for_text(self, text: str, *, session_id: str | None = None) -> dict[str, Any]:
        project_resolution = self.entity_resolver.resolve_project(text, session_id=session_id)
        repository = None
        relationships_used = []
        if project_resolution.entity:
            repository = self.queries.get_repository_for_project(project_resolution.entity.id)
            relationships_used = [
                rel.id
                for rel in self.store.incoming(project_resolution.entity.id, "belongs_to")
                if repository and rel.source_id == repository.id
            ]
        elif "repo" in text.lower() or "repository" in text.lower():
            repo_resolution = self.entity_resolver.resolve_repository(text, session_id=session_id)
            repository = repo_resolution.entity
        active_resource = self.queries.get_active_resource(session_id)
        entities = [entity for entity in [project_resolution.entity, repository, active_resource] if entity]
        return {
            "world_entities_used": [self._dump_entity(entity) for entity in entities],
            "world_relationships_used": relationships_used,
            "world_resolution_reason": project_resolution.reason or ("active_resource" if active_resource else "none"),
            "resolved_project": self._dump_entity(project_resolution.entity),
            "resolved_repository": self._dump_entity(repository),
            "active_resource": self._dump_entity(active_resource),
            "ambiguity_candidates": [self._dump_entity(entity) for entity in project_resolution.ambiguity_candidates],
        }

    def _dump_entity(self, entity) -> dict[str, Any] | None:
        if not entity:
            return None
        try:
            return entity.model_dump()
        except AttributeError:
            return entity.dict()
