from collections.abc import Generator
from contextvars import ContextVar
from time import perf_counter
from dataclasses import dataclass, field
from threading import Lock

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config.settings import settings

_is_sqlite = settings.database_url.startswith("sqlite")
@dataclass
class _DatabaseTiming:
    count: int = 0
    milliseconds: float = 0.0
    request_id: str | None = None
    lock: Lock = field(default_factory=Lock)


# Worker threads inherit the request context, but not subsequent ContextVar sets.
# Share only this request's accumulator across those copied contexts.
_database_timing: ContextVar[_DatabaseTiming | None] = ContextVar("database_timing", default=None)
_engine_options = {"pool_pre_ping": True}
if _is_sqlite:
    _engine_options["connect_args"] = {"check_same_thread": False}
    if settings.database_url.rstrip("/") == "sqlite:":
        _engine_options["poolclass"] = StaticPool
else:
    _engine_options.update(
        pool_size=max(1, settings.database_pool_size),
        max_overflow=max(0, settings.database_max_overflow),
        pool_timeout=max(0.1, settings.database_pool_timeout_seconds),
        pool_recycle=max(1, settings.database_pool_recycle_seconds),
    )

engine = create_engine(settings.database_url, **_engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def begin_database_timing(request_id: str | None = None):
    return _database_timing.set(_DatabaseTiming(request_id=request_id))


def database_request_id() -> str | None:
    timing = _database_timing.get()
    return timing.request_id if timing is not None else None


def database_timing() -> tuple[int, float]:
    timing = _database_timing.get()
    if timing is None:
        return 0, 0.0
    with timing.lock:
        return timing.count, round(timing.milliseconds, 2)


def end_database_timing(tokens) -> None:
    _database_timing.reset(tokens)


@event.listens_for(engine, "before_cursor_execute")
def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._ceaser_query_started_at = perf_counter()


@event.listens_for(engine, "after_cursor_execute")
def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    started_at = getattr(context, "_ceaser_query_started_at", None)
    timing = _database_timing.get()
    if started_at is not None and timing is not None:
        with timing.lock:
            timing.count += 1
            timing.milliseconds += (perf_counter() - started_at) * 1000


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
