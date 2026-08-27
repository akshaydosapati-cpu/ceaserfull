import asyncio

from app.api.ceaser import routes


def test_guest_demo_uses_bounded_context_and_continues_length_stop(monkeypatch) -> None:
    calls: list[dict] = []

    async def fake_stream_text(**kwargs):
        calls.append(kwargs)
        kwargs["trace"]["finish_reason"] = "length" if len(calls) == 1 else "stop"
        yield "First part. " if len(calls) == 1 else "Finished."

    monkeypatch.setattr(routes, "stream_text", fake_stream_text)
    payload = routes.CeaserDemoRequest(
        message="tell me more",
        recent_turns=[
            routes.CeaserDemoTurn(role="user", content=f"question {index}")
            if index % 2 == 0
            else routes.CeaserDemoTurn(role="assistant", content=f"answer {index}")
            for index in range(8)
        ],
    )

    result = asyncio.run(routes.ceaser_public_demo(payload))

    assert result.response == "First part. Finished."
    assert result.continuation_count == 1
    assert len(calls) == 2
    assert "question 0" not in calls[0]["input_text"]
    assert "question 2" in calls[0]["input_text"]
    assert "tell me more" in calls[0]["input_text"]
    assert calls[0]["model_request"].needs_streaming is True
