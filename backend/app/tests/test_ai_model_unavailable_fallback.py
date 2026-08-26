from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.core.config.settings import Settings, settings
from app.intelligence.ai.ai_provider_service import ai_provider_service
from app.intelligence.ai.errors import AIServiceUnavailableError, allows_provider_fallback
from app.intelligence.ai.sync import stream_text


class FailingStreamProvider:
    async def stream(self, **_kwargs):
        raise AIServiceUnavailableError(
            "model removed",
            retryable=False,
            provider="groq",
            category="model_unavailable",
        )
        yield ""  # pragma: no cover


class SuccessfulStreamProvider:
    async def stream(self, **_kwargs):
        yield "fallback response"


def selection(provider: str, model_id: str):
    return SimpleNamespace(
        model=SimpleNamespace(
            provider_id=provider,
            model_id=model_id,
            provider_model_name=model_id,
        )
    )


def test_stream_falls_back_when_selected_model_is_unavailable(monkeypatch):
    attempts = [
        (selection("groq", "groq-primary"), FailingStreamProvider()),
        (selection("openai", "openai-primary"), SuccessfulStreamProvider()),
    ]
    monkeypatch.setattr(settings, "llm_max_fallbacks", 1)
    monkeypatch.setattr(ai_provider_service.llm, "model_candidates", lambda *_args, **_kwargs: attempts)
    monkeypatch.setattr(ai_provider_service.llm.router, "record_failure", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ai_provider_service.llm.router, "record_success", lambda *_args, **_kwargs: None)

    async def collect():
        trace = {"request_id": "fallback-test"}
        chunks = [chunk async for chunk in stream_text(instructions="safe", input_text="hello", trace=trace)]
        return "".join(chunks), trace

    text, trace = asyncio.run(collect())

    assert text == "fallback response"
    assert trace["provider"] == "openai"
    assert trace["fallback_used"] is True
    assert trace["fallback_from"] == "groq"


def test_only_safe_provider_failures_allow_fallback():
    unavailable = AIServiceUnavailableError(category="model_unavailable", retryable=False)
    authentication = AIServiceUnavailableError(category="authentication", retryable=False)

    assert allows_provider_fallback(unavailable) is True
    assert allows_provider_fallback(authentication) is False


def test_retired_groq_model_is_migrated_without_overriding_current_models():
    retired = Settings(_env_file=None, GROQ_MODEL="llama-3.3-70b-versatile")
    current = Settings(_env_file=None, GROQ_MODEL="openai/gpt-oss-120b")

    assert retired.groq_model == "openai/gpt-oss-20b"
    assert current.groq_model == "openai/gpt-oss-120b"
