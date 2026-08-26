from __future__ import annotations

from world_model.graph_store import GraphStore
from world_model.models import WorldEntity, WorldRelationship


class WorldModelQueries:
    def __init__(self, store: GraphStore) -> None:
        self.store = store

    def get_current_project(self, session_id: str | None = None) -> WorldEntity | None:
        sessions = self.store.find_by_type("user_session")
        if session_id:
            sessions = [session for session in sessions if session.attributes.get("session_id") == session_id or session.name == session_id]
        sessions = sorted(sessions, key=lambda entity: entity.updated_at, reverse=True)
        for session in sessions:
            for rel in self.store.outgoing(session.id, "working_on"):
                project = self.store.entity(rel.target_id)
                if project and project.type == "project":
                    return project
        projects = sorted(self.store.find_by_type("project"), key=lambda entity: entity.updated_at, reverse=True)
        return projects[0] if len(projects) == 1 else None

    def get_repository_for_project(self, project_id: str) -> WorldEntity | None:
        repos: list[WorldEntity] = []
        for rel in self.store.incoming(project_id, "belongs_to"):
            entity = self.store.entity(rel.source_id)
            if entity and entity.type == "repository":
                repos.append(entity)
        repos = sorted(repos, key=lambda entity: entity.updated_at, reverse=True)
        return repos[0] if repos else None

    def get_files_for_repository(self, repository_id: str) -> list[WorldEntity]:
        files: list[WorldEntity] = []
        for rel in self.store.incoming(repository_id, "belongs_to"):
            entity = self.store.entity(rel.source_id)
            if entity and entity.type in {"file", "document"}:
                files.append(entity)
        return sorted(files, key=lambda entity: entity.updated_at, reverse=True)

    def get_notion_pages_for_project(self, project_id: str) -> list[WorldEntity]:
        pages: list[WorldEntity] = []
        for rel in self.store.incoming(project_id, "connected_to"):
            entity = self.store.entity(rel.source_id)
            if entity and entity.type == "notion_page":
                pages.append(entity)
        return sorted(pages, key=lambda entity: entity.updated_at, reverse=True)

    def get_active_resource(self, session_id: str | None = None) -> WorldEntity | None:
        sessions = self.store.find_by_type("user_session")
        if session_id:
            sessions = [session for session in sessions if session.attributes.get("session_id") == session_id or session.name == session_id]
        sessions = sorted(sessions, key=lambda entity: entity.updated_at, reverse=True)
        for session in sessions:
            for rel in sorted(self.store.outgoing(session.id, "current_for"), key=lambda item: item.updated_at, reverse=True):
                entity = self.store.entity(rel.target_id)
                if entity and entity.type in {"file", "document", "webpage", "folder"}:
                    return entity
        return None

    def get_current_goal(self, session_id: str | None = None) -> WorldEntity | None:
        sessions = self.store.find_by_type("user_session")
        if session_id:
            sessions = [session for session in sessions if session.attributes.get("session_id") == session_id or session.name == session_id]
        for session in sorted(sessions, key=lambda entity: entity.updated_at, reverse=True):
            for rel in self.store.outgoing(session.id, "working_on"):
                goal = self.store.entity(rel.target_id)
                if goal and goal.type == "goal":
                    return goal
        return None

    def get_resources_discussed_in_conversation(self, conversation_id: str) -> list[WorldEntity]:
        resources: list[WorldEntity] = []
        for rel in self.store.incoming(conversation_id, "discussed_in"):
            entity = self.store.entity(rel.source_id)
            if entity and entity.type in {"file", "document", "webpage", "repository", "notion_page"}:
                resources.append(entity)
        return sorted(resources, key=lambda entity: entity.updated_at, reverse=True)

    def get_projects_connected_to_session(self, session_id: str) -> list[WorldEntity]:
        session = self.store.entity(f"user_session:{session_id}") or next(
            (item for item in self.store.find_by_type("user_session") if item.attributes.get("session_id") == session_id),
            None,
        )
        if not session:
            return []
        projects = []
        for rel in self.store.outgoing(session.id, "working_on"):
            entity = self.store.entity(rel.target_id)
            if entity and entity.type == "project":
                projects.append(entity)
        return sorted(projects, key=lambda entity: entity.updated_at, reverse=True)

    def relationships_for(self, entity_id: str) -> list[WorldRelationship]:
        return self.store.outgoing(entity_id) + self.store.incoming(entity_id)
