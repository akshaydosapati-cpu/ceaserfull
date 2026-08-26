from core.command_service import CommandService
from core.schemas import CommandRequest
from conversation.context_resolver import WorldContextResolver
from working_memory.working_memory import WorkingMemoryManager


def make_request(text, context=None, session="wm"):
    return CommandRequest(
        request_id=f"req_{abs(hash((text, session))) % 100000}",
        user_id="user-1",
        session_id=session,
        source="typed",
        raw_text=text,
        normalized_text=text,
        context=context or {},
    )


def test_open_vs_code_updates_desktop_and_project_context():
    manager = WorkingMemoryManager()
    resolver = WorldContextResolver(working_memory=manager)
    context = resolver.resolve(
        make_request(
            "open VS Code",
            {
                "activeWindow": {
                    "process": "Code.exe",
                    "title": "ceaser - Visual Studio Code",
                },
                "current_folder": "C:/work/ceaser",
                "selected_file": "C:/work/ceaser/desktop/src/main.js",
            },
        )
    )
    snapshot = context["working_memory"]
    assert snapshot["active_app"] == "Code.exe"
    assert snapshot["current_folder"] == "C:/work/ceaser"
    assert snapshot["selected_file"].endswith("main.js")
    assert snapshot["current_editor"] == "VS Code"
    assert snapshot["repository"] == "ceaser"


def test_open_pdf_changes_current_resource_and_explain_this_resolves_it():
    manager = WorkingMemoryManager()
    resolver = WorldContextResolver(working_memory=manager)
    resolver.resolve(
        make_request(
            "open the offer letter",
            {"active_resource": {"type": "pdf", "name": "OfferLetter.pdf", "path": "C:/docs/OfferLetter.pdf"}},
        )
    )
    context = resolver.resolve(make_request("explain this"))
    resolved = context["references"]["resolved_reference"]["target"]
    assert resolved["kind"] == "resource"
    assert resolved["type"] == "pdf"
    assert resolved["name"] == "OfferLetter.pdf"


def test_github_repository_result_updates_integration_memory():
    seen = []

    def handler(text):
        seen.append(text)
        return {"status": "completed", "message": "Repository ready", "repository": "CliniLocker", "verified": True}

    service = CommandService(handler, context_resolver=WorldContextResolver())
    result = service.execute(make_request("show GitHub repo CliniLocker", session="repo"))
    assert result.capability == "github.list_repositories"

    context = service.context_resolver.resolve(make_request("show commits from it", session="repo"))
    snapshot = context["working_memory"]
    assert snapshot["active_integration"] == "github"
    assert snapshot["github_repository"] == "CliniLocker"
    assert context["references"]["resolved_reference"]["repository"] == "CliniLocker"


def test_continue_uses_previous_response_from_working_memory():
    def handler(text):
        return {"status": "completed", "message": f"Answered: {text}", "verified": True}

    service = CommandService(handler, context_resolver=WorldContextResolver())
    service.execute(make_request("explain Arjuna's skills", session="conv"))
    result = service.execute(make_request("continue", session="conv"))
    assert result.capability == "ai.answer"
    assert result.evidence["cortex_reason"] == "conversation_follow_up"
    assert result.evidence["context_rewritten"] is True


def test_active_app_changes_update_desktop_snapshot():
    resolver = WorldContextResolver(working_memory=WorkingMemoryManager())
    first = resolver.resolve(make_request("what is open", {"activeWindow": {"process": "chrome.exe", "title": "Chrome"}}))
    second = resolver.resolve(make_request("what is open", {"activeWindow": {"process": "WINWORD.EXE", "title": "Document1 - Word"}}))
    assert first["working_memory"]["active_app"] == "chrome.exe"
    assert second["working_memory"]["active_app"] == "WINWORD.EXE"
