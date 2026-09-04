import asyncio

from relaydesk.worker import bridge


def test_run_executes_a_coroutine_and_returns_its_value() -> None:
    async def answer() -> int:
        return 42

    bridge.init_worker_process()
    assert bridge.run(answer()) == 42


def test_run_reuses_one_event_loop_across_calls() -> None:
    """asyncpg binds connections to the loop that created them, so a fresh
    loop per task would discard the pool every time. One loop per process is
    what makes the engine reusable."""

    async def current_loop() -> asyncio.AbstractEventLoop:
        return asyncio.get_running_loop()

    bridge.init_worker_process()
    first = bridge.run(current_loop())
    second = bridge.run(current_loop())

    assert first is second


def test_run_before_init_is_a_clear_error() -> None:
    async def noop() -> None:
        return None

    bridge.reset_for_tests()
    try:
        raised = None
        try:
            bridge.run(noop())
        except RuntimeError as error:
            raised = error
        assert raised is not None
        assert "init_worker_process" in str(raised)
    finally:
        bridge.init_worker_process()
