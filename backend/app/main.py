from contextlib import asynccontextmanager
import logging
import os
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError

from app.api.auth.routes import router as auth_router
from app.api.admin.routes import router as admin_router
from app.api.admin.internships import router as admin_internships_router
from app.api.automations.routes import router as automations_router
from app.api.agents.routes import router as agents_router
from app.api.billing.routes import router as billing_router
from app.api.capabilities.routes import router as capabilities_router
from app.api.ceaser.routes import router as ceaser_router
from app.api.certificates.routes import router as certificates_router
from app.api.cloud.routes import router as cloud_router
from app.api.commercial.routes import router as commercial_router
from app.api.conversations.routes import router as conversations_router
from app.api.credits.routes import router as credits_router
from app.api.documents.routes import router as documents_router
from app.api.desktop.routes import router as desktop_router
from app.api.drafts.routes import agent_router as agent_workbenches_router
from app.api.drafts.routes import router as drafts_router
from app.api.files.routes import router as files_router
from app.api.integrations.routes import router as integrations_router
from app.api.knowledge.routes import router as knowledge_router
from app.api.live.routes import router as live_router
from app.api.memories.routes import router as memories_router
from app.api.messages.routes import chat_router, router as messages_router
from app.api.projects.routes import router as projects_router
from app.api.research.routes import router as research_router
from app.api.voice.routes import router as voice_router
from app.api.waitlist.routes import router as waitlist_router
from app.api.workflows.routes import router as workflows_router
from app.core.config.settings import settings
from app.core.database.session import SessionLocal, begin_database_timing, database_timing, end_database_timing
from app.core.security.supabase_auth import supabase_auth
from app.intelligence.ai.errors import AIServiceUnavailableError
from app.intelligence.ai.ai_provider_service import ai_provider_service
from app.services.automations.automation_worker import automation_worker


logger = logging.getLogger(__name__)


def configure_application_logging() -> None:
    """Ensure CEASER provider telemetry reaches Render stdout."""
    app_logger = logging.getLogger("app")
    level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    app_logger.setLevel(level)
    if not app_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        app_logger.addHandler(handler)
    # Uvicorn configures its own loggers. Keep CEASER logs single-emission.
    app_logger.propagate = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    configuration_errors = settings.production_configuration_errors()
    if configuration_errors:
        raise RuntimeError(
            "Unsafe or incomplete production configuration: " + ", ".join(configuration_errors)
        )
    logger.info(
        "ceaser_llm_configuration primary=%s provider_order=%s openai_key_configured=%s",
        settings.llm_provider,
        settings.llm_provider_order_raw,
        bool(settings.openai_api_key),
    )
    automation_worker.start()
    try:
        yield
    finally:
        await automation_worker.stop()
        await supabase_auth.close()
        await ai_provider_service.llm.aclose()


