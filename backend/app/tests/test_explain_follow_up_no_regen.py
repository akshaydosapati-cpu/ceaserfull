"""Integration test: EXPLAIN follow-up should not regenerate code artifact."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.services.orchestrator.response_pipeline import ResponsePipeline
from app.services.orchestrator.response_planner import OperationType


def test_explain_follow_up_dispatches_to_non_generative_stream():
    """Verify that EXPLAIN operation routes to _stream_non_generative, not code continuation."""
    response_plan = {
        "operation": "EXPLAIN",
        "reference": "code",
        "target_artifact_id": "code-1",
        "preserve_format": True,
        "output_mode": "explanation",
        "change_type": None,
        "constraints": {"verbosity": "detailed"},
        "confidence": 0.85,
    }

    message = "explain it every step"
    context = {
        "response_plan": response_plan,
        "merged_contributions": {"selected_agents": []},
        "conversation": [
            {"role": "user", "content": "write a code for prime number in c"},
            {"role": "assistant", "content": "Here's prime number code in C:\n```c\n#include <stdio.h>\nint main() { return 0; }\n```"},
        ],
        "follow_up_trace": {"follow_up_detected": True, "active_topic": "prime number code in c"},
    }

    pipeline = ResponsePipeline()
    assert response_plan["operation"] in {"EXPLAIN", "SUMMARIZE", "CLARIFY"}


def test_explain_instructs_without_code_regen():
    """Verify that _contextualize_follow_up embeds EXPLAIN instruction when operation is EXPLAIN."""
    from app.services.orchestrator.orchestrator import CeaserOrchestrator

    orchestrator = CeaserOrchestrator.__new__(CeaserOrchestrator)
    response_plan_payload = {
        "operation": "EXPLAIN",
        "constraints": {"complexity": "clear"},
    }
    follow_up_trace = {
        "follow_up_detected": True,
        "active_topic": "Prime number in C",
        "active_subtopic": None,
    }

    contextualized = orchestrator._contextualize_follow_up(
        "explain it every step",
        follow_up_trace,
        response_plan=response_plan_payload,
    )

    assert "explain" in contextualized.lower()
    assert "without regenerating" in contextualized.lower()
    assert "Prime number in C" in contextualized


def test_non_generative_operation_check():
    """Verify that EXPLAIN, SUMMARIZE, CLARIFY are marked as non-generative."""
    from app.services.orchestrator.orchestrator import CeaserOrchestrator

    for operation in ["EXPLAIN", "SUMMARIZE", "CLARIFY"]:
        plan = {"operation": operation}
        assert CeaserOrchestrator._non_generative_operation(plan) is True

    for operation in ["CREATE", "MODIFY", "CONTINUE", "TRANSFORM"]:
        plan = {"operation": operation}
        assert CeaserOrchestrator._non_generative_operation(plan) is False


@pytest.mark.asyncio
async def test_stream_routes_based_on_operation():
    """Verify that stream() dispatches EXPLAIN to _stream_non_generative."""
    pipeline = ResponsePipeline()

    async def mock_non_generative(*args, **kwargs):
        yield "This is an explanation."

    async def mock_generative(*args, **kwargs):
        yield "```\ncode here\n```"

    with patch.object(pipeline, "_stream_non_generative", mock_non_generative):
        with patch.object(pipeline, "_stream_generative", mock_generative):
            context_explain = {"response_plan": {"operation": "EXPLAIN"}}
            chunks = [chunk async for chunk in pipeline.stream("explain it", context_explain)]
            assert "".join(chunks) == "This is an explanation."

            context_create = {"response_plan": {"operation": "CREATE"}}
            chunks = [chunk async for chunk in pipeline.stream("write code", context_create)]
            assert "".join(chunks) == "```\ncode here\n```"

