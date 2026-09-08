import asyncio
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models import ApiKeyScope, ApiKeyUsage, Workspace
from relaydesk.services import api_keys, api_usage
from tests.factories import make_workspace


async def _key(db_session, name="Production ingest"):
    workspace = await make_workspace(db_session, slug=name.lower().replace(" ", "-"))
    _, key = await api_keys.mint(
        db_session,
        workspace.id,
        name=name,
        scopes=[ApiKeyScope.conversations_read],
        created_by_user_id=None,
    )
    return key


async def test_calls_under_the_limit_are_allowed(db_session) -> None:
    key = await _key(db_session)

    for _ in range(3):
        allowed, _remaining = await api_usage.charge(db_session, key.id, limit=3)
        assert allowed


async def test_remaining_counts_down(db_session) -> None:
    key = await _key(db_session)

    _, first = await api_usage.charge(db_session, key.id, limit=3)
    _, second = await api_usage.charge(db_session, key.id, limit=3)

    assert (first, second) == (2, 1)


async def test_the_call_over_the_limit_is_refused(db_session) -> None:
    key = await _key(db_session)
    for _ in range(3):
        await api_usage.charge(db_session, key.id, limit=3)

    allowed, remaining = await api_usage.charge(db_session, key.id, limit=3)

    assert not allowed
    assert remaining == 0


async def test_two_keys_have_separate_allowances(db_session) -> None:
    ours = await _key(db_session, name="Ours")
    theirs = await _key(db_session, name="Theirs")
    for _ in range(3):
        await api_usage.charge(db_session, ours.id, limit=3)

    allowed, _ = await api_usage.charge(db_session, theirs.id, limit=3)

    assert allowed


async def test_one_row_per_key_per_window(db_session) -> None:
    key = await _key(db_session)

    for _ in range(5):
        await api_usage.charge(db_session, key.id, limit=100)

    rows = list(
        await db_session.scalars(
            sa.select(ApiKeyUsage).where(ApiKeyUsage.api_key_id == key.id)
        )
    )
    assert len(rows) == 1
    assert rows[0].count == 5


async def test_concurrent_charges_are_all_counted(db_session, engine) -> None:
    """The whole reason this exists rather than reusing ``ratelimit.check``.

    Ten callers arriving together must produce a count of ten, not a count
    of one repeated ten times -- and must do it without an advisory lock
    serialising them.

    This test opens its own session against ``engine`` -- rather than using
    ``db_session`` -- to create its workspace and key, and commits genuinely.
    ``db_session`` binds to a connection inside an outer transaction using
    ``join_transaction_mode="create_savepoint"``; its ``commit()`` only
    releases a savepoint, so the outer transaction stays open and rolls back
    at teardown, and no other connection would ever see those rows. The ten
    concurrent sessions below are separate connections, so the key's
    workspace and the key itself have to be real, committed rows or every
    concurrent insert would fail its foreign key. Because these writes are
    real and are not rolled back by any fixture, the test cleans up after
    itself at the end.
    """
    async with AsyncSession(bind=engine, expire_on_commit=False) as setup_session:
        workspace = await make_workspace(setup_session, slug="concurrent-callers")
        _, key = await api_keys.mint(
            setup_session,
            workspace.id,
            name="Concurrent callers",
            scopes=[ApiKeyScope.conversations_read],
            created_by_user_id=None,
        )
        await setup_session.commit()
        key_id = key.id

    async def charge_once() -> None:
        async with AsyncSession(bind=engine, expire_on_commit=False) as session:
            await api_usage.charge(session, key_id, limit=100)

    try:
        await asyncio.gather(*(charge_once() for _ in range(10)))

        async with engine.connect() as connection:
            total = await connection.scalar(
                sa.select(sa.func.sum(ApiKeyUsage.__table__.c.count)).where(
                    ApiKeyUsage.__table__.c.api_key_id == key_id
                )
            )
        assert total == 10
    finally:
        async with AsyncSession(bind=engine, expire_on_commit=False) as cleanup_session:
            await cleanup_session.execute(
                sa.delete(Workspace).where(Workspace.id == workspace.id)
            )
            await cleanup_session.commit()


async def test_sweep_drops_windows_older_than_the_retention(db_session) -> None:
    key = await _key(db_session)
    db_session.add(
        ApiKeyUsage(
            api_key_id=key.id,
            window_start=datetime.now(UTC) - timedelta(days=2),
            count=7,
        )
    )
    await db_session.commit()
    await api_usage.charge(db_session, key.id, limit=100)

    dropped = await api_usage.sweep(db_session, timedelta(days=1))

    assert dropped == 1
    remaining = list(
        await db_session.scalars(
            sa.select(ApiKeyUsage).where(ApiKeyUsage.api_key_id == key.id)
        )
    )
    assert len(remaining) == 1


async def test_usage_in_a_previous_window_does_not_count_against_this_one(
    db_session,
) -> None:
    """The behaviour that matters operationally, and nothing covered it.

    A key that spends its whole allowance gets it back at the top of the
    next minute. If that broke, a key would be locked out permanently after
    120 calls and the suite would stay green -- every other test here spends
    a single window, and ``sa.func.now()`` is the transaction timestamp, so
    ``date_trunc('minute', now())`` cannot advance inside one test.

    Seeding an exhausted row for the *previous* window is the way around
    that: the clock never has to move, because the second window is already
    in the table. ``interval '1 minute'`` back from Postgres's own
    ``date_trunc('minute', now())`` is used rather than a Python timestamp,
    so the row lands exactly one window before the one ``charge`` will
    compute for itself.
    """
    key = await _key(db_session)
    previous_window = await db_session.scalar(
        sa.select(
            sa.func.date_trunc("minute", sa.func.now())
            - sa.text("interval '1 minute'")
        )
    )
    db_session.add(
        ApiKeyUsage(api_key_id=key.id, window_start=previous_window, count=3)
    )
    await db_session.commit()

    allowed, remaining = await api_usage.charge(db_session, key.id, limit=3)

    assert allowed
    # 2, not 0: the fresh window starts at one, and the exhausted window
    # behind it contributes nothing.
    assert remaining == 2
    rows = list(
        await db_session.scalars(
            sa.select(ApiKeyUsage)
            .where(ApiKeyUsage.api_key_id == key.id)
            .order_by(ApiKeyUsage.window_start)
        )
    )
    assert [row.count for row in rows] == [3, 1]


async def test_a_charge_lands_in_the_current_minutes_window(db_session) -> None:
    """Pins the window *granularity*, which nothing else here does.

    ``charge``'s truncation could be widened from ``'minute'`` to ``'day'``
    and every other test in this file would still pass, because each spends
    exactly one window and a wider window is still one window. The limit
    would then be 120 calls a day. Comparing the stored ``window_start``
    against Postgres's own ``date_trunc('minute', now())`` is what makes
    that change fail a test.
    """
    key = await _key(db_session)

    await api_usage.charge(db_session, key.id, limit=100)

    stored = await db_session.scalar(
        sa.select(ApiKeyUsage.window_start).where(ApiKeyUsage.api_key_id == key.id)
    )
    expected = await db_session.scalar(
        sa.select(sa.func.date_trunc("minute", sa.func.now()))
    )
    assert stored == expected
