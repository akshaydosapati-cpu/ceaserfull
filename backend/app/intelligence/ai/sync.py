from __future__ import annotations

import asyncio
import atexit
from concurrent.futures import TimeoutError as FutureTimeoutError
import logging
import re
import threading
from collections.abc import AsyncIterator
from time import perf_counter
from typing import Any

from app.core.config.settings import settings
from app.intelligence.ai.errors import AIServiceUnavailableError, allows_provider_fallback
from app.intelligence.ai.model_router import ModelRequest, request_for_chat

logger = logging.getLogger(__name__)


class _SyncAsyncRunner:
    """Keep sync provider calls on one event loop so pooled clients stay valid."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, name="ceaser-ai-sync", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run(self, coroutine, *, timeout: float | None = None):
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        try:
            return future.result(timeout=timeout)
        except FutureTimeoutError:
            future.cancel()
            raise

    def close(self) -> None:
        if not self._loop.is_running():
            return

        async def close_providers() -> None:
            from app.intelligence.ai.ai_provider_service import ai_provider_service

            await ai_provider_service.llm.aclose()

        try:
            self.run(close_providers(), timeout=5.0)
        except Exception:  # noqa: BLE001 - interpreter shutdown is best effort.
            logger.debug("AI sync runner provider cleanup did not complete.", exc_info=True)
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5.0)


_SYNC_ASYNC_RUNNER = _SyncAsyncRunner()
atexit.register(_SYNC_ASYNC_RUNNER.close)


def _usable_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def generate_text_sync(
    *,
    instructions: str,
    input_text: str,
    temperature: float | None = None,
    max_output_tokens: int | None = None,
    model_request: ModelRequest | None = None,
    attempt_timeout_seconds: float | None = None,
    overall_timeout_seconds: float | None = None,
    trace: dict[str, Any] | None = None,
) -> str:
    from app.intelligence.ai.ai_provider_service import ai_provider_service

    async def _generate() -> str:
        last_error: Exception | None = None
        request_started = perf_counter()
        request = model_request or request_for_chat(context_size_estimate=max(1, len(input_text) // 4))
        attempts = ai_provider_service.llm.model_candidates(request, max_count=max(1, settings.llm_max_fallbacks + 1))
        if not attempts:
            raise AIServiceUnavailableError("No LLM provider is configured.", retryable=False, category="configuration")
        for index, (selection, provider) in enumerate(attempts):
            provider_name = selection.model.provider_id
            started = perf_counter()
            timeout_seconds = attempt_timeout_seconds
            if overall_timeout_seconds is not None:
                remaining_seconds = overall_timeout_seconds - (perf_counter() - request_started)
                if remaining_seconds <= 0:
                    break
                timeout_seconds = min(timeout_seconds, remaining_seconds) if timeout_seconds is not None else remaining_seconds
            if trace is not None:
                trace.update(
                    {
                        "provider": provider_name,
                        "model": selection.model.model_id,
                        "fallback_used": index > 0,
                        "provider_attempt": index + 1,
                    }
                )
            logger.info(
                "AI provider attempt: request_id=%s attempt=%s provider=%s model=%s fallback_attempt=%s",
                (trace or {}).get("request_id"),
                index + 1,
                provider_name,
                selection.model.model_id,
                index,
            )
            try:
                tools = request.tools if request and hasattr(request, 'tools') else None
                generate = provider.generate(
                    instructions=instructions,
                    input_text=input_text,
                    model=selection.model.provider_model_name,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    tools=tools,
                )
                text = await asyncio.wait_for(generate, timeout=timeout_seconds) if timeout_seconds is not None else await generate
                text = _usable_text(text)
                if not text:
                    raise AIServiceUnavailableError(
                        "Provider returned no usable text.",
                        retryable=True,
                        provider=provider_name,
                        category="empty_output",
                    )
                ai_provider_service.llm.router.record_success(
                    provider_name,
                    model_id=selection.model.model_id,
                    total_ms=(perf_counter() - started) * 1000,
                )
                if trace is not None:
                    trace.update(
                        provider_generation_ms=round((perf_counter() - started) * 1000, 2),
                        final_provider=provider_name,
                        final_status="success",
                        output_chars=len(text),
                    )
                logger.info("AI provider succeeded: provider=%s total_ms=%s", provider_name, round((perf_counter() - started) * 1000))
                return text
            except asyncio.TimeoutError:
                timeout_error = AIServiceUnavailableError(
                    "Provider response exceeded the configured request budget.",
                    retryable=True,
                    provider=provider_name,
                    category="timeout",
                )
                last_error = timeout_error
                ai_provider_service.llm.router.record_failure(provider_name, timeout_error, model_id=selection.model.model_id)
                if trace is not None:
                    trace.setdefault("failed_attempts", []).append(
                        {"provider": provider_name, "category": "timeout", "detail": timeout_error.detail}
                    )
                logger.warning("AI provider timed out: provider=%s timeout_seconds=%s", provider_name, timeout_seconds)
                if index >= len(attempts) - 1:
                    break
            except AIServiceUnavailableError as exc:
                last_error = exc
                ai_provider_service.llm.router.record_failure(provider_name, exc, model_id=selection.model.model_id)
                if trace is not None:
                    trace.setdefault("failed_attempts", []).append(
                        {
                            "provider": provider_name,
                            "category": exc.category,
                            "detail": exc.detail,
                            "retryable": exc.retryable,
                        }
                    )
                logger.warning(
                    "AI provider failed: provider=%s retryable=%s category=%s detail=%s",
                    provider_name,
                    exc.retryable,
                    exc.category,
                    exc.detail,
                )
                if not allows_provider_fallback(exc) or index >= len(attempts) - 1:
                    break
            except Exception as exc:  # noqa: BLE001
                last_error = AIServiceUnavailableError(repr(exc), retryable=True, provider=provider_name, category="unexpected")
                ai_provider_service.llm.router.record_failure(provider_name, last_error, model_id=selection.model.model_id)
                logger.warning("AI provider failed unexpectedly: provider=%s error=%s", provider_name, repr(exc))
                if index >= len(attempts) - 1:
                    break
        if trace is not None:
            trace.update(final_provider=None, final_status="unavailable", output_chars=0)
        raise AIServiceUnavailableError(repr(last_error), retryable=False)

    runner_timeout = None if overall_timeout_seconds is None else overall_timeout_seconds + 1.0
    return _SYNC_ASYNC_RUNNER.run(_generate(), timeout=runner_timeout)


async def stream_text(
    *,
    instructions: str,
    input_text: str,
    temperature: float | None = None,
    max_output_tokens: int | None = None,
    trace: dict[str, Any] | None = None,
    model_request: ModelRequest | None = None,
) -> AsyncIterator[str]:
    from app.intelligence.ai.ai_provider_service import ai_provider_service

    last_error: Exception | None = None
    request = model_request or request_for_chat(streaming=True, context_size_estimate=max(1, len(input_text) // 4))
    model_selection_started = perf_counter()
    attempts = ai_provider_service.llm.model_candidates(request, max_count=max(1, settings.llm_max_fallbacks + 1))
    model_selection_ms = round((perf_counter() - model_selection_started) * 1000, 2)
    if trace is not None:
        trace["model_selection_ms"] = model_selection_ms
    if not attempts:
        raise AIServiceUnavailableError("No LLM provider is configured.", retryable=False, category="configuration")

    for index, (selection, provider) in enumerate(attempts):
        provider_name = selection.model.provider_id
        started = perf_counter()
        first_token_ms: float | None = None
        yielded_text = False
        try:
            if trace is not None:
                trace["provider"] = provider_name
                trace["model"] = selection.model.model_id
                trace["fallback_used"] = index > 0
                trace["fallback_started"] = index > 0
                trace["fallback_provider"] = provider_name if index > 0 else None
                trace["provider_attempt"] = index + 1
                trace.setdefault("failed_attempts", [])
                trace["provider_request_started_ms"] = round((perf_counter() - model_selection_started) * 1000, 2)
                if index > 0 and "fallback_from" not in trace and trace["failed_attempts"]:
                    trace["fallback_from"] = trace["failed_attempts"][0].get("provider")
                    trace["fallback_reason"] = trace["failed_attempts"][0].get("detail")
                if "request_id" in trace:
                    logger.info(
                        "ceaser_stream_stage request_id=%s stage=provider_selected provider=%s model=%s fallback_used=%s",
                        trace["request_id"],
                        provider_name,
                        trace.get("model"),
                        trace.get("fallback_used"),
                    )
                    if trace.get("fallback_started"):
                        logger.info(
                            "ceaser_stream_stage request_id=%s stage=fallback_started fallback_provider=%s fallback_from=%s fallback_reason=%s",
                            trace["request_id"],
                            trace.get("fallback_provider"),
                            trace.get("fallback_from"),
                            trace.get("fallback_reason"),
                        )
            # Extract tools from model_request if available
            tools = request.tools if request and hasattr(request, 'tools') else None

            async for chunk in provider.stream(
                instructions=instructions,
                input_text=input_text,
                model=selection.model.provider_model_name,
                max_output_tokens=max_output_tokens,
                trace=trace,
                tools=tools,
            ):
                if not chunk:
                    continue
                yielded_text = True
                if first_token_ms is None:
                    first_token_ms = (perf_counter() - started) * 1000
                    if trace is not None:
                        trace["first_token_ms"] = round(first_token_ms, 2)
                        if "request_id" in trace:
                            logger.info(
                                "ceaser_stream_stage request_id=%s stage=first_upstream_token provider=%s model=%s first_token_ms=%s",
                                trace["request_id"],
                                provider_name,
                                trace.get("model"),
                                trace["first_token_ms"],
                            )
                yield chunk
            if not yielded_text:
                raise AIServiceUnavailableError(
                    "Provider stream returned no usable text.",
                    retryable=True,
                    provider=provider_name,
                    category="empty_output",
                )
            total_ms = (perf_counter() - started) * 1000
            ai_provider_service.llm.router.record_success(
                provider_name,
                model_id=selection.model.model_id,
                total_ms=total_ms,
                first_token_ms=first_token_ms,
            )
            if trace is not None:
                trace.update(
                    provider_generation_ms=round(total_ms, 2),
                    final_provider=provider_name,
                    final_status="success",
                )
            logger.info(
                "AI provider stream succeeded: provider=%s first_token_ms=%s total_ms=%s",
                provider_name,
                None if first_token_ms is None else round(first_token_ms, 2),
                round(total_ms, 2),
            )
            return
        except AIServiceUnavailableError as exc:
            last_error = exc
            ai_provider_service.llm.router.record_failure(provider_name, exc, model_id=selection.model.model_id)
            if trace is not None:
                trace.setdefault("failed_attempts", []).append(
                    {
                        "provider": provider_name,
                        "detail": exc.detail,
                        "category": exc.category,
                        "retryable": exc.retryable,
                    }
                )
            logger.warning(
                "AI provider stream failed: provider=%s retryable=%s category=%s detail=%s",
                provider_name,
                exc.retryable,
                exc.category,
                exc.detail,
            )
            if yielded_text:
                if trace is not None:
                    trace.update(final_status="interrupted", fallback_blocked_after_output=True)
                raise
            if not allows_provider_fallback(exc) or index >= len(attempts) - 1:
                break
        except Exception as exc:  # noqa: BLE001
            last_error = AIServiceUnavailableError(repr(exc), retryable=True, provider=provider_name, category="unexpected")
            ai_provider_service.llm.router.record_failure(provider_name, last_error, model_id=selection.model.model_id)
            if trace is not None:
                trace.setdefault("failed_attempts", []).append(
                    {
                        "provider": provider_name,
                        "detail": repr(exc),
                        "category": "unexpected",
                        "retryable": True,
                    }
                )
            logger.warning("AI provider stream failed unexpectedly: provider=%s error=%s", provider_name, repr(exc))
            if yielded_text:
                if trace is not None:
                    trace.update(final_status="interrupted", fallback_blocked_after_output=True)
                raise last_error from exc
            if index >= len(attempts) - 1:
                break

    if trace is not None:
        trace.update(final_provider=None, final_status="unavailable")
    raise AIServiceUnavailableError(repr(last_error), retryable=False)


def _progressive_chunks(chunk: str, *, maximum_length: int = 56) -> list[str]:
    """Keep native small deltas intact, but break buffered completions at word boundaries."""
    if len(chunk) <= maximum_length:
        return [chunk]

    parts = re.findall(r"\S+\s*|\s+", chunk)
    result: list[str] = []
    current = ""
    for part in parts:
        if current and len(current) + len(part) > maximum_length:
            result.append(current)
            current = part
        else:
            current += part
    if current:
        result.append(current)
    return result
