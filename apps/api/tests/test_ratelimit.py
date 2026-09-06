import asyncio
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
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


async def test_concurrent_callers_sharing_a_key_cannot_exceed_the_limit(
    engine,
) -> None:
    """The limit must hold against parallel requests, not just sequential ones.

    Counting and then inserting is two statements. Under READ COMMITTED --
    Postgres's default, and what this application runs on -- N transactions
    that all count before any of them commits all read the same pre-insert
    total, all find room, and all insert. The effective cap becomes the
    attacker's connection count rather than `limit`, which for the public
    ticket form means its only real abuse control does not exist: the
    submitter's address is never attested, so the per-email cap is evaded
    by varying it and this IP cap is all there is.

    Every other test in this file runs through the suite's `db_session`
    fixture, which is one session on one connection driven sequentially --
    a shape in which this bug is invisible by construction. So this test
    deliberately does not use that fixture. It takes `engine` directly and
    gives each caller its own `AsyncSession`, and therefore its own pooled
    connection and its own transaction, and runs them under
    `asyncio.gather`.

    The `asyncio.Barrier` is what makes the failure deterministic rather
    than a race the scheduler might happen to lose: each caller opens its
    transaction with a round trip *first*, then waits, so every one of them
    is provably inside an open transaction before any of them counts.
    Against the unfixed implementation all eight are allowed; against the
    advisory-lock implementation they serialise on the key and exactly
    `limit` are.

    Nothing here is rolled back for us -- these sessions commit for real --
    so the bucket is unique to this test and the rows are deleted at the
    end.
    """
    bucket = "concurrency-probe"
    key = "203.0.113.44"
    limit = 3
    callers = 8

    barrier = asyncio.Barrier(callers)

    async def attempt() -> bool:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            # Force the connection out of the pool and the transaction open
            # before the barrier, so waiting on it means "everyone is in a
            # transaction", not "everyone is about to ask for a connection".
            await session.execute(sa.select(sa.literal(1)))
            await barrier.wait()
            return await ratelimit.check(
                session, bucket, key, limit=limit, window=WINDOW
            )

    try:
        outcomes = await asyncio.gather(*(attempt() for _ in range(callers)))

        assert sum(outcomes) == limit, (
            f"{sum(outcomes)} of {callers} concurrent callers were allowed "
            f"through a limit of {limit}"
        )

        async with AsyncSession(engine) as session:
            recorded = await session.scalar(
                sa.select(sa.func.count())
                .select_from(RateLimitHit)
                .where(RateLimitHit.bucket == bucket)
            )
        assert recorded == limit
    finally:
        async with AsyncSession(engine) as session:
            await session.execute(
                sa.delete(RateLimitHit).where(RateLimitHit.bucket == bucket)
            )
            await session.commit()


async def test_concurrent_callers_on_different_keys_all_get_their_own_allowance(
    engine,
) -> None:
    """The lock serialises one key, not the endpoint.

    A lock taken on something coarser -- the bucket, or a single global id
    -- would still pass the test above while quietly turning every
    concurrent submission from unrelated visitors into a queue behind one
    another. This pins that different keys do not block each other and each
    keeps a full allowance.
    """
    bucket = "concurrency-probe-keys"
    callers = 6
    barrier = asyncio.Barrier(callers)

    async def attempt(index: int) -> bool:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            await session.execute(sa.select(sa.literal(1)))
            await barrier.wait()
            return await ratelimit.check(
                session, bucket, f"198.51.100.{index}", limit=1, window=WINDOW
            )

    try:
        outcomes = await asyncio.gather(*(attempt(i) for i in range(callers)))
        assert all(outcomes)
    finally:
        async with AsyncSession(engine) as session:
            await session.execute(
                sa.delete(RateLimitHit).where(RateLimitHit.bucket == bucket)
            )
            await session.commit()


