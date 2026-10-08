import asyncio
import anyio
import httpx
import logging
import uuid
from typing import Annotated, Literal

import json
from collections.abc import AsyncIterator
from time import perf_counter

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from app.core.rate_limiter import rate_limiter
from app.core.stream_diagnostics import stream_diagnostics
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database.session import SessionLocal, database_timing, get_db
from app.core.database.execution import run_serial_db
from app.core.security.dependencies import get_current_user
from app.intelligence.ai.model_router import request_for_chat
from app.intelligence.ai.sync import generate_text_sync, stream_text
from app.intelligence.ai.errors import AIServiceUnavailableError
from app.models.user import User
from app.schemas.ceaser import CeaserChatRequest, CeaserChatResponse
from app.services.audit_service import AuditService
from app.services.background_task_service import background_task_store
from app.services.conversation_service import ConversationService
from app.services.orchestrator import CeaserOrchestrator
from app.services.rich_response_service import RichResponseService
from app.services.credit_service import CreditService, InsufficientCreditsError, ReservationConflictError

router = APIRouter(prefix="/ceaser", tags=["ceaser"])
logger = logging.getLogger(__name__)
_autocomplete_client = httpx.AsyncClient(timeout=httpx.Timeout(2.5, connect=1.0))


class CeaserDemoTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class CeaserDemoRequest(BaseModel):
    message: str = Field(min_length=1, max_length=14000)
    recent_turns: list[CeaserDemoTurn] = Field(default_factory=list, max_length=8)


class CeaserDemoResponse(BaseModel):
    response: str
    source: str = "live_backend"
    continuation_count: int = 0


@router.get("/chat/autocomplete")
async def ceaser_chat_autocomplete(
    _: Annotated[User, Depends(get_current_user)],
    query: str = Query(min_length=2, max_length=200),
):
    """Return live query completions without invoking the chat pipeline."""
    try:
        response = await _autocomplete_client.get(
            "https://suggestqueries.google.com/complete/search",
            params={"client": "firefox", "q": query, "hl": "en"},
        )
        response.raise_for_status()
        payload = response.json()
        suggestions = payload[1] if isinstance(payload, list) and len(payload) > 1 and isinstance(payload[1], list) else []
        return {"suggestions": [str(item).strip() for item in suggestions if str(item).strip()][:5]}
    except (httpx.HTTPError, ValueError, TypeError):
        logger.info("chat_autocomplete_unavailable query_chars=%s", len(query))
        return {"suggestions": []}


