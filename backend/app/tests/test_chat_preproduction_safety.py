import asyncio
from datetime import timedelta
from types import SimpleNamespace

import anyio
import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app.api.ceaser import routes
from app.core.config.settings import settings
from app.core.database.base import Base
from app.core.security import dependencies
from app.intelligence.ai.ai_provider_service import ai_provider_service
from app.intelligence.ai.errors import AIServiceUnavailableError
from app.intelligence.ai.sync import stream_text
from app.models.conversation import Conversation, Message
from app.models.growth import CreditReservation, CreditWallet
from app.models.mixins import utc_now
from app.models.user import User
from app.schemas.ceaser import CeaserChatRequest
from app.services.conversation_service import ConversationService
from app.services.credit_service import CreditService, ReservationConflictError
from app.services.orchestrator.memory_capture import MemoryCapture
from app.services.orchestrator.orchestrator import CeaserOrchestrator
from app.services.orchestrator.response_pipeline import ResponsePipeline


@pytest.fixture
def database(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        owner, other = User(email="owner@test.invalid"), User(email="other@test.invalid")
        db.add_all([owner, other])
        db.commit()
        ids = owner.id, other.id
    monkeypatch.setattr(routes, "SessionLocal", factory)
    monkeypatch.setattr(CeaserOrchestrator, "_generate_suggestions", lambda *a, **kw: [])
    monkeypatch.setattr(MemoryCapture, "capture_interaction", lambda *a, **kw: [])
    try:
        yield factory, ids
    finally:
        engine.dispose()


def request():
    req = Request({"type": "http", "method": "POST", "path": "/ceaser/chat/stream", "headers": []})
    req.state.request_id = "safety-test"
    return req


def test_foreign_conversation_rejected_before_history(database, monkeypatch):
    factory, (owner, other) = database
    with factory() as db:
        conversation = ConversationService(db).create(other)
        conversation_id = conversation.id
        orchestrator = CeaserOrchestrator(db)
        monkeypatch.setattr(orchestrator, "_conversation_context", lambda *_: pytest.fail("history accessed"))
        with pytest.raises(ValueError, match="Conversation not found"):
            orchestrator.prepare_stream_request(owner, "hello", conversation_id)


@pytest.mark.parametrize("status", ["settled", "released", "expired"])
def test_reservation_reuse_rejects_terminal_or_expired(database, status):
    factory, (owner, _) = database
    with factory() as db:
        service = CreditService(db)
        reservation = service.reserve(owner, "reuse", "ai_conversation")
        if status == "expired":
            reservation.expires_at = utc_now() - timedelta(seconds=1)
        else:
            reservation.status = status
        db.commit()
        with pytest.raises(ReservationConflictError):
            service.reserve(owner, "reuse", "ai_conversation")


def test_reservation_snapshot_has_no_reload_and_active_duplicate_rejected(database):
    factory, (owner, _) = database
    with factory() as db:
        service = CreditService(db)
        reservation = service.reserve(owner, "snapshot", "ai_conversation", estimate=5)
        assert "estimated_credits" not in inspect(reservation).expired_attributes
        statements = []
        def record(*args):
            statements.append(args[2])
        event.listen(db.bind, "before_cursor_execute", record)
        assert reservation.estimated_credits == 5
        assert statements == []
        event.remove(db.bind, "before_cursor_execute", record)
        with pytest.raises(ReservationConflictError):
            service.reserve(owner, "snapshot", "ai_conversation", allow_existing=False)
        assert db.query(CreditReservation).count() == 1


@pytest.mark.parametrize("status, expected", [(500, 503), (503, 503), (429, 503), (401, 401)])
def test_auth_upstream_status_classification(monkeypatch, status, expected):
    monkeypatch.setattr(settings, "dev_auth_bypass", False)
    monkeypatch.setattr(dependencies, "verify_desktop_access_token", lambda _: None)
    monkeypatch.setattr(dependencies, "_cached_supabase_user", lambda _: None)
    async def fail(_):
        response = httpx.Response(status, request=httpx.Request("GET", "https://auth.test.invalid/user"))
        response.raise_for_status()
    monkeypatch.setattr(dependencies.supabase_auth, "get_user", fail)
    with pytest.raises(HTTPException) as error:
        asyncio.run(dependencies.get_current_user(request(), None, "Bearer test"))
    assert error.value.status_code == expected


@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.parametrize("unexpected", [False, True])
def test_provider_fallback_only_before_visible_text(monkeypatch, partial, unexpected):
    called = []
    class First:
        async def stream(self, **kwargs):
            if partial:
                yield "First prefix"
            if unexpected:
                raise RuntimeError("connection interrupted")
            raise AIServiceUnavailableError("interrupted", retryable=True)
    class Second:
        async def stream(self, **kwargs):
            called.append(True)
            yield "Second answer"
    def selection(name):
        return SimpleNamespace(model=SimpleNamespace(provider_id=name, model_id=name, provider_model_name=name))
    monkeypatch.setattr(ai_provider_service.llm, "model_candidates", lambda *a, **kw: [(selection("groq"), First()), (selection("gemini"), Second())])
    monkeypatch.setattr(ai_provider_service.llm.router, "record_failure", lambda *a, **kw: None)
    monkeypatch.setattr(ai_provider_service.llm.router, "record_success", lambda *a, **kw: None)
    async def run():
        chunks, trace = [], {}
        try:
            async for chunk in stream_text(instructions="test", input_text="hello", trace=trace):
                chunks.append(chunk)
        except AIServiceUnavailableError:
            assert partial
        if partial:
            assert chunks == ["First prefix"] and not called
            assert trace["final_status"] == "interrupted"
        else:
            assert chunks == ["Second answer"] and called
    asyncio.run(run())


@pytest.mark.parametrize("stop_at", ["first_token", "complete", "finish", "provider_error"])
def test_stream_persists_and_settles_at_each_boundary(database, monkeypatch, stop_at):
    factory, (owner, _) = database
    async def provider(*a, **kw):
        yield "Hello"
        if stop_at == "provider_error":
            raise RuntimeError("stream interrupted")
        yield " there"
    monkeypatch.setattr(ResponsePipeline, "stream", provider)
    async def run():
        db = factory()
        try:
            response = await routes.ceaser_chat_stream(request(), CeaserChatRequest(message="hello", request_id="boundary"), SimpleNamespace(id=owner), db)
            async for chunk in response.body_iterator:
                if (stop_at == "first_token" and chunk.startswith("event: token")) or (stop_at == "complete" and chunk.startswith("event: complete\n")):
                    await response.body_iterator.aclose()
                    break
        finally:
            db.close()
    asyncio.run(run())
    with factory() as db:
        messages = db.query(Message).all()
        assert [message.role for message in messages].count("user") == 1
        assistants = [message for message in messages if message.role == "assistant"]
        assert len(assistants) == 1
        assistant = assistants[0]
        interrupted = stop_at in {"first_token", "provider_error"}
        assert assistant.content == ("Hello" if interrupted else "Hello there")
        assert assistant.extra_metadata["streaming"] is False
        if interrupted:
            assert assistant.extra_metadata["status"] == "interrupted"
        assert db.query(CreditReservation).one().status == ("released" if interrupted else "settled")
        assert db.query(CreditWallet).one().reserved_balance == 0


def test_anyio_disconnect_drains_worker_without_starvation():
    import threading
    from app.core.database.execution import run_serial_db
    entered, finished = threading.Event(), threading.Event()
    def work():
        entered.set()
        finished.wait(.03)
        finished.set()
    async def run():
        async with anyio.create_task_group() as group:
            group.start_soon(run_serial_db, work)
            while not entered.is_set():
                await anyio.sleep(0)
            group.cancel_scope.cancel()
        assert finished.is_set()
    anyio.run(run)


@pytest.mark.parametrize("phase", ["begin_stream_response", "finalize_stream_response"])
def test_disconnect_during_committed_worker_preserves_accounting(database, monkeypatch, phase):
    import threading
    factory, (owner, _) = database
    entered = threading.Event()
    original = getattr(CeaserOrchestrator, phase)
    def slow_committed(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        entered.set()
        threading.Event().wait(.03)
        return result
    monkeypatch.setattr(CeaserOrchestrator, phase, slow_committed)
    async def provider(*a, **kw):
        yield "Hello"
    monkeypatch.setattr(ResponsePipeline, "stream", provider)
    async def consume():
        db = factory()
        try:
            response = await routes.ceaser_chat_stream(request(), CeaserChatRequest(message="hello", request_id="disconnect"), SimpleNamespace(id=owner), db)
            async for _ in response.body_iterator:
                pass
        finally:
            db.close()
    async def run():
        with anyio.fail_after(5):
            async with anyio.create_task_group() as group:
                group.start_soon(consume)
                while not entered.is_set():
                    await anyio.sleep(.001)
                group.cancel_scope.cancel()
    anyio.run(run)
    with factory() as db:
        assert db.query(Message).count() == 2
        assistant = db.query(Message).filter_by(role="assistant").one()
        assert assistant.content == "Hello"
        assert assistant.extra_metadata["streaming"] is False
        expected = "settled" if phase == "finalize_stream_response" else "released"
        assert db.query(CreditReservation).one().status == expected
        assert db.query(CreditWallet).one().reserved_balance == 0


def test_duplicate_stream_does_not_release_original_reservation(database):
    factory, (owner, _) = database
    with factory() as db:
        CreditService(db).reserve(owner, "chat:duplicate", "ai_conversation")
    async def run():
        db = factory()
        try:
            with pytest.raises(HTTPException) as error:
                await routes.ceaser_chat_stream(request(), CeaserChatRequest(message="hello", request_id="duplicate"), SimpleNamespace(id=owner), db)
            assert error.value.status_code == 409
        finally:
            db.close()
    asyncio.run(run())
    with factory() as db:
        assert db.query(Conversation).count() == 0
        assert db.query(CreditReservation).one().status == "reserved"
        assert db.query(CreditWallet).one().reserved_balance > 0
