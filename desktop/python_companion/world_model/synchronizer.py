from __future__ import annotations

import os
from typing import Any

from core.schemas import ActionResult, CommandRequest, IntentResult
from working_memory.models import ContextSnapshot
from world_model.graph_store import GraphStore
from world_model.models import WorldEntity


class WorldModelSynchronizer:
    def __init__(self, store: GraphStore) -> None:
        self.store = store

    def sync_snapshot(self, request: CommandRequest, snapshot: ContextSnapshot) -> None:
        self.store.expire()
        session = self._session(request)
        conversation = self.store.upsert_entity(
            "conversation",
            request.session_id,
            attributes={"session_id": request.session_id, "last_command": snapshot.last_command},
            source="conversation",
            ttl_seconds=1800,
        )
        self.store.upsert_relationship(conversation.id, "current_for", session.id, source="working_memory", ttl_seconds=1800)

        workspace = self._workspace(snapshot)
        if workspace:
            self.store.upsert_relationship(session.id, "active_in", workspace.id, source="working_memory", ttl_seconds=180)

        project = self._project(snapshot)
        if project:
            self.store.upsert_relationship(session.id, "working_on", project.id, source="working_memory", ttl_seconds=1800)
            self.store.upsert_relationship(conversation.id, "discussed_in", project.id, source="conversation", ttl_seconds=1800)

        repository = self._repository(snapshot, project)
        if repository and project:
            self.store.upsert_relationship(repository.id, "belongs_to", project.id, source="working_memory", ttl_seconds=1800)

        folder = self._folder(snapshot, project)
        if folder and project:
            self.store.upsert_relationship(folder.id, "belongs_to", project.id, source="working_memory", ttl_seconds=1800)

        file_entity = self._file(snapshot, repository, folder)
        if file_entity:
            self.store.upsert_relationship(session.id, "current_for", file_entity.id, source="working_memory", ttl_seconds=600)
            self.store.upsert_relationship(file_entity.id, "discussed_in", conversation.id, source="conversation", ttl_seconds=1800)
            if repository:
                self.store.upsert_relationship(file_entity.id, "belongs_to", repository.id, source="working_memory", ttl_seconds=1800)
            elif folder:
                self.store.upsert_relationship(file_entity.id, "stored_in", folder.id, source="working_memory", ttl_seconds=1800)

        resource = self._resource(snapshot)
        if resource:
            self.store.upsert_relationship(session.id, "current_for", resource.id, source="working_memory", ttl_seconds=600)
            self.store.upsert_relationship(resource.id, "discussed_in", conversation.id, source="conversation", ttl_seconds=1800)
            if project:
                self.store.upsert_relationship(resource.id, "associated_with", project.id, source="working_memory", ttl_seconds=1800)

        notion_page = self._notion_page(snapshot)
        if notion_page and project:
            self.store.upsert_relationship(notion_page.id, "connected_to", project.id, source="working_memory", ttl_seconds=1800)

        for provider in snapshot.connected_integrations:
            integration = self.store.upsert_entity("integration", provider, attributes={"provider": provider}, source="integration", ttl_seconds=600)
            self.store.upsert_relationship(integration.id, "connected_to", session.id, source="working_memory", ttl_seconds=600)

    def update_after_result(self, request: CommandRequest, intent: IntentResult, result: ActionResult, snapshot: ContextSnapshot) -> None:
        if result.status == "failed" or result.verified is False:
            return
        session = self._session(request)
        project = self._project(snapshot)
        capability = result.capability or intent.capability or ""
        data = result.data or {}

        if capability in {"desktop.open_file", "ai.summarize_document", "ai.explain_content"} and data.get("path"):
            name = data.get("name") or os.path.basename(str(data.get("path")))
            entity = self.store.upsert_entity("file", name, attributes={"path": data.get("path")}, source=capability, ttl_seconds=1800)
            self.store.upsert_relationship(session.id, "current_for", entity.id, source=capability, ttl_seconds=900)
            if project:
                self.store.upsert_relationship(entity.id, "associated_with", project.id, source=capability, ttl_seconds=1800)

        if capability.startswith("github.") and data.get("repository"):
            repo = self.store.upsert_entity("repository", str(data.get("repository")), attributes={"provider": "github"}, source=capability, ttl_seconds=1800)
            if project:
                self.store.upsert_relationship(repo.id, "belongs_to", project.id, source=capability, ttl_seconds=1800)
            self.store.upsert_relationship(session.id, "current_for", repo.id, source=capability, ttl_seconds=900)

        if capability.startswith("notion.") and data.get("notion_page"):
            page = self.store.upsert_entity("notion_page", str(data.get("notion_page")), attributes={"provider": "notion"}, source=capability, ttl_seconds=1800)
            if project:
                self.store.upsert_relationship(page.id, "connected_to", project.id, source=capability, ttl_seconds=1800)

    def _session(self, request: CommandRequest) -> WorldEntity:
        return self.store.upsert_entity(
            "user_session",
            request.session_id,
            attributes={"session_id": request.session_id, "user_id": request.user_id},
            source="session",
            ttl_seconds=1800,
            entity_id=f"user_session:{request.session_id}",
        )

    def _workspace(self, snapshot: ContextSnapshot) -> WorldEntity | None:
        name = snapshot.current_workspace or snapshot.active_app or snapshot.active_window
        if not name:
            return None
        return self.store.upsert_entity(
            "local_workspace",
            name,
            attributes={"app": snapshot.active_app, "process": snapshot.active_process, "window": snapshot.active_window},
            source="desktop",
            ttl_seconds=300,
        )

    def _project(self, snapshot: ContextSnapshot) -> WorldEntity | None:
        name = snapshot.current_project or snapshot.repository or snapshot.github_repository
        if not name:
            return None
        return self.store.upsert_entity("project", name, attributes={"aliases": [name]}, source="working_memory", ttl_seconds=1800)

    def _repository(self, snapshot: ContextSnapshot, project: WorldEntity | None) -> WorldEntity | None:
        name = snapshot.repository or snapshot.github_repository or (project.name if project else "")
        if not name:
            return None
        return self.store.upsert_entity("repository", name, attributes={"branch": snapshot.branch, "language": snapshot.current_language}, source="working_memory", ttl_seconds=1800)

    def _folder(self, snapshot: ContextSnapshot, project: WorldEntity | None) -> WorldEntity | None:
        if not snapshot.current_folder:
            return None
        return self.store.upsert_entity("folder", os.path.basename(snapshot.current_folder) or snapshot.current_folder, attributes={"path": snapshot.current_folder}, source="working_memory", ttl_seconds=1800)

    def _file(self, snapshot: ContextSnapshot, repository: WorldEntity | None, folder: WorldEntity | None) -> WorldEntity | None:
        if not snapshot.selected_file:
            return None
        return self.store.upsert_entity(
            "file",
            os.path.basename(snapshot.selected_file) or snapshot.selected_file,
            attributes={"path": snapshot.selected_file, "language": snapshot.current_language},
            source="working_memory",
            ttl_seconds=1800,
        )

    def _resource(self, snapshot: ContextSnapshot) -> WorldEntity | None:
        resource = snapshot.active_resource or {}
        name = resource.get("name") or resource.get("path") or resource.get("url")
        if not name:
            return None
        resource_type = str(resource.get("type") or "document").lower()
        entity_type = "webpage" if resource_type in {"webpage", "url"} else "document"
        return self.store.upsert_entity(entity_type, os.path.basename(str(name)) or str(name), attributes=resource, source="resource", ttl_seconds=1800)

    def _notion_page(self, snapshot: ContextSnapshot) -> WorldEntity | None:
        if not snapshot.notion_page:
            return None
        return self.store.upsert_entity("notion_page", snapshot.notion_page, attributes={"provider": "notion"}, source="working_memory", ttl_seconds=1800)