def create_app() -> FastAPI:
    configure_application_logging()
    app = FastAPI(title="CEASER Backend", version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def observability_middleware(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid4().hex
        request.state.request_id = request_id
        started = perf_counter()
        request.state.ceaser_request_received_at = started
        timing_tokens = begin_database_timing(request_id=request_id)
        try:
            response = await call_next(request)
            elapsed_ms = round((perf_counter() - started) * 1000)
            query_count, database_ms = database_timing()
            response.headers["X-Request-Id"] = request_id
            response.headers["X-Process-Time-Ms"] = str(elapsed_ms)
            response.headers["X-Database-Time-Ms"] = str(database_ms)
            response.headers["X-Database-Query-Count"] = str(query_count)
            response.headers["Server-Timing"] = f"app;dur={elapsed_ms}, db;dur={database_ms}"
            auth_trace = getattr(request.state, "ceaser_auth_trace", {})
            for label, key in (("auth", "total_ms"), ("auth_remote", "remote_ms"), ("auth_db", "db_validation_ms")):
                value = auth_trace.get(key)
                if type(value) in (int, float) and 0 <= value < 3600000:
                    response.headers["Server-Timing"] += f", {label};dur={value:.2f}"
            logger.info(
                "request_complete method=%s path=%s status=%s request_id=%s elapsed_ms=%s db_ms=%s db_queries=%s",
                request.method,
                request.url.path,
                response.status_code,
                request_id,
                elapsed_ms,
                database_ms,
                query_count,
            )
            return response
        finally:
            end_database_timing(timing_tokens)

    # Keep CORS outside application middleware so normalized error responses
    # retain their origin headers as well as successful responses.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(
            dict.fromkeys(
                [
                    *settings.cors_origins,
                    "https://heyceaser.in",
                    "https://www.heyceaser.in",
                    "ceaser-app://bundle",
                ]
            )
        ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-Request-Id",
            "X-Process-Time-Ms",
            "X-Database-Time-Ms",
            "X-Database-Query-Count",
            "Server-Timing",
        ],
        max_age=600,
    )

    @app.exception_handler(AIServiceUnavailableError)
    async def ai_service_unavailable_handler(request: Request, exc: AIServiceUnavailableError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": exc.public_message})

    @app.exception_handler(SQLAlchemyTimeoutError)
    async def database_pool_timeout_handler(request: Request, exc: SQLAlchemyTimeoutError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.warning("database_pool_timeout path=%s request_id=%s", request.url.path, request_id)
        return JSONResponse(
            status_code=503,
            content={"detail": "CEASER is temporarily busy. Please try again in a moment."},
            headers={"X-Request-Id": request_id or "", "Retry-After": "5"},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.exception("unhandled_request_error path=%s request_id=%s", request.url.path, request_id)
        origin = request.headers.get("origin")
        allowed_origins = {
            *settings.cors_origins,
            "https://heyceaser.in",
            "https://www.heyceaser.in",
            "ceaser-app://bundle",
        }
        headers = {"X-Request-Id": request_id or ""}
        if origin in allowed_origins:
            headers["Access-Control-Allow-Origin"] = origin
            headers["Access-Control-Allow-Credentials"] = "true"
            headers["Vary"] = "Origin"
        return JSONResponse(
            status_code=500,
            content={"detail": "We couldn't complete your request. Please try again."},
            headers=headers,
        )

    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(admin_internships_router)
    app.include_router(automations_router)
    app.include_router(agents_router)
    app.include_router(capabilities_router)
    app.include_router(conversations_router)
    app.include_router(credits_router)
    app.include_router(documents_router)
    app.include_router(desktop_router)
    app.include_router(drafts_router)
    app.include_router(agent_workbenches_router)
    app.include_router(messages_router)
    app.include_router(chat_router)
    app.include_router(ceaser_router)
    app.include_router(certificates_router)
    app.include_router(cloud_router)
    app.include_router(billing_router)
    app.include_router(commercial_router)
    app.include_router(memories_router)
    app.include_router(projects_router)
    app.include_router(files_router)
    app.include_router(integrations_router)
    app.include_router(knowledge_router)
    app.include_router(live_router)
    app.include_router(research_router)
    app.include_router(voice_router)
    app.include_router(waitlist_router)
    app.include_router(workflows_router)

    @app.get("/")
    def root() -> dict:
        return {"service": "CEASER API", "status": "online", "version": app.version}

    @app.get("/health")
    @app.get("/health/live")
    def health() -> dict:
        return {"status": "healthy", "service": "ceaser-api", "version": app.version}

    @app.get("/health/ready")
    def readiness() -> dict:
        started = perf_counter()
        try:
            with SessionLocal() as db:
                db.execute(text("SELECT 1"))
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail={"status": "not_ready", "database": "unavailable", "reason": exc.__class__.__name__},
            ) from exc
        return {
            "status": "ready",
            "database": "ready",
            "auth": "configured" if settings.supabase_url and settings.supabase_anon_key else "not_configured",
            "ai": "configured" if settings.openai_api_key or settings.gemini_api_key else "not_configured",
            "voice": "configured" if settings.deepgram_api_key else "not_configured",
            "automation_worker": automation_worker.state.as_dict(),
            "latency_ms": round((perf_counter() - started) * 1000),
        }

    return app


app = create_app()