async def test_the_charge_is_committed_by_check_itself(engine) -> None:
    """`check` commits; a caller does not have to remember to.

    The charge has to outlive the request that earned it whatever that
    request goes on to do -- the portal answers a caught honeypot with a
    fake 201 and refuses an over-cap address with a 429, and both of those
    end the request without reaching any commit of their own. Leaving the
    commit to the call site meant exactly one code path was proven to have
    it; a second caller omitting it would reintroduce a fixed Critical with
    a green suite. This asserts the contract at the service, where every
    caller inherits it.
    """
    bucket = "commit-probe"
    key = "203.0.113.55"
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            assert await ratelimit.check(
                session, bucket, key, limit=1, window=WINDOW
            )
            # No commit here, and the session is closed -- which rolls back
            # anything uncommitted, exactly as `get_session` does at the end
            # of a request.

        async with AsyncSession(engine) as session:
            recorded = await session.scalar(
                sa.select(sa.func.count())
                .select_from(RateLimitHit)
                .where(RateLimitHit.bucket == bucket)
            )
        assert recorded == 1
    finally:
        async with AsyncSession(engine) as session:
            await session.execute(
                sa.delete(RateLimitHit).where(RateLimitHit.bucket == bucket)
            )
            await session.commit()


async def test_the_window_start_is_computed_by_the_database(
    db_session: AsyncSession, engine
) -> None:
    """A regression pin on *where* the window's start comes from.

    `created_at` is filled in by Postgres's `now()`. If the window's start
    were computed from the app process's clock instead, an app clock
    running ahead of the database's by more than the window would put every
    existing hit outside it -- the count would always be zero and the limit
    would silently never fire, with nothing there to notice it.

    Stated plainly: this asserts the mechanism, not the behaviour. The
    behaviour is unobservable from here, because the app and the database
    share a clock in this environment and nothing in a test can skew one
    against the other. What it does catch is a revert to an app-side
    `since` -- which is the only way the bug comes back -- and it catches
    it by reading the SQL `check` actually sent, not SQL the test built
    for itself.
    """
    statements: list[str] = []

    def record(_conn, _cursor, statement, _params, _context, _many) -> None:
        statements.append(statement)

    sa.event.listen(engine.sync_engine, "before_cursor_execute", record)
    try:
        await ratelimit.check(
            db_session, "clock", "203.0.113.9", limit=1, window=WINDOW
        )
    finally:
        sa.event.remove(engine.sync_engine, "before_cursor_execute", record)

    counts = [s for s in statements if "count(" in s and "rate_limit_hits" in s]
    assert counts, f"no count query was issued; saw {statements}"
    assert all("now()" in s for s in counts), counts


async def test_the_sweep_deletes_only_hits_past_the_retention(
    db_session: AsyncSession,
) -> None:
    """Nothing else deletes these rows, and every allowed call adds one.

    Including every submission the portal's honeypot catches, which is
    answered with a fake success and so leaves nothing else behind -- so
    without a sweeper the table only ever grows, and the model's docstring
    claiming rows are "swept by age" was simply untrue.
    """
    db_session.add_all(
        [
            RateLimitHit(
                bucket="sweep",
                key="stale",
                created_at=datetime.now(UTC) - timedelta(days=2),
            ),
            RateLimitHit(
                bucket="sweep",
                key="fresh",
                created_at=datetime.now(UTC) - timedelta(minutes=1),
            ),
        ]
    )
    await db_session.flush()

    removed = await ratelimit.sweep(db_session, timedelta(days=1))

    assert removed == 1
    survivors = (
        await db_session.scalars(
            sa.select(RateLimitHit.key).where(RateLimitHit.bucket == "sweep")
        )
    ).all()
    assert list(survivors) == ["fresh"]


def test_the_sweep_is_on_the_beat_schedule() -> None:
    """A sweeper nothing schedules is the same as no sweeper at all."""
    from relaydesk.worker.app import app

    assert "relaydesk.sweep_rate_limits" in app.tasks
    scheduled = {
        entry["task"] for entry in app.conf.beat_schedule.values()
    }
    assert "relaydesk.sweep_rate_limits" in scheduled
