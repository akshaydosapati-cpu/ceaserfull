import asyncio
import json

from app.core.config.settings import settings
from app.intelligence.ai.llm.gemini_provider import GeminiFallbackProvider


class _Response:
    status_code = 200

    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self):
        for payload in (
            {"candidates": [{"content": {"parts": [{"text": "First "}]}}]},
            {"candidates": [{"content": {"parts": [{"text": "second."}]}, "finishReason": "STOP"}]},
        ):
            yield f"data: {json.dumps(payload)}"


class _StreamContext:
    async def __aenter__(self):
        return _Response()

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _Client:
    is_closed = False

    def stream(self, *args, **kwargs):
        return _StreamContext()


def test_gemini_stream_emits_incremental_sse_chunks(monkeypatch) -> None:
    async def verify() -> None:
        monkeypatch.setattr(settings, "gemini_api_key", "test-key")
        provider = GeminiFallbackProvider()
        provider._http_clients = {asyncio.get_running_loop(): _Client()}
        trace = {}

        chunks = [chunk async for chunk in provider.stream(instructions="Answer.", input_text="Hello", trace=trace)]

        assert chunks == ["First ", "second."]
        assert "".join(chunks) == "First second."
        assert trace["stream_opened"] is True
        assert trace["stream_completed"] is True
        assert trace["finish_reason"] == "stop"

    asyncio.run(verify())
