from core.command_service import CommandService
from core.schemas import CommandRequest


def make_service(seen):
    def handler(text):
        seen.append(text)
        return {"status": "completed", "message": f"ok:{text[:60]}", "verified": True}

    return CommandService(handler)


def execute(service, text, session="s"):
    return service.execute(
        CommandRequest(
            request_id=f"req_{len(text)}",
            session_id=session,
            source="typed",
            raw_text=text,
            normalized_text=text,
        )
    )


def test_cortex_routes_desktop_command():
    seen = []
    result = execute(make_service(seen), "open Chrome")
    assert result.capability == "app.open"
    assert result.evidence["cortex_destination"] == "desktop"
    assert result.evidence["cortex_reason"] == "desktop_signal"


def test_cortex_routes_github_command():
    seen = []
    result = execute(make_service(seen), "show commits of CliniLocker repository")
    assert result.capability == "github.list_commits"
    assert result.evidence["cortex_destination"] == "integration"
    assert result.evidence["cortex_signals"]["github"] is True


def test_cortex_routes_notion_command():
    seen = []
    result = execute(make_service(seen), "show my Notion tasks")
    assert result.capability == "notion.list_tasks"
    assert result.evidence["cortex_destination"] == "integration"
    assert result.evidence["cortex_signals"]["notion"] is True


def test_cortex_routes_workflow_without_planner_implementation():
    seen = []
    result = execute(make_service(seen), "prepare me for my CliniLocker viva")
    assert result.capability == "workflow.plan"
    assert result.evidence["cortex_destination"] == "workflow"
    assert result.evidence["cortex_reason"] == "workflow_signal"


def test_cortex_routes_backend_ai():
    seen = []
    result = execute(make_service(seen), "explain quantum computing")
    assert result.capability == "ai.answer"
    assert result.evidence["cortex_destination"] == "backend_ai"


def test_cortex_routes_follow_up_using_session_context():
    seen = []
    service = make_service(seen)
    execute(service, "explain Ramayana", session="follow")
    result = execute(service, "continue", session="follow")
    assert result.capability == "ai.answer"
    assert result.evidence["cortex_reason"] == "conversation_follow_up"
    assert result.evidence["context_rewritten"] is True


def test_cortex_unsupported_stays_clean_failure():
    seen = []
    result = execute(make_service(seen), "xyzabc")
    assert result.status == "failed"
    assert result.error_code == "unsupported_request"
    assert result.evidence["cortex_destination"] == "unsupported"
