from __future__ import annotations

from core.schemas import CommandRequest
from conversation.context_resolver import WorldContextResolver
from conversation.executive_cortex import ExecutiveCortex
from prediction.prediction_engine import PredictionEngine
from routing.intent_router import IntentRouter


def make_request(text: str = "summarize today's work", *, context: dict | None = None) -> CommandRequest:
    return CommandRequest(
        request_id=f"pred-{abs(hash(text)) % 999999}",
        user_id="user-a",
        session_id="stage14",
        source="typed",
        raw_text=text,
        normalized_text=text,
        context=context or {},
    )


def test_vscode_active_repo_prepares_git_status_and_commits():
    engine = PredictionEngine()
    request = make_request()
    context = engine.as_context(
        request,
        working_memory={"active_app": "Visual Studio Code", "current_repository": "CliniLocker"},
        world_model={},
        awareness={},
        experience={},
    )

    prediction = context["predictions"][0]
    preparation = context["preparation"]["git_activity:clinilocker"]

    assert prediction["likely_capability"] == "github.list_commits"
    assert prediction["safe_read_only"] is True
    assert preparation["status"] == "prepared"
    assert preparation["data"]["includes"] == ["git_status", "recent_commits"]
    assert preparation["data"]["read_only"] is True


def test_preparation_cache_reports_hit_and_latency_evidence():
    engine = PredictionEngine()
    request = make_request()
    payload = {
        "working_memory": {"active_app": "VS Code", "current_repository": "CEASER"},
        "world_model": {},
        "awareness": {},
        "experience": {},
    }

    first = engine.as_context(request, **payload)
    second = engine.as_context(request, **payload)

    first_prep = first["preparation"]["git_activity:ceaser"]
    second_prep = second["preparation"]["git_activity:ceaser"]
    assert first_prep["cache_hit"] is False
    assert second_prep["cache_hit"] is True
    assert second_prep["latency_ms"] >= 0
    assert "prepared_context_available" in second_prep["evidence"]


def test_repeated_github_summary_workflow_prepares_repository_activity():
    engine = PredictionEngine()
    context = engine.as_context(
        make_request(),
        working_memory={},
        world_model={},
        awareness={},
        experience={
            "repeated_workflows": [
                {
                    "label": "Summarize GitHub repository activity",
                    "count": 3,
                    "metadata": {"workflow_type": "github_activity_summary", "active_project": "CEASER"},
                }
            ]
        },
    )

    prediction = context["predictions"][0]
    preparation = context["preparation"]["repository_activity:ceaser"]
    assert prediction["likely_workflow"] == "github_activity_summary"
    assert preparation["data"]["includes"] == ["repository_summary", "recent_commits", "open_issues", "pull_requests"]


def test_repeated_notion_study_workflow_prepares_study_metadata():
    engine = PredictionEngine()
    context = engine.as_context(
        make_request(),
        working_memory={},
        world_model={"active_workspace": "Akshay Notion"},
        awareness={},
        experience={
            "repeated_workflows": [
                {
                    "label": "Review Notion study notes",
                    "count": 2,
                    "metadata": {"workflow_type": "notion_study_quiz"},
                }
            ]
        },
    )

    prediction = context["predictions"][0]
    preparation = context["preparation"]["notion_study_metadata:recent"]
    assert prediction["likely_workflow"] == "notion_study_review"
    assert preparation["data"]["provider"] == "notion"
    assert "study_page_metadata" in preparation["data"]["includes"]


def test_repeated_command_sequence_recommends_next_command_only():
    engine = PredictionEngine()
    context = engine.as_context(
        make_request("open chrome"),
        working_memory={},
        world_model={},
        awareness={},
        experience={"repeated_commands": [{"label": "open chrome", "count": 4}]},
    )

    prediction = context["predictions"][0]
    assert prediction["type"] == "next_command"
    assert prediction["likely_command"] == "open chrome"
    assert context["preparation"] == {}


def test_low_confidence_prediction_does_nothing():
    engine = PredictionEngine()
    context = engine.as_context(
        make_request("hello"),
        working_memory={"active_app": "Chrome"},
        world_model={},
        awareness={},
        experience={"repeated_commands": [{"label": "random command", "count": 1}]},
    )

    assert context["predictions"] == []
    assert context["preparation"] == {}
    assert context["summary"] == "no_prediction"


def test_context_resolver_exposes_prediction_context():
    engine = PredictionEngine()
    resolver = WorldContextResolver(prediction_engine=engine)
    request = make_request(
        "summarize repo",
        context={"foreground": {"process": "Code.exe", "title": "CEASER - Visual Studio Code"}, "current_project": "CEASER"},
    )

    context = resolver.resolve(request)

    assert "prediction" in context
    assert context["prediction"]["summary"] != "not_configured"


def test_executive_cortex_carries_prediction_as_optional_evidence_only():
    request = make_request("what is this project?")
    context = {
        "prediction": {
            "summary": "Prepare Git activity",
            "predictions": [{"label": "Prepare Git activity", "confidence": 0.82}],
        }
    }

    decision = ExecutiveCortex().route(request, context, IntentRouter())

    assert decision.signals["prediction_summary"] == "Prepare Git activity"
    assert decision.signals["prediction_evidence"][0]["label"] == "Prepare Git activity"
    assert decision.destination != "workflow"