@router.post("/demo", response_model=CeaserDemoResponse)
async def ceaser_public_demo(payload: CeaserDemoRequest):
    instructions = (
        "You are CEASER, an AI operating system product demo. "
        "Generate a concise, polished, useful answer for a public landing-page demo. "
        "Use the provided scenario/context exactly. Do not ask for missing context unless the prompt truly has none. "
        "Do not mention backend, APIs, tokens, providers, or internal implementation. "
        "Keep the answer structured, specific, and appropriately concise. "
        "Use recent conversation turns to resolve follow-up requests without asking the user to repeat context."
    )
    history = "\n".join(f"{turn.role.title()}: {turn.content}" for turn in payload.recent_turns[-6:])
    input_text = "\n\n".join(part for part in (f"Recent conversation:\n{history}" if history else "", f"Current user request:\n{payload.message}") if part)
    model_request = request_for_chat(streaming=True, context_size_estimate=max(1, len(input_text) // 4))
    trace: dict = {}
    chunks = [chunk async for chunk in stream_text(
        instructions=instructions,
        input_text=input_text,
        temperature=0.35,
        max_output_tokens=1200,
        trace=trace,
        model_request=model_request,
    )]
    response = "".join(chunks)
    continuation_count = 0
    if trace.get("finish_reason") in {"length", "max_tokens", "token_limit"} and response:
        continuation_count = 1
        continuation_trace: dict = {}
        continuation_input = (
            f"Original user request:\n{payload.message}\n\n"
            f"Tail of answer so far:\n{response[-6000:]}\n\n"
            "Continue exactly where the answer stopped. Do not repeat earlier content. "
            "Finish the answer cleanly and output only the continuation."
        )
        response += "".join([chunk async for chunk in stream_text(
            instructions=instructions,
            input_text=continuation_input,
            temperature=0.35,
            max_output_tokens=900,
            trace=continuation_trace,
            model_request=model_request,
        )])
    return CeaserDemoResponse(response=response, continuation_count=continuation_count)


@router.post("/chat", response_model=CeaserChatResponse)
def ceaser_chat(payload: CeaserChatRequest, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    user_id = user.id
    billing_id = f"chat:{payload.request_id or uuid.uuid4().hex}"
    credits = CreditService(db)
    try:
        reservation = credits.reserve(user_id, billing_id, "ai_conversation")
    except InsufficientCreditsError as exc:
        raise HTTPException(status_code=402, detail="Insufficient CEASER credits.") from exc
    try:
        desktop_fast = _maybe_desktop_fast_response(payload)
        if desktop_fast is not None:
            credits.settle(user_id, billing_id, reservation.estimated_credits, meaningful_output=True)
            return desktop_fast
        response = CeaserOrchestrator(db).handle_message(
            user_id=user_id,
            message=payload.message,
            conversation_id=payload.conversation_id,
            file_ids=payload.file_ids,
            request_id=payload.request_id,
            parent_message_id=payload.parent_message_id,
            device_id=payload.device_id,
            desktop_file_context=payload.desktop_file_context,
            model_preference=payload.model_preference,
            force_live_web_search=payload.force_live_web_search,
            response_mode=payload.response_mode,
            image_model_preference=payload.image_model_preference,
        )
        response["rich_response"] = RichResponseService.compose(response,user_id=user_id,task_id=payload.request_id).model_dump(mode="json")
        AuditService(db).record(
            user_id=user_id,
            action="message_created",
            resource_type="conversation",
            resource_id=payload.conversation_id,
            metadata={"selected_agents": response.get("selected_agents", []), "memory_count": len(response.get("memories_used", []))},
        )
        credits.settle(user_id, billing_id, reservation.estimated_credits, meaningful_output=bool(response.get("response")))
        return response
    except ValueError as exc:
        db.rollback()
        credits.release(user_id, billing_id)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AIServiceUnavailableError as exc:
        db.rollback()
        credits.release(user_id, billing_id)
        raise HTTPException(
            status_code=503,
            detail={"code": "ai_capacity_busy", "message": "CEASER is handling unusually high AI demand. Please try again in a moment."},
            headers={"Retry-After": "5"},
        ) from exc
    except Exception:
        db.rollback()
        credits.release(user_id, billing_id)
        raise


def _maybe_desktop_fast_response(payload: CeaserChatRequest) -> dict | None:
    if payload.source != "desktop_companion" or not payload.voice:
        return None
    if payload.conversation_id or payload.file_ids:
        return None
    message = (payload.original_message or payload.message or "").strip()
    if not message:
        return None
    normalized = message.lower()
    heavy_terms = (
        "my ", "me ", "project", "file", "document", "pdf", "report", "memory",
        "notion", "github", "calendar", "task", "email", "mail", "upload", "post", "publish",
        "delete", "restore", "rename", "latest", "connected", "workspace",
        "summarize my", "what do i have", "what is my", "who am i",
    )
    current_terms = ("current", "latest", "today", "now", "news", "weather", "score", "price", "stock", "stats")
    if any(term in normalized for term in heavy_terms + current_terms):
        return None
    started = perf_counter()
    instructions = (
        "You are CEASER Desktop Companion. Answer the user's voice question directly and quickly. "
        "Keep the response concise, accurate, and useful for spoken playback. "
        "Use short paragraphs or bullets only when helpful. "
        "Do not mention backend, providers, sources, or implementation. "
        "Maximum 180 words."
    )
    trace: dict[str, object] = {}
    response = generate_text_sync(
        instructions=instructions,
        input_text=message,
        temperature=0.35,
        max_output_tokens=300,
        model_request=request_for_chat(context_size_estimate=max(1, len(message) // 4)),
        attempt_timeout_seconds=5.0,
        overall_timeout_seconds=12.0,
        trace=trace,
    ).strip()
    elapsed_ms = round((perf_counter() - started) * 1000, 2)
    logger.info(
        "ceaser_desktop_fast_response request_id=%s elapsed_ms=%s input_chars=%s output_chars=%s",
        payload.request_id,
        elapsed_ms,
        len(message),
        len(response),
    )
    return {
        "scope": "desktop_fast_ai",
        "conversation_id": None,
        "selected_agents": ["Ceaser"],
        "contributions": [],
        "contribution_summary": "Desktop fast response generated.",
        "memories_used": [],
        "research": None,
        "workflow": None,
        "context_summary": {
            "retrieval_scope": "desktop_fast_ai",
            "retrieval_sources": ["none"],
            "retrieval_time_ms": 0,
            "context_build_ms": 0,
            "backend_fast_path_ms": elapsed_ms,
            "provider": trace.get("provider"),
            "model": trace.get("model"),
            "fallback_used": bool(trace.get("fallback_used")),
            "provider_first_token_ms": trace.get("first_token_ms"),
            "cache_hit": True,
        },
        "suggestions": [],
        "response": response,
    }


@router.post("/chat/background")
def ceaser_chat_background(
    payload: CeaserChatRequest,
    background_tasks: BackgroundTasks,
    user: Annotated[User, Depends(get_current_user)],
):
    task_id = str(uuid.uuid4())
    background_task_store.create(task_id, user.id)
    background_tasks.add_task(_run_chat_background_task, task_id, user.id, payload)
    return {"task_id": task_id, "status": "queued"}


@router.get("/chat/background/{task_id}")
def get_ceaser_background_task(task_id: str, user: Annotated[User, Depends(get_current_user)]):
    record = background_task_store.get(task_id)
    if not record or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found.")
    return {
        "task_id": record.id,
        "status": record.status,
        "result": record.result,
        "error": record.error,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def _run_chat_background_task(task_id: str, user_id: str, payload: CeaserChatRequest) -> None:
    background_task_store.set_running(task_id)
    db = SessionLocal()
    billing_id = f"chat:{payload.request_id or task_id}"
    credits = CreditService(db)
    reserved = False
    try:
        credits.reserve(user_id, billing_id, "ai_conversation")
        reserved = True
        response = CeaserOrchestrator(db).handle_message(
            user_id=user_id,
            message=payload.message,
            conversation_id=payload.conversation_id,
            file_ids=payload.file_ids,
            request_id=payload.request_id,
            parent_message_id=payload.parent_message_id,
            device_id=payload.device_id,
            desktop_file_context=payload.desktop_file_context,
            model_preference=payload.model_preference,
            force_live_web_search=payload.force_live_web_search,
            response_mode=payload.response_mode,
            image_model_preference=payload.image_model_preference,
        )
        credits.settle(user_id, billing_id, settings.credit_costs.get("ai_conversation", 5), meaningful_output=bool(response))
        reserved = False
        background_task_store.set_result(task_id, response)
    except InsufficientCreditsError:
        background_task_store.set_error(task_id, "Insufficient CEASER credits.")
    except Exception:
        logger.exception("ceaser_background_task_failed task_id=%s user_id=%s", task_id, user_id)
        background_task_store.set_error(task_id, "We couldn't complete your request. Please try again.")
    finally:
        if reserved:
            credits.release(user_id, billing_id)
        db.close()


@router.post("/chat/stream")
async def ceaser_chat_stream(request: Request, payload: CeaserChatRequest, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    route_entered = perf_counter()
    user_id = user.id
    message = payload.message
    conversation_id = payload.conversation_id
    file_ids = list(payload.file_ids)
    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    billing_id = f"chat:{payload.request_id or request_id}"
    auth_trace = getattr(request.state, "ceaser_auth_trace", {})
    rate_started = perf_counter()
    request_limit = rate_limiter.check("chat", user_id, limit=10, window_seconds=60)
    rate_check_ms = round((perf_counter() - rate_started) * 1000, 2)
    if not request_limit.allowed:
        raise HTTPException(
            status_code=429,
            detail={"code": "rate_limited", "message": "You're sending requests pretty quickly. Try again in a few seconds.", "retry_after": request_limit.retry_after},
            headers={"Retry-After": str(request_limit.retry_after)},
        )
    concurrency_started = perf_counter()
    concurrency_limit = rate_limiter.acquire("chat-generation", user_id, limit=3)
    concurrency_check_ms = round((perf_counter() - concurrency_started) * 1000, 2)
    if not concurrency_limit.allowed:
        raise HTTPException(
            status_code=429,
            detail={"code": "rate_limited", "message": "You're sending requests pretty quickly. Try again in a few seconds.", "retry_after": concurrency_limit.retry_after},
            headers={"Retry-After": str(concurrency_limit.retry_after)},
        )
    credits = CreditService(db)
    conversation = None
    reservation_owned = False

    def reserve_credit():
        nonlocal reservation_owned
        result = credits.reserve(user_id, billing_id, "ai_conversation", allow_existing=False)
        reservation_owned = True
        return result

    def cleanup_before_stream():
        db.rollback()
        if reservation_owned:
            credits.release(user_id, billing_id)

    try:
        db_count_before, db_ms_before = database_timing()
        # The reservation already requires a durable transaction. Flush a new
        # conversation first so both records are committed in that transaction.
        if not conversation_id:
            conversation_started = perf_counter()
            conversation = await run_serial_db(ConversationService(db).create_pending, user_id=user_id)
            conversation_id = conversation.id
            conversation_lookup_ms = round((perf_counter() - conversation_started) * 1000, 2)
        else:
            conversation_lookup_ms = 0.0
        reserve_started = perf_counter()
        reservation = await run_serial_db(reserve_credit)
        credit_reservation_ms = round((perf_counter() - reserve_started) * 1000, 2)
        db_count_after, db_ms_after = database_timing()
        logger.info(
            "ceaser_stream_stage request_id=%s stage=credits_reserved duration_ms=%.2f db_queries=%s db_ms=%.2f",
            request_id, credit_reservation_ms,
            max(0, db_count_after - db_count_before), max(0.0, db_ms_after - db_ms_before),
        )
    except asyncio.CancelledError:
        try:
            with anyio.CancelScope(shield=True):
                await run_serial_db(cleanup_before_stream)
        finally:
            rate_limiter.release("chat-generation", user_id)
        raise
    except ReservationConflictError as exc:
        try:
            with anyio.CancelScope(shield=True):
                await run_serial_db(cleanup_before_stream)
        finally:
            rate_limiter.release("chat-generation", user_id)
        raise HTTPException(status_code=409, detail={"code": "request_id_conflict", "message": str(exc)}) from exc
    except InsufficientCreditsError as exc:
        rate_limiter.release("chat-generation", user_id)
        raise HTTPException(status_code=402, detail="Insufficient CEASER credits.") from exc
    except Exception:
        try:
            with anyio.CancelScope(shield=True):
                await run_serial_db(cleanup_before_stream)
        finally:
            rate_limiter.release("chat-generation", user_id)
        raise
    # Keep only immutable primitives across the async SSE lifetime. The ORM
    # reservation is committed/refreshed here and must not be dereferenced
    # after the request session has expired or been detached.
    try:
        snapshot_started = perf_counter()
        reservation_estimated_credits = await run_serial_db(lambda: int(reservation.estimated_credits))
        reservation_snapshot_ms = round((perf_counter() - snapshot_started) * 1000, 2)
        # A new chat is created authoritatively inside the stream request. This
        # removes the frontend's blocking create-conversation round trip while
        # preserving one durable conversation and the existing ownership checks.
        if conversation is not None:
            logger.info("ceaser_stream_stage request_id=%s stage=conversation_created duration_ms=%.2f", request_id, conversation_lookup_ms)
    except (Exception, asyncio.CancelledError):
        try:
            with anyio.CancelScope(shield=True):
                await run_serial_db(cleanup_before_stream)
        finally:
            rate_limiter.release("chat-generation", user_id)
        raise
    request_received = getattr(request.state, "ceaser_request_received_at", route_entered)
    logger.info("ceaser_latency request_id=%s route_entry_ms=%.2f conversation_id=%s", request_id, (route_entered - request_received) * 1000, conversation_id)
    logger.info("ceaser_stream_stage request_id=%s stage=authentication_complete user_id=%s", request_id, user_id)
    logger.info(
        "ceaser_stream_baseline request_id=%s phase=pre_stream auth_total_ms=%s auth_remote_ms=%s auth_db_validation_ms=%s auth_cache_hit=%s rate_check_ms=%s concurrency_check_ms=%s credit_reservation_ms=%s conversation_create_ms=%s",
        request_id, auth_trace.get("total_ms"), auth_trace.get("remote_ms"), auth_trace.get("db_validation_ms"),
        auth_trace.get("cache_hit"), rate_check_ms, concurrency_check_ms, credit_reservation_ms, conversation_lookup_ms,
    )

    def event(event_type: str, data: dict | str) -> str:
        payload_text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=True)
        return f"event: {event_type}\ndata: {payload_text}\n\n"

    async def stream() -> AsyncIterator[str]:
        # FastAPI releases request-scoped dependencies once the streaming
        # response starts. Keep all ORM work inside a session owned by the SSE
        # generator so models cannot become detached mid-stream.
        stream_db = SessionLocal()
        stream_credits = CreditService(stream_db)
        started = request_received
        stage_marks: dict[str, float] = {"start": started}
        trace: dict[str, object] = {
            "request_id": request_id,
            "auth_total_ms": auth_trace.get("total_ms"),
            "route_entry_ms": round((route_entered - request_received) * 1000, 2),
            "pre_stream_ms": round((perf_counter() - request_received) * 1000, 2),
            "auth_remote_ms": auth_trace.get("remote_ms"),
            "auth_db_validation_ms": auth_trace.get("db_validation_ms"),
            "auth_db_query_ms": auth_trace.get("db_query_ms"),
            "rate_check_ms": rate_check_ms,
            "concurrency_check_ms": concurrency_check_ms,
            "credit_reservation_ms": credit_reservation_ms,
            "conversation_create_ms": conversation_lookup_ms,
            "reservation_snapshot_ms": reservation_snapshot_ms,
        }
        first_sse_token_logged = False
        completed_meaningfully = False
        prepared = None
        chunks: list[str] = []
        orchestrator = None

        def finalize_response(text, assistant_message=None):
            nonlocal completed_meaningfully
            result = orchestrator.finalize_stream_response(prepared, text, assistant_message=assistant_message)
            completed_meaningfully = bool(result.get("response"))
            return result

        def cleanup_stream():
            try:
                if not completed_meaningfully and prepared is not None:
                    try:
                        stream_db.rollback()
                        orchestrator.interrupt_stream_response(prepared, "".join(chunks))
                    except Exception:
                        stream_db.rollback()
                        logger.exception("ceaser_stream_interruption_persistence_failed request_id=%s", request_id)
                if completed_meaningfully:
                    stream_credits.settle(user_id, billing_id, reservation_estimated_credits, meaningful_output=True)
                else:
                    stream_db.rollback()
                    stream_credits.release(user_id, billing_id)
            except Exception:
                stream_db.rollback()
                logger.exception("ceaser_stream_settlement_failed request_id=%s billing_id=%s", request_id, billing_id)
            finally:
                stream_db.close()

        try:
            yield event("response.started", {"id": request_id, "status": "streaming", "conversation_id": conversation_id})
            orchestrator = await run_serial_db(CeaserOrchestrator, stream_db)
            trace["agent_started_ms"] = round((perf_counter() - started) * 1000, 2)
            logger.info("ceaser_latency request_id=%s agent_started_ms=%s", request_id, trace["agent_started_ms"])
            logger.info("ceaser_stream_stage request_id=%s stage=retrieval_started", request_id)
            prepare_started = perf_counter()
            trace["prepare_started_ms"] = round((prepare_started - started) * 1000, 2)
            prepared = await orchestrator.prepare_stream_request(
                user_id=user_id,
                message=message,
                conversation_id=conversation_id,
                file_ids=file_ids,
                request_id=payload.request_id or request_id,
                parent_message_id=payload.parent_message_id,
                model_preference=payload.model_preference,
                force_live_web_search=payload.force_live_web_search,
            )
            stage_marks["prepared"] = perf_counter()
            trace["prepare_completed_ms"] = round((stage_marks["prepared"] - started) * 1000, 2)
            trace["prepare_stream_request_ms"] = round((stage_marks["prepared"] - prepare_started) * 1000, 2)
            trace["prepare_stage_timings"] = prepared.get("observability", {}).get("stage_timings", [])
            trace["prepare_worker_ms"] = prepared.get("observability", {}).get("prepare_ms")
            trace["prepare_logging_ms"] = prepared.get("observability", {}).get("prepare_logging_ms")
            trace["prepare_unattributed_ms"] = prepared.get("observability", {}).get("prepare_unattributed_ms")
            trace["retrieval_time_ms"] = prepared.get("observability", {}).get("retrieval_time_ms")
            trace["routing_ms"] = prepared.get("observability", {}).get("routing_ms")
            trace["tool_calls_ms"] = prepared.get("observability", {}).get("tool_calls_ms")
            trace["web_search_requested"] = prepared.get("observability", {}).get("web_search_requested")
            trace["search_ms"] = prepared.get("observability", {}).get("search_ms")
            trace["extraction_ms"] = prepared.get("observability", {}).get("extraction_ms")
            trace["research_assembly_ms"] = prepared.get("observability", {}).get("research_assembly_ms")
            trace["research_total_ms"] = prepared.get("observability", {}).get("research_total_ms")
            trace["internal_context_found"] = prepared.get("observability", {}).get("internal_context_found")
            trace["memory_match_count"] = prepared.get("observability", {}).get("memory_match_count")
            trace["context_build_ms"] = prepared.get("observability", {}).get("retrieval_time_ms")
            logger.info(
                "ceaser_stream_stage request_id=%s stage=intent_complete intent_ms=%s",
                request_id,
                prepared.get("observability", {}).get("intent_ms"),
            )
            logger.info(
                "ceaser_stream_stage request_id=%s stage=retrieval_complete retrieval_time_ms=%s",
                request_id,
                prepared.get("observability", {}).get("retrieval_time_ms"),
            )
            logger.info(
                "ceaser_stream_stage request_id=%s stage=context_complete context_tokens=%s prepare_ms=%s routing_ms=%s tool_calls_ms=%s web_search_requested=%s search_ms=%s extraction_ms=%s research_assembly_ms=%s internal_context_found=%s memory_match_count=%s context_mode=%s retrieval_scope=%s retrieval_sources=%s",
                request_id,
                prepared.get("observability", {}).get("context_tokens"),
                prepared.get("observability", {}).get("prepare_ms"),
                trace.get("routing_ms"),
                trace.get("tool_calls_ms"),
                trace.get("web_search_requested"),
                trace.get("search_ms"),
                trace.get("extraction_ms"),
                trace.get("research_assembly_ms"),
                trace.get("internal_context_found"),
                trace.get("memory_match_count"),
                prepared.get("observability", {}).get("context_mode"),
                prepared.get("observability", {}).get("retrieval_scope"),
                prepared.get("observability", {}).get("retrieval_sources"),
            )

            if prepared["mode"] == "direct":
                trace["endpoint_ttft_ms"] = round((perf_counter() - started) * 1000, 2)
                trace["total_time_ms"] = trace["endpoint_ttft_ms"]
                trace["output_tokens"] = max(1, round(len(prepared["response"]) / 4)) if prepared.get("response") else 0
                yield event("token", prepared["response"])
                first_sse_token_logged = True
                logger.info(
                    "ceaser_stream_stage request_id=%s stage=first_sse_token endpoint_ttft_ms=%s",
                    request_id,
                    trace["endpoint_ttft_ms"],
                )
                prepared["stream_trace"] = trace
                response = await run_serial_db(finalize_response, prepared["response"])
                rich = RichResponseService.compose(response,user_id=user_id,task_id=request_id).model_dump(mode="json")
                response["rich_response"] = rich
                for block in rich["blocks"]: yield event("block.created", block)
                yield event("response.completed", rich)
                yield event("complete", response)
                completed_meaningfully = bool(response.get("response"))
                logger.info(
                    "[CEASER PERF] request_id=%s context_ms=%s model_start_ms=%s ttft_ms=%s generation_ms=%s total_ms=%s context_tokens=%s output_tokens=%s",
                    request_id,
                    prepared.get("observability", {}).get("prepare_ms"),
                    "not_applicable",
                    trace.get("endpoint_ttft_ms"),
                    "not_applicable",
                    trace.get("total_time_ms"),
                    prepared.get("observability", {}).get("context_tokens"),
                    trace.get("output_tokens"),
                )
                logger.info("ceaser_stream_stage request_id=%s stage=request_complete total_ms=%s", request_id, trace["total_time_ms"])
                return

            stage_marks["context_ready"] = perf_counter()
            trace["llm_request_sent_ms"] = round((perf_counter() - started) * 1000, 2)
            logger.info("ceaser_latency request_id=%s llm_request_sent_ms=%s", request_id, trace["llm_request_sent_ms"])
            chunks: list[str] = []
            assistant_message = None
            persisted_length = 0
            async for chunk in orchestrator.response_pipeline.stream(
                prepared["message"],
                prepared["context"],
                trace=trace,
            ):
                chunks.append(chunk)
                response_so_far = "".join(chunks)
                if not first_sse_token_logged:
                    # Capture TTFT timestamps before anything else so the
                    # measurement is not inflated by logging or serialization.
                    token_received_at = perf_counter()
                    trace["endpoint_ttft_ms"] = round((perf_counter() - started) * 1000, 2)
                    first_sse_token_logged = True
                    # Yield the first token immediately — nothing must come
                    # between the provider delivering the first chunk and the
                    # client receiving it. All logging and diagnostics follow.
                    yield event("token", chunk)
                    trace["first_token_forwarding_ms"] = round((perf_counter() - token_received_at) * 1000, 2)
                    # Post-yield: log the full TTFT breakdown. These calls are
                    # now safely after the token is on the wire.
                    logger.info("ceaser_latency request_id=%s first_token_ms=%s", request_id, trace["endpoint_ttft_ms"])
                    logger.info(
                        "ceaser_stream_stage request_id=%s stage=first_sse_token endpoint_ttft_ms=%s",
                        request_id,
                        trace["endpoint_ttft_ms"],
                    )
                    logger.info(
                        "ceaser_stream_baseline request_id=%s phase=first_token auth_ms=%s rate_ms=%s concurrency_ms=%s credits_ms=%s conversation_ms=%s prepare_ms=%s intent_ms=%s routing_ms=%s retrieval_ms=%s context_ms=%s model_selection_ms=%s prompt_build_ms=%s provider_connect_ms=%s provider_first_token_ms=%s endpoint_ttft_ms=%s",
                        request_id, trace.get("auth_total_ms"), trace.get("rate_check_ms"), trace.get("concurrency_check_ms"),
                        trace.get("credit_reservation_ms"), trace.get("conversation_create_ms"), trace.get("prepare_stream_request_ms"),
                        prepared.get("observability", {}).get("intent_ms"), trace.get("routing_ms"), trace.get("retrieval_time_ms"),
                        prepared.get("observability", {}).get("context_build_ms"), trace.get("model_selection_ms"), trace.get("prompt_build_ms"),
                        trace.get("provider_connect_ms"), trace.get("first_token_ms"), trace.get("endpoint_ttft_ms"),
                    )
                    logger.info(
                        "ceaser_stream_baseline request_id=%s phase=prepare_breakdown stages=%s",
                        request_id,
                        json.dumps(trace.get("prepare_stage_timings", []), ensure_ascii=True, separators=(",", ":")),
                    )
                    db_queries, db_ms = database_timing()
                    yield event("diagnostics", stream_diagnostics(trace, request_id=request_id,
                        stage="first_content_forwarded", elapsed_ms=(perf_counter() - started) * 1000,
                        db_queries=db_queries, db_ms=db_ms))
                    # Durability begins only after the first chunk has been
                    # forwarded. A database commit must never delay user TTFT.
                    assistant_message = await run_serial_db(orchestrator.begin_stream_response, prepared)
                    if assistant_message:
                        await run_serial_db(orchestrator.persist_stream_response, assistant_message, response_so_far)
                        persisted_length = len(response_so_far)
                    continue
                if assistant_message and len(response_so_far) - persisted_length >= 360:
                    await run_serial_db(orchestrator.persist_stream_response, assistant_message, response_so_far)
                    persisted_length = len(response_so_far)
                yield event("token", chunk)
            response_text = "".join(chunks).strip()
            trace["output_tokens"] = max(1, round(len(response_text) / 4)) if response_text else 0
            trace["total_time_ms"] = round((perf_counter() - started) * 1000, 2)
            prepared["stream_trace"] = trace
            persistence_started = perf_counter()
            response = await run_serial_db(finalize_response, response_text, assistant_message=assistant_message)
            trace["persistence_ms"] = round((perf_counter() - persistence_started) * 1000, 2)
            logger.info("ceaser_stream_stage request_id=%s stage=persistence_complete persistence_ms=%s elapsed_ms=%.2f", request_id, trace["persistence_ms"], (perf_counter() - started) * 1000)
            if trace.get("structural_completion_blocked"):
                response["status"] = "partial"
                response["completion_warning"] = "The code artifact needs continuation before it is complete."
                logger.warning(
                    "ceaser_stream_stage request_id=%s stage=structural_completion_blocked artifact_type=%s continuation_count=%s",
                    request_id,
                    trace.get("artifact_type"),
                    trace.get("continuation_count", 0),
                )
            rich = RichResponseService.compose(response,user_id=user_id,task_id=request_id).model_dump(mode="json")
            response["rich_response"] = rich
            stage_marks["complete"] = perf_counter()
            logger.info(
                "ceaser_latency request_id=%s request_received_ms=0 agent_started_ms=%s context_build_ms=%s routing_ms=%s tool_calls_ms=%s llm_request_sent_ms=%s first_token_ms=%s last_token_ms=%s",
                request_id,
                trace.get("agent_started_ms"),
                trace.get("context_build_ms"),
                trace.get("routing_ms"),
                trace.get("tool_calls_ms"),
                trace.get("llm_request_sent_ms"),
                trace.get("endpoint_ttft_ms"),
                trace.get("total_time_ms"),
            )
            logger.info(
                "[CEASER PERF] request_id=%s context_ms=%s model_start_ms=%s ttft_ms=%s generation_ms=%s total_ms=%s context_tokens=%s output_tokens=%s",
                request_id,
                prepared.get("observability", {}).get("prepare_ms"),
                trace.get("llm_request_sent_ms"),
                trace.get("endpoint_ttft_ms"),
                trace.get("provider_generation_ms") or trace.get("total_time_ms"),
                trace.get("total_time_ms"),
                prepared.get("observability", {}).get("context_tokens"),
                trace.get("output_tokens"),
            )
            logger.info(
                "ceaser_stream_trace user_id=%s conversation_id=%s prepare_ms=%s context_ms=%s provider=%s model=%s fallback=%s first_token_ms=%s total_ms=%s",
                user_id,
                conversation_id,
                round((stage_marks.get("prepared", started) - started) * 1000, 2),
                round((stage_marks.get("context_ready", stage_marks.get("prepared", started)) - stage_marks.get("prepared", started)) * 1000, 2),
                trace.get("provider"),
                trace.get("model"),
                trace.get("fallback"),
                trace.get("first_token_ms"),
                round((stage_marks["complete"] - started) * 1000, 2),
            )
            logger.info(
                "ceaser_stream_stage request_id=%s stage=generation_complete provider=%s model=%s fallback_used=%s fallback_from=%s upstream_ttft_ms=%s provider_connect_ms=%s provider_generation_ms=%s output_tokens=%s",
                request_id,
                trace.get("provider"),
                trace.get("model"),
                trace.get("fallback_used"),
                trace.get("fallback_from"),
                trace.get("first_token_ms"),
                trace.get("provider_connect_ms"),
                trace.get("provider_generation_ms"),
                trace.get("output_tokens"),
            )
            await run_serial_db(AuditService(stream_db).record,
                user_id=user_id,
                action="message_created",
                resource_type="conversation",
                resource_id=conversation_id,
                metadata={"selected_agents": response.get("selected_agents", []), "memory_count": len(response.get("memories_used", []))},
            )
            for block in rich["blocks"]: yield event("block.created", block)
            yield event("activity", rich["activity"][0])
            yield event("response.completed", rich)
            yield event("complete", response)
            db_queries, db_ms = database_timing()
            yield event("diagnostics", stream_diagnostics(trace, request_id=request_id,
                stage="response_completed", elapsed_ms=(perf_counter() - started) * 1000,
                db_queries=db_queries, db_ms=db_ms))
            completed_meaningfully = bool(response.get("response"))
            logger.info("ceaser_stream_stage request_id=%s stage=request_complete total_ms=%s", request_id, trace.get("total_time_ms"))
        except ValueError as exc:
            yield event("response.failed", {"id": request_id, "status": "failed", "error": {"category": "validation", "message": str(exc), "retryable": False}})
            yield event("error", {"message": str(exc)})
        except Exception:
            await run_serial_db(stream_db.rollback)
            logger.exception("ceaser_chat_stream_failed user_id=%s conversation_id=%s", user_id, conversation_id)
            yield event("response.failed", {"id": request_id, "status": "failed", "error": {"category": "internal", "message": "We couldn't complete your request. Please try again.", "retryable": True}})
            yield event("error", {"message": "We couldn't complete your request. Please try again."})
        finally:
            try:
                with anyio.CancelScope(shield=True):
                    await run_serial_db(cleanup_stream)
            finally:
                rate_limiter.release("chat-generation", user_id)

    # Keep SSE events flowing through hosting proxies as they are produced.
    # Without no-transform / X-Accel-Buffering, a proxy can hold small token
    # events and make a genuine stream look like one delayed final response.
    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _chunk_text(text: str, max_chars: int = 120) -> list[str]:
    if not text:
        return []
    chunks: list[str] = []
    buffer = ""
    for piece in text.split():
        candidate = f"{buffer} {piece}".strip()
        if len(candidate) > max_chars and buffer:
            chunks.append(buffer)
            buffer = piece
        else:
            buffer = candidate
    if buffer:
        chunks.append(buffer)
    return chunks
