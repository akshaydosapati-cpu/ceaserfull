from __future__ import annotations

import re
from typing import Any

from world_model.graph_store import GraphStore
from world_model.models import EntityResolution, EntityType, WorldEntity
from world_model.queries import WorldModelQueries


PROJECT_REF_PATTERN = re.compile(r"\b(this project|my project|current project|project notes)\b", re.IGNORECASE)
REPO_REF_PATTERN = re.compile(r"\b(this repo|this repository|current repo|current repository)\b", re.IGNORECASE)
RESOURCE_REF_PATTERN = re.compile(r"\b(this|it|that|current document|current file|previous resource|last one)\b", re.IGNORECASE)


class EntityResolver:
    def __init__(self, store: GraphStore) -> None:
        self.store = store
        self.queries = WorldModelQueries(store)

    def resolve(self, text: str, *, entity_type: EntityType | None = None, session_id: str | None = None) -> EntityResolution:
        lowered = str(text or "").lower()
        explicit = self._resolve_explicit_name(text, entity_type)
        if explicit.entity or explicit.ambiguous:
            return explicit

        if PROJECT_REF_PATTERN.search(lowered):
            project = self.queries.get_current_project(session_id)
            if project:
                return EntityResolution(entity=project, confidence=0.86, reason="current_project", evidence={"matched": "project_reference"})
            projects = self.store.find_by_type("project")
            if len(projects) > 1:
                return EntityResolution(ambiguity_candidates=projects, confidence=0.0, reason="ambiguous_projects")

        if REPO_REF_PATTERN.search(lowered):
            project = self.queries.get_current_project(session_id)
            repo = self.queries.get_repository_for_project(project.id) if project else None
            if repo:
                return EntityResolution(entity=repo, confidence=0.84, reason="current_repository", evidence={"project": project.name if project else ""})

        if RESOURCE_REF_PATTERN.search(lowered):
            resource = self.queries.get_active_resource(session_id)
            if resource:
                return EntityResolution(entity=resource, confidence=0.8, reason="active_resource", evidence={"matched": "resource_reference"})

        recent = self._most_recent(entity_type)
        if recent:
            return EntityResolution(entity=recent, confidence=0.52, reason="most_recent_matching_entity")
        return EntityResolution(reason="unresolved")

    def resolve_project(self, text: str, session_id: str | None = None) -> EntityResolution:
        return self.resolve(text, entity_type="project", session_id=session_id)

    def resolve_repository(self, text: str, session_id: str | None = None) -> EntityResolution:
        return self.resolve(text, entity_type="repository", session_id=session_id)

    def _resolve_explicit_name(self, text: str, entity_type: EntityType | None) -> EntityResolution:
        candidates: list[WorldEntity] = []
        for entity in self.store.entities.values():
            if entity_type and entity.type != entity_type:
                continue
            if self._mentions_entity(text, entity):
                candidates.append(entity)
        candidates = sorted(candidates, key=lambda item: item.updated_at, reverse=True)
        if len(candidates) == 1:
            return EntityResolution(entity=candidates[0], confidence=0.9, reason="explicit_name", evidence={"name": candidates[0].name})
        if len(candidates) > 1:
            return EntityResolution(ambiguity_candidates=candidates, reason="explicit_name_ambiguous")
        return EntityResolution(reason="no_explicit_name")

    def _mentions_entity(self, text: str, entity: WorldEntity) -> bool:
        lowered = str(text or "").lower()
        names = [entity.name, *[alias for alias in entity.attributes.get("aliases", []) if isinstance(alias, str)]]
        return any(name and str(name).lower() in lowered for name in names)

    def _most_recent(self, entity_type: EntityType | None) -> WorldEntity | None:
        entities = [entity for entity in self.store.entities.values() if entity_type is None or entity.type == entity_type]
        entities = sorted(entities, key=lambda item: item.updated_at, reverse=True)
        return entities[0] if len(entities) == 1 else None


def resolution_as_context(resolution: EntityResolution) -> dict[str, Any]:
    def dump_entity(entity: WorldEntity | None) -> dict[str, Any] | None:
        if not entity:
            return None
        try:
            return entity.model_dump()
        except AttributeError:
            return entity.dict()

    return {
        "entity": dump_entity(resolution.entity),
        "confidence": resolution.confidence,
        "evidence": resolution.evidence,
        "ambiguity_candidates": [dump_entity(entity) for entity in resolution.ambiguity_candidates],
        "reason": resolution.reason,
        "ambiguous": resolution.ambiguous,
    }
