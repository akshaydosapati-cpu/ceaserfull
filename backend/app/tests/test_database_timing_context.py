import asyncio
from types import SimpleNamespace
from time import perf_counter

from app.core.database.session import (
    _after_cursor_execute,
    begin_database_timing,
    database_timing,
    end_database_timing,
)


def record_query():
    context = SimpleNamespace(_ceaser_query_started_at=perf_counter() - 0.001)
    _after_cursor_execute(None, None, None, None, context, False)


def test_worker_query_timings_reach_request_and_remain_isolated():
    async def request():
        token = begin_database_timing()
        try:
            await asyncio.gather(*(asyncio.to_thread(record_query) for _ in range(3)))
            count, milliseconds = database_timing()
            assert count == 3
            assert milliseconds >= 3
        finally:
            end_database_timing(token)
        assert database_timing() == (0, 0.0)

    async def run():
        await asyncio.gather(request(), request())

    asyncio.run(run())
