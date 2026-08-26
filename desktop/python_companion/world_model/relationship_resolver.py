from __future__ import annotations

from world_model.graph_store import GraphStore
from world_model.models import WorldEntity
from world_model.queries import WorldModelQueries


class RelationshipResolver:
    def __init__(self, store: GraphStore) -> None:
        self.store = store
        self.queries = WorldModelQueries(store)

    def repository_for_project(self, project: WorldEntity | None) -> WorldEntity | None:
        if not project:
            return None
        return self.queries.get_repository_for_project(project.id)

    def notion_pages_for_project(self, project: WorldEntity | None) -> list[WorldEntity]:
        if not project:
            return []
        return self.queries.get_notion_pages_for_project(project.id)

    def related_entities(self, entity: WorldEntity | None) -> list[WorldEntity]:
        if not entity:
            return []
        related: list[WorldEntity] = []
        for relationship in self.queries.relationships_for(entity.id):
            other_id = relationship.target_id if relationship.source_id == entity.id else relationship.source_id
            other = self.store.entity(other_id)
            if other:
                related.append(other)
        return sorted(related, key=lambda item: item.updated_at, reverse=True)
