"""Await blocking session work without abandoning an in-flight transaction."""
import asyncio
import anyio
import logging
from time import perf_counter

from app.core.database.session import database_request_id, database_timing

logger = logging.getLogger(__name__)


def measured_db_call(function, submitted_at, *args, **kwargs):
    started = perf_counter()
    count_before, sql_before = database_timing()
    try:
        return function(*args, **kwargs)
    finally:
        worker_ms = (perf_counter() - started) * 1000
        count_after, sql_after = database_timing()
        sql_ms = max(0.0, sql_after - sql_before)
        # Residual includes acquisition/pre-ping, ORM work and transaction I/O;
        # it must not be reported as pool wait or network latency alone.
        logger.info(
            "ceaser_db_operation request_id=%s operation=%s queue_ms=%.2f worker_ms=%.2f "
            "sql_ms=%.2f queries=%s non_sql_ms=%.2f",
            database_request_id(), getattr(function, "__qualname__", type(function).__name__),
            (started - submitted_at) * 1000, worker_ms, sql_ms,
            max(0, count_after - count_before), max(0.0, worker_ms - sql_ms),
        )


async def run_serial_db(function, *args, **kwargs):
    task = asyncio.create_task(asyncio.to_thread(measured_db_call, function, perf_counter(), *args, **kwargs))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        # A cancelled HTTP request must not close/reuse the session while its
        # worker still owns it. Drain the operation before propagating cancellation.
        with anyio.CancelScope(shield=True):
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    break
        if not task.cancelled():
            task.exception()
        raise
