from pathlib import Path

from conversation.continuation_resolver import ConversationContinuationResolver


def test_self_contained_workflow_with_save_it_is_not_a_follow_up():
    resolver = ConversationContinuationResolver()

    resolved = resolver.resolve(
        "Prepare me for my CliniLocker viva and save it to Notion",
        session={},
        working={},
    )

    assert resolved["follow_up_detected"] is False
    assert resolved["resolved_reference"] is None


def test_short_follow_up_still_uses_the_immediate_previous_result():
    resolver = ConversationContinuationResolver()

    resolved = resolver.resolve(
        "summarize",
        session={"last_result": {"summary": "Assam flood response details."}},
        working={},
    )

    assert resolved["follow_up_detected"] is True
    assert resolved["continuation_kind"] == "summarize"
    assert resolved["resolved_reference"]["last_summary"] == "Assam flood response details."


def test_authoritative_runtime_does_not_silently_call_legacy_execution():
    desktop_root = Path(__file__).resolve().parents[2]
    server_source = (desktop_root / "python_companion" / "desktop_voice_server.py").read_text(encoding="utf-8")
    renderer_source = (desktop_root / "src" / "renderer" / "app.js").read_text(encoding="utf-8")

    execute_text_body = server_source.split("def execute_text(", 1)[1].split("def call_ceaser_backend_chat", 1)[0]
    execute_step_body = server_source.split("def execute_single_step(", 1)[1].split("def execute_text_legacy", 1)[0]
    run_command_body = renderer_source.split("async function runCommand(", 1)[1].split("async function handleFollowUpCommand", 1)[0]

    assert "execute_text_legacy(" not in execute_text_body
    assert "assistant.match_command(" not in execute_step_body
    assert ".classify(" not in run_command_body
    assert "compatibility fallback used" not in run_command_body
