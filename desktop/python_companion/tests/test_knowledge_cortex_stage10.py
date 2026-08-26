from pathlib import Path

from capabilities.registry import build_default_registry
from core.command_service import CommandService
from core.schemas import CommandRequest
from knowledge.knowledge_cortex import KnowledgeCortex
from knowledge.knowledge_loader import KnowledgeLoader
from knowledge.knowledge_store import KnowledgeStore
from knowledge.models import KnowledgeItem
from knowledge.trust_policy import TrustPolicy


def make_request(text, session="knowledge"):
    return CommandRequest(
        request_id=f"req_{abs(hash((text, session))) % 100000}",
        user_id="user-1",
        session_id=session,
        source="typed",
        raw_text=text,
        normalized_text=text,
    )


def test_architecture_query_returns_authoritative_desktop_brain_result():
    cortex = KnowledgeCortex(".", build_default_registry())
    cortex.load()
    result = cortex.query("What is Desktop Brain v2?")
    assert result.status == "completed"
    assert result.verified is True
    assert any("DESKTOP_BRAIN_V2.md" in source for source in result.evidence["sources"])


def test_capability_query_github_returns_capability_or_integration_result():
    service = CommandService(lambda text: {"status": "completed", "message": "legacy", "verified": True})
    result = service.execute(make_request("What can CEASER do with GitHub?"))
    assert result.capability == "knowledge.query"
    assert result.evidence["cortex_destination"] == "knowledge"
    assert "github" in result.summary.lower() or any("github" in str(match).lower() for match in result.data["matches"])


def test_safety_query_returns_confirmation_rule():
    service = CommandService(lambda text: {"status": "completed", "message": "legacy", "verified": True})
    result = service.execute(make_request("Which actions require confirmation?"))
    assert result.capability == "knowledge.query"
    assert "confirmation" in result.summary.lower()
    assert result.verified is True


def test_non_ceaser_query_routes_backend_ai_not_knowledge():
    service = CommandService(lambda text: {"status": "completed", "message": "ai", "verified": True})
    result = service.execute(make_request("Explain quantum computing."))
    assert result.capability == "ai.answer"
    assert result.evidence["cortex_destination"] == "backend_ai"


def test_duplicate_loading_creates_no_duplicates():
    cortex = KnowledgeCortex(".", build_default_registry())
    cortex.load()
    first_count = len(cortex.store.items)
    cortex.load()
    assert len(cortex.store.items) == first_count


def test_incremental_refresh_updates_changed_item_hash():
    store = KnowledgeStore()
    item = KnowledgeItem(id="doc:a", category="documentation", title="A", content="one", content_hash="one")
    store.upsert(item)
    updated = KnowledgeItem(id="doc:a", category="documentation", title="A", content="two", content_hash="two")
    _, changed = store.upsert(updated)
    assert changed is True
    assert store.by_id("doc:a").content_hash == "two"


def test_secret_like_content_is_rejected():
    policy = TrustPolicy()
    assert policy.is_safe_content("OPENAI_API_KEY=sk-secretvalue") is False


def test_authoritative_current_item_outranks_deprecated():
    cortex = KnowledgeCortex(".", build_default_registry())
    current = KnowledgeItem(id="current", category="faq", title="Notion confirmation", content="Notion writes require confirmation.", keywords=["notion", "confirmation"], trust_level="authoritative")
    old = KnowledgeItem(id="old", category="faq", title="Notion confirmation old", content="Deprecated old Notion confirmation.", keywords=["notion", "confirmation"], trust_level="deprecated")
    cortex.store.upsert(old)
    cortex.store.upsert(current)
    cortex.index.rebuild(cortex.store.all())
    result = cortex.query("Notion confirmation")
    assert result.data["matches"][0]["item"]["id"] == "current"


def test_missing_source_returns_visible_load_warning(tmp_path):
    cortex = KnowledgeCortex(tmp_path, build_default_registry())
    cortex.load()
    assert cortex.load_errors
    refresh = cortex.refresh()
    assert refresh.status == "partial"
    assert refresh.warnings


def test_no_fabrication_for_unsupported_product_feature():
    cortex = KnowledgeCortex(".", build_default_registry())
    cortex.load()
    result = cortex.query("Does CEASER support teleporting files with holograms?")
    assert result.status == "failed"
    assert result.error_code == "knowledge_not_found"


def test_simple_desktop_command_bypasses_knowledge():
    service = CommandService(lambda text: {"status": "completed", "message": "Chrome opened", "verified": True})
    result = service.execute(make_request("Open Chrome"))
    assert result.capability == "app.open"
    assert result.evidence["cortex_destination"] == "desktop"


def test_integration_action_bypasses_knowledge():
    service = CommandService(lambda text: {"status": "completed", "message": "commits", "verified": True})
    result = service.execute(make_request("Show GitHub commits"))
    assert result.capability == "github.list_commits"
    assert result.evidence["cortex_destination"] == "integration"
