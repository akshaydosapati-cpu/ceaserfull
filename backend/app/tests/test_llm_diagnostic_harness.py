import pytest

from app.tests.test_ai_model_unavailable_fallback import (
    selection, EmptyGenerateProvider, SuccessfulGenerateProvider,
)
from app.core.config.settings import settings
from app.intelligence.ai.ai_provider_service import ai_provider_service
from app.intelligence.ai.sync import generate_text_sync
from app.intelligence.ai.llm.http_errors import ai_error_from_status
from scripts.llm_provider_benchmark import summary


@pytest.mark.parametrize("failures", [0, 2])
def test_fallback_attempts_stop_at_success(monkeypatch, failures):
    calls = []

    class Empty(EmptyGenerateProvider):
        async def generate(self, **kwargs):
            calls.append(kwargs["model"])
            return await super().generate(**kwargs)

    class Success(SuccessfulGenerateProvider):
        async def generate(self, **kwargs):
            calls.append(kwargs["model"])
            return await super().generate(**kwargs)

    attempts = [(selection(f"failed-{i}", f"failed-{i}"), Empty()) for i in range(failures)]
    attempts += [(selection("winner", "winner"), Success()), (selection("unused", "unused"), Success())]
    monkeypatch.setattr(settings, "llm_max_fallbacks", 3)
    monkeypatch.setattr(ai_provider_service.llm, "model_candidates", lambda *a, **k: attempts)
    monkeypatch.setattr(ai_provider_service.llm.router, "record_failure", lambda *a, **k: None)
    monkeypatch.setattr(ai_provider_service.llm.router, "record_success", lambda *a, **k: None)
    trace = {}
    assert generate_text_sync(instructions="test", input_text="test", trace=trace) == "fallback response"
    assert trace["final_status"] == "success"
    assert trace["final_provider"] == "winner"
    assert trace["fallback_used"] is (failures > 0)
    assert len(trace.get("failed_attempts", [])) == failures
    assert calls == [f"failed-{i}" for i in range(failures)] + ["winner"]


@pytest.mark.parametrize("status,category,retryable", [
    (401, "authentication", False), (400, "invalid_request", False),
    (404, "model_unavailable", False), (429, "rate_limit", True),
    (504, "timeout", True), (503, "generation", True),
])
def test_http_categories(status, category, retryable):
    error = ai_error_from_status(status_code=status, body="", provider="test")
    assert error.category == category
    assert error.retryable == retryable


def test_percentiles_separate_missing_samples():
    assert summary([None]) is None
    assert summary([1, 2, 3, 4, 5])["p95"] == 4.8
