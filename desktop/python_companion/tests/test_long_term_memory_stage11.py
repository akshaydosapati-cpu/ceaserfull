from __future__ import annotations

from core.command_service import CommandService
from core.schemas import ActionResult, CommandRequest, IntentResult
from conversation.context_resolver import WorldContextResolver
from long_term_memory.memory_manager import LongTermMemoryManager
from long_term_memory.memory_store import LocalJsonMemoryStore


def make_request(text: str, *, user_id: str = "user-a", session_id: str = "stage11", context: dict | None = None) -> CommandRequest:
    return CommandRequest(
        request_id=f"req-{abs(hash((text, user_id, session_id))) % 999999}",
        user_id=user_id,
        session_id=session_id,
        source="typed",
        raw_text=text,
        normalized_text=text,
        context=context or {},
    )


def make_manager(tmp_path) -> LongTermMemoryManager:
    return LongTermMemoryManager(LocalJsonMemoryStore(tmp_path / "ltm.json"))


def test_explicit_project_memory_is_saved(tmp_path):
    manager = make_manager(tmp_path)
    result = manager.handle_command(make_request("Remember that CliniLocker is my healthcare project."))

    assert result is not None
    assert result.status == "completed"
    memories = manager.store.list("user-a")
    assert len(memories) == 1
    assert memories[0].type == "project"
    assert memories[0].structured_data["project"] == "CliniLocker"


def test_preference_persists_and_can_be_listed(tmp_path):
    manager = make_manager(tmp_path)
    manager.handle_command(make_request("Remember that I prefer brief answers."))

    result = manager.handle_command(make_request("What do you remember about me?"))

    assert result is not None
    assert result.status == "completed"
    assert "brief" in result.summary.lower()
    assert result.data["memories"][0]["type"] == "preference"


def test_forget_that_deletes_latest_memory(tmp_path):
    manager = make_manager(tmp_path)
    manager.handle_command(make_request("Remember that I prefer brief answers."))

    result = manager.handle_command(make_request("Forget that."))

    assert result is not None
    assert result.status == "completed"
    assert manager.store.list("user-a") == []


def test_secret_is_rejected(tmp_path):
    manager = make_manager(tmp_path)

    result = manager.handle_command(make_request("Remember that my API key is sk-testsecret123456."))

    assert result is not None
    assert result.status == "failed"
    assert result.error_code == "secret_rejected"
    assert manager.store.list("user-a") == []


def test_sensitive_generic_memory_requires_confirmation(tmp_path):
    manager = make_manager(tmp_path)

    result = manager.handle_command(make_request("Remember that my medical diagnosis is private."))

    assert result is not None
    assert result.status == "needs_confirmation"
    assert result.data["pending_memory_confirmation"]
    assert manager.store.list("user-a") == []


def test_session_memory_disable_blocks_new_memory(tmp_path):
    manager = make_manager(tmp_path)
    manager.handle_command(make_request("Do not remember this session.", session_id="private-session"))

    result = manager.handle_command(make_request("Remember that Turisst is my travel project.", session_id="private-session"))

    assert result is not None
    assert result.status == "failed"
    assert result.error_code == "session_memory_disabled"
    assert manager.retrieve(make_request("What about Turisst?", session_id="private-session"))["memories"] == []


def test_duplicate_memory_merges_instead_of_duplicating(tmp_path):
    manager = make_manager(tmp_path)
    first = manager.handle_command(make_request("Remember that CliniLocker is my healthcare project."))
    second = manager.handle_command(make_request("Remember that CliniLocker is my healthcare project."))

    assert first is not None and second is not None
    assert len(manager.store.list("user-a")) == 1
    assert second.data["memories_created"][0]["id"] == first.data["memories_created"][0]["id"]


def test_user_isolation(tmp_path):
    manager = make_manager(tmp_path)
    manager.handle_command(make_request("Remember that CliniLocker is my healthcare project.", user_id="user-a"))

    other = manager.retrieve(make_request("What is CliniLocker?", user_id="user-b"))

    assert other["memories"] == []


def test_retrieval_is_relevant(tmp_path):
    manager = make_manager(tmp_path)
    manager.handle_command(make_request("Remember that CliniLocker is my healthcare project."))
    manager.handle_command(make_request("Remember that Turisst is my travel project."))

    result = manager.retrieve(make_request("Tell me about healthcare work."))

    assert result["memories"]
    assert "CliniLocker" in result["memories"][0]["content"]


def test_current_context_remains_primary_over_stale_memory(tmp_path):
    manager = make_manager(tmp_path)
    manager.handle_command(make_request("Remember that CliniLocker is my healthcare project."))
    resolver = WorldContextResolver(long_term_memory=manager)

    context = resolver.resolve(make_request("Summarize this project.", context={"active_project": "CEASER"}))

    assert context["working_memory"]["current_project"] == "CEASER"
    assert context["long_term_memory"]["memories"]


def test_ordinary_desktop_command_does_not_create_memory(tmp_path):
    manager = make_manager(tmp_path)
    request = make_request("Open Chrome.")
    intent = IntentResult(intent="open_application", capability="desktop.open_application", confidence=0.9, route="desktop")
    result = ActionResult(status="completed", capability="desktop.open_application", summary="Opened Chrome.", verified=True)

    delta = manager.after_result(request, intent, result)

    assert delta["memories_created"] == []
    assert manager.store.list("user-a") == []


def test_command_service_intercepts_memory_before_legacy_handler(tmp_path):
    called = {"legacy": False}

    def legacy_handler(_text: str):
        called["legacy"] = True
        return {"status": "completed", "message": "legacy"}

    service = CommandService(legacy_handler, context_resolver=WorldContextResolver())
    manager = make_manager(tmp_path)
    service.long_term_memory = manager
    service.context_resolver.long_term_memory = manager

    result = service.execute(make_request("Remember that CliniLocker is my healthcare project."))

    assert result.status == "completed"
    assert result.capability == "memory.remember"
    assert called["legacy"] is False
