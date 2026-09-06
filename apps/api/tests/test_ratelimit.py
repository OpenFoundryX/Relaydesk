from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.services import ratelimit

WINDOW = timedelta(hours=1)


async def test_calls_under_the_limit_are_allowed(db_session: AsyncSession) -> None:
    for _ in range(3):
        assert await ratelimit.check(
            db_session, "tickets", "203.0.113.9", limit=3, window=WINDOW
        )


async def test_the_call_over_the_limit_is_refused(db_session: AsyncSession) -> None:
    for _ in range(3):
        await ratelimit.check(
            db_session, "tickets", "203.0.113.9", limit=3, window=WINDOW
        )
    assert not await ratelimit.check(
        db_session, "tickets", "203.0.113.9", limit=3, window=WINDOW
    )


async def test_two_callers_have_separate_allowances(db_session: AsyncSession) -> None:
    for _ in range(3):
        await ratelimit.check(
            db_session, "tickets", "203.0.113.9", limit=3, window=WINDOW
        )
    assert await ratelimit.check(
        db_session, "tickets", "198.51.100.1", limit=3, window=WINDOW
    )


async def test_two_buckets_have_separate_allowances(db_session: AsyncSession) -> None:
    for _ in range(3):
        await ratelimit.check(
            db_session, "tickets", "203.0.113.9", limit=3, window=WINDOW
        )
    assert await ratelimit.check(
        db_session, "other", "203.0.113.9", limit=3, window=WINDOW
    )


async def test_hits_outside_the_window_do_not_count(db_session: AsyncSession) -> None:
    """A caller who used the whole allowance yesterday starts today fresh."""
    for _ in range(3):
        await ratelimit.check(
            db_session, "tickets", "203.0.113.9", limit=3, window=timedelta(seconds=0)
        )
    assert await ratelimit.check(
        db_session, "tickets", "203.0.113.9", limit=3, window=timedelta(seconds=0)
    )
