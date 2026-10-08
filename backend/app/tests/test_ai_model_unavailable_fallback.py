from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from app.core.config.settings import Settings, settings
from app.intelligence.ai.ai_provider_service import ai_provider_service
from app.intelligence.ai.errors import AIServiceUnavailableError, allows_provider_fallback
from app.intelligence.ai.sync import generate_text_sync, stream_text
from app.intelligence.ai.model_router.registry import configured_models


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


class SlowGenerateProvider:
    async def generate(self, **_kwargs):
        await asyncio.sleep(0.05)
        return "too late"


class SuccessfulGenerateProvider:
    async def generate(self, **_kwargs):
        return "fallback response"


class EmptyGenerateProvider:
    async def generate(self, **_kwargs):
        return "   "


class EmptyStreamProvider:
    async def stream(self, **_kwargs):
        if False:
            yield ""


class LoopRecordingProvider:
    def __init__(self):
        self.loop_ids = []

    async def generate(self, **_kwargs):
        self.loop_ids.append(id(asyncio.get_running_loop()))
        await asyncio.sleep(0.005)
        return "stable response"


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


def test_sync_generation_uses_bounded_timeout_then_falls_back(monkeypatch):
    attempts = [
        (selection("groq", "groq-primary"), SlowGenerateProvider()),
        (selection("openai", "openai-primary"), SuccessfulGenerateProvider()),
    ]
    monkeypatch.setattr(settings, "llm_max_fallbacks", 1)
    monkeypatch.setattr(ai_provider_service.llm, "model_candidates", lambda *_args, **_kwargs: attempts)
    monkeypatch.setattr(ai_provider_service.llm.router, "record_failure", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ai_provider_service.llm.router, "record_success", lambda *_args, **_kwargs: None)

    trace = {}
    text = generate_text_sync(
        instructions="safe",
        input_text="hello",
        attempt_timeout_seconds=0.01,
        overall_timeout_seconds=0.1,
        trace=trace,
    )

    assert text == "fallback response"
    assert trace["provider"] == "openai"
    assert trace["fallback_used"] is True
    assert trace["failed_attempts"][0]["category"] == "timeout"


def test_sync_empty_output_falls_back_and_final_success_is_canonical(monkeypatch):
    attempts = [
        (selection("groq", "groq-primary"), EmptyGenerateProvider()),
        (selection("gemini", "gemini-primary"), SuccessfulGenerateProvider()),
    ]
    monkeypatch.setattr(settings, "llm_max_fallbacks", 1)
    monkeypatch.setattr(ai_provider_service.llm, "model_candidates", lambda *_args, **_kwargs: attempts)
    monkeypatch.setattr(ai_provider_service.llm.router, "record_failure", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ai_provider_service.llm.router, "record_success", lambda *_args, **_kwargs: None)

    trace = {"request_id": "empty-fallback"}
    text = generate_text_sync(instructions="safe", input_text="hello", trace=trace)

    assert text == "fallback response"
    assert trace["failed_attempts"][0]["category"] == "empty_output"
    assert trace["final_provider"] == "gemini"
    assert trace["final_status"] == "success"
    assert trace["output_chars"] == len(text)


def test_empty_stream_falls_back_to_usable_stream(monkeypatch):
    attempts = [
        (selection("groq", "groq-primary"), EmptyStreamProvider()),
        (selection("gemini", "gemini-primary"), SuccessfulStreamProvider()),
    ]
    monkeypatch.setattr(settings, "llm_max_fallbacks", 1)
    monkeypatch.setattr(ai_provider_service.llm, "model_candidates", lambda *_args, **_kwargs: attempts)
    monkeypatch.setattr(ai_provider_service.llm.router, "record_failure", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ai_provider_service.llm.router, "record_success", lambda *_args, **_kwargs: None)

    async def collect():
        trace = {"request_id": "empty-stream"}
        text = "".join([chunk async for chunk in stream_text(instructions="safe", input_text="hello", trace=trace)])
        return text, trace

    text, trace = asyncio.run(collect())
    assert text == "fallback response"
    assert trace["failed_attempts"][0]["category"] == "empty_output"
    assert trace["final_provider"] == "gemini"
    assert trace["final_status"] == "success"


def test_sync_provider_loop_is_stable_across_sequential_and_concurrent_requests(monkeypatch):
    provider = LoopRecordingProvider()
    attempts = [(selection("groq", "groq-primary"), provider)]
    monkeypatch.setattr(settings, "llm_max_fallbacks", 0)
    monkeypatch.setattr(ai_provider_service.llm, "model_candidates", lambda *_args, **_kwargs: attempts)
    monkeypatch.setattr(ai_provider_service.llm.router, "record_failure", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ai_provider_service.llm.router, "record_success", lambda *_args, **_kwargs: None)

    assert generate_text_sync(instructions="safe", input_text="one") == "stable response"
    assert generate_text_sync(instructions="safe", input_text="two") == "stable response"
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(
            lambda value: generate_text_sync(instructions="safe", input_text=value),
            ("three", "four", "five"),
        ))

    assert results == ["stable response"] * 3
    assert len(set(provider.loop_ids)) == 1


def test_retired_groq_model_is_migrated_without_overriding_current_models():
    retired = Settings(_env_file=None, GROQ_MODEL="llama-3.3-70b-versatile")
    current = Settings(_env_file=None, GROQ_MODEL="openai/gpt-oss-120b")

    assert retired.groq_model == "openai/gpt-oss-20b"
    assert current.groq_model == "openai/gpt-oss-120b"


def test_unsupported_huggingface_model_is_excluded_from_configured_pool(monkeypatch):
    monkeypatch.setattr(
        settings,
        "huggingface_coding_models_raw",
        "deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct,Qwen/Qwen2.5-Coder-7B-Instruct",
    )

    provider_models = [model.provider_model_name.lower() for model in configured_models() if model.available]
    assert "deepseek-ai/deepseek-coder-v2-lite-instruct" not in provider_models
    assert "qwen/qwen2.5-coder-7b-instruct" in provider_models
