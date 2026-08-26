import time

from core.command_service import CommandService
from core.schemas import ActionResult, CommandRequest, IntentResult
from conversation.context_resolver import WorldContextResolver
from world_model.graph_store import GraphStore
from world_model.world_model import SemanticWorldModel


def make_request(text, context=None, session="world"):
    return CommandRequest(
        request_id=f"req_{abs(hash((text, session))) % 100000}",
        user_id="user-1",
        session_id=session,
        source="typed",
        raw_text=text,
        normalized_text=text,
        context=context or {},
    )


def ceaser_context():
    return {
        "active_project": "CEASER",
        "active_repository": "CEASER",
        "selected_file": "C:/work/CEASER/python_companion/core/command_service.py",
        "current_folder": "C:/work/CEASER",
        "activeWindow": {"process": "Code.exe", "title": "CEASER - Visual Studio Code"},
    }


def test_project_graph_creation_without_duplicates():
    world = SemanticWorldModel()
    resolver = WorldContextResolver(world_model=world)
    request = make_request("show current project", ceaser_context())
    resolver.resolve(request)
    resolver.resolve(request)

    projects = [entity for entity in world.store.entities.values() if entity.type == "project"]
    repos = [entity for entity in world.store.entities.values() if entity.type == "repository"]
    files = [entity for entity in world.store.entities.values() if entity.type == "file"]

    assert len(projects) == 1
    assert len(repos) == 1
    assert len(files) == 1
    assert projects[0].name == "CEASER"
    assert repos[0].name == "CEASER"
    assert files[0].name == "command_service.py"
    assert any(rel.source_id == repos[0].id and rel.target_id == projects[0].id and rel.type == "belongs_to" for rel in world.store.relationships.values())
    assert any(rel.source_id == files[0].id and rel.target_id == repos[0].id and rel.type == "belongs_to" for rel in world.store.relationships.values())


def test_project_reference_resolution_routes_github_with_repository_evidence():
    def handler(text):
        return {"status": "completed", "message": "commits", "verified": True}

    service = CommandService(handler, context_resolver=WorldContextResolver())
    result = service.execute(make_request("show commits for this project", ceaser_context(), session="github-project"))

    assert result.capability == "github.list_commits"
    assert result.evidence["cortex_destination"] == "integration"
    assert result.evidence["cortex_signals"]["world_resolution_reason"] in {"current_project", "explicit_name"}
    assert result.evidence["cortex_signals"]["world_entities_used"]


def test_notion_page_connected_to_project():
    world = SemanticWorldModel()
    resolver = WorldContextResolver(world_model=world)
    context = {
        "active_project": "CliniLocker",
        "active_repository": "CliniLocker",
        "activeWindow": {"process": "Code.exe", "title": "CliniLocker - Visual Studio Code"},
    }
    resolver.resolve(make_request("open notion roadmap", context, session="notion"))
    resolver.record_turn(
        make_request("open notion roadmap", context, session="notion"),
        IntentResult(intent="notion_get_page", capability="notion.get_page", confidence=0.9, route="integration"),
        ActionResult(status="completed", capability="notion.get_page", summary="Loaded roadmap", data={"notion_page": "Project Roadmap"}, verified=True),
    )
    resolver.resolve(make_request("show project notes", {"active_project": "CliniLocker", "notion_page": "Project Roadmap"}, session="notion"))
    project = world.queries.get_current_project("notion")
    pages = world.queries.get_notion_pages_for_project(project.id)
    assert project.name == "CliniLocker"
    assert any(page.name == "Project Roadmap" for page in pages)


def test_ambiguity_returns_candidates_without_random_selection():
    world = SemanticWorldModel()
    world.store.upsert_entity("project", "CEASER", source="test")
    world.store.upsert_entity("project", "CliniLocker", source="test")
    resolution = world.entity_resolver.resolve_project("open my project", session_id="missing")
    assert resolution.entity is None
    assert resolution.ambiguous is True
    assert {candidate.name for candidate in resolution.ambiguity_candidates} == {"CEASER", "CliniLocker"}


def test_verified_open_file_updates_active_resource():
    world = SemanticWorldModel()
    resolver = WorldContextResolver(world_model=world)
    request = make_request("open roadmap", ceaser_context(), session="verified")
    resolver.resolve(request)
    resolver.record_turn(
        request,
        IntentResult(intent="open_file", capability="desktop.open_file", confidence=0.9, route="desktop"),
        ActionResult(status="completed", capability="desktop.open_file", summary="Opened roadmap", data={"path": "C:/work/CEASER/roadmap.pdf"}, verified=True),
    )
    active = world.queries.get_active_resource("verified")
    assert active is not None
    assert active.name == "roadmap.pdf"


def test_failed_action_does_not_update_active_relationships():
    world = SemanticWorldModel()
    resolver = WorldContextResolver(world_model=world)
    request = make_request("open missing file", ceaser_context(), session="failed")
    resolver.resolve(request)
    before = len(world.store.relationships)
    resolver.record_turn(
        request,
        IntentResult(intent="open_file", capability="desktop.open_file", confidence=0.9, route="desktop"),
        ActionResult(status="failed", capability="desktop.open_file", summary="Missing file", data={"path": "C:/secret/missing.pdf"}, verified=False),
    )
    assert len(world.store.relationships) == before
    assert all("missing.pdf" not in entity.name for entity in world.store.entities.values())


def test_secret_fields_are_excluded_from_entity_attributes():
    store = GraphStore()
    entity = store.upsert_entity(
        "integration",
        "GitHub",
        attributes={"access_token": "secret", "api_key": "secret", "account": "Akshay", "count": 9},
        source="test",
    )
    assert "access_token" not in entity.attributes
    assert "api_key" not in entity.attributes
    assert entity.attributes["account"] == "Akshay"


def test_expired_entities_and_relationships_are_removed():
    store = GraphStore()
    source = store.upsert_entity("project", "Old", source="test", ttl_seconds=1)
    target = store.upsert_entity("repository", "OldRepo", source="test", ttl_seconds=10)
    store.upsert_relationship(target.id, "belongs_to", source.id, source="test", ttl_seconds=10)
    source.expires_at = time.time() - 1
    store.expire()
    assert source.id not in store.entities
    assert not store.relationships
