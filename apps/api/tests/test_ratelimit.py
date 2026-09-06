from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models.rate_limit import RateLimitHit
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


async def test_hits_older_than_the_window_do_not_count(
    db_session: AsyncSession,
) -> None:
    """A caller who used their allowance two hours ago is fresh within one."""
    db_session.add(
        RateLimitHit(
            bucket="tickets",
            key="203.0.113.9",
            created_at=datetime.now(UTC) - timedelta(hours=2),
        )
    )
    await db_session.flush()

    assert await ratelimit.check(
        db_session, "tickets", "203.0.113.9", limit=1, window=timedelta(hours=1)
    )


async def test_hits_inside_the_window_still_count(db_session: AsyncSession) -> None:
    """The same two-hour-old hit still counts against a three-hour window."""
    db_session.add(
        RateLimitHit(
            bucket="tickets",
            key="203.0.113.9",
            created_at=datetime.now(UTC) - timedelta(hours=2),
        )
    )
    await db_session.flush()

    assert not await ratelimit.check(
        db_session, "tickets", "203.0.113.9", limit=1, window=timedelta(hours=3)
    )


async def test_keys_longer_than_the_column_are_still_limited(
    db_session: AsyncSession,
) -> None:
    """A key over 64 chars must be truncated the same way for both the
    lookup and the stored row -- otherwise a stored (truncated) hit can
    never match a lookup on the raw key, and that caller is never limited.
    """
    long_key = "203.0.113.9-" + "x" * 60
    assert len(long_key) > 64
    for _ in range(3):
        await ratelimit.check(db_session, "tickets", long_key, limit=3, window=WINDOW)
    assert not await ratelimit.check(
        db_session, "tickets", long_key, limit=3, window=WINDOW
    )
