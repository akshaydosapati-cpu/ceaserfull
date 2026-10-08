"""Regression test: _stream_generative() must initialize prompt_started."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.services.orchestrator.response_pipeline import ResponsePipeline


@pytest.mark.asyncio
async def test_stream_generative_traces_prompt_build_ms():
    """Verify that _stream_generative() initializes prompt_started for trace tracking.

    Regression: NameError: name 'prompt_started' is not defined
    This test exercises the actual _stream_generative() path with trace enabled.
    """
    pipeline = ResponsePipeline()

    message = "Write a Python function for factorial."
    context = {
        "response_plan": {"operation": "CREATE"},
        "merged_contributions": {"selected_agents": []},
        "conversation": [],
    }
    trace = {}

    # Mock the underlying stream_text to avoid LLM call
    async def mock_stream_text(*args, **kwargs):
        yield "def factorial(n):\n"
        yield "    return n * factorial(n-1) if n > 0 else 1\n"

    with patch("app.services.orchestrator.response_pipeline.stream_text", mock_stream_text):
        chunks = []
        async for chunk in pipeline._stream_generative(message, context, trace):
            chunks.append(chunk)

    # Verify:
    # 1. Stream completed without NameError
    assert chunks, "Stream should emit at least one chunk"

    # 2. Trace was populated (proves prompt_started was initialized)
    assert "prompt_build_ms" in trace, "trace['prompt_build_ms'] must be set"
    assert isinstance(trace["prompt_build_ms"], (int, float)), "prompt_build_ms must be a number"
    assert trace["prompt_build_ms"] >= 0, "prompt_build_ms must be non-negative"

    # 3. Other trace fields were populated
    assert "context_tokens" in trace
    assert "prompt_tokens" in trace
    assert "max_output_tokens" in trace


@pytest.mark.asyncio
async def test_stream_generative_vs_non_generative_trace_consistency():
    """Verify both generative and non-generative paths handle trace consistently."""
    pipeline = ResponsePipeline()

    message = "Test message"
    context = {"response_plan": {}, "conversation": []}

    async def mock_stream_text(*args, **kwargs):
        yield "test output"

    with patch("app.services.orchestrator.response_pipeline.stream_text", mock_stream_text):
        # Test generative path
        trace_generative = {}
        async for _ in pipeline._stream_generative(message, context, trace_generative):
            pass

        # Test non-generative path
        trace_non_generative = {}
        async for _ in pipeline._stream_non_generative(message, context, trace_non_generative):
            pass

    # Both should have prompt_build_ms
    assert "prompt_build_ms" in trace_generative
    assert "prompt_build_ms" in trace_non_generative
