import asyncio
import threading

import pytest

from app.core.database.execution import run_serial_db


def test_blocking_database_work_does_not_block_event_loop():
    async def scenario():
        entered, release = threading.Event(), threading.Event()
        main_thread = threading.get_ident()

        def operation():
            assert threading.get_ident() != main_thread
            entered.set()
            assert release.wait(2), "event loop could not release blocked DB worker"
            return 42

        task = asyncio.create_task(run_serial_db(operation))
        try:
            while not entered.is_set():
                await asyncio.sleep(.001)
            release.set()
            assert await task == 42
        finally:
            release.set()

    asyncio.run(scenario())


def test_cancellation_waits_for_database_owner_before_cleanup():
    async def scenario():
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()

        def operation():
            entered.set()
            release.wait(2)
            finished.set()

        task = asyncio.create_task(run_serial_db(operation))
        try:
            while not entered.is_set():
                await asyncio.sleep(.001)
            task.cancel()
            await asyncio.sleep(.01)
            assert not task.done()
            task.cancel()
            await asyncio.sleep(.01)
            assert not task.done()
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert finished.is_set()
        finally:
            release.set()

    asyncio.run(scenario())


def test_database_exception_reaches_caller():
    def fail():
        raise ValueError("transaction failed")

    with pytest.raises(ValueError, match="transaction failed"):
        asyncio.run(run_serial_db(fail))
def test_measured_db_call_preserves_result_and_reports_components():
    from unittest.mock import patch
    from time import perf_counter
    from app.core.database.execution import measured_db_call

    with patch("app.core.database.execution.logger.info") as log:
        assert measured_db_call(lambda: 42, perf_counter()) == 42
    log.assert_called_once()
    for field in ("queue_ms=", "worker_ms=", "sql_ms=", "queries=", "non_sql_ms="):
        assert field in log.call_args.args[0]
