import uuid
from datetime import timedelta

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models.api_usage import ApiKeyUsage


async def charge(
    session: AsyncSession, api_key_id: uuid.UUID, *, limit: int
) -> tuple[bool, int]:
    """Record one call and say whether the key is still within its limit.

    Returns ``(allowed, remaining)``.

    One statement, one round trip: the upsert increments the current
    window's row and returns the new count in the same breath. Because the
    increment happens inside the row's own lock, concurrent callers are
    counted correctly without an advisory lock and without serialising --
    which is the difference between this and ``services.ratelimit.check``.

    **This commits**, for the reason that function documents: the charge has
    to outlive the request that earned it whatever else that request goes on
    to do, and ``get_session`` rolls back a session that ends without an
    explicit commit. It is called from a dependency, before the route body
    runs, so nothing else is pending on the session when it does.

    The window boundary is computed by Postgres (``date_trunc`` over
    ``now()``), not by this process, for the reason spelled out in
    ``ratelimit.check``: one clock has to decide both sides of the
    comparison, or a skewed app clock silently disables the limit.

    A refused call is still counted. A caller already over the limit does
    not get free retries by being refused.
    """
    statement = (
        pg_insert(ApiKeyUsage)
        .values(
            api_key_id=api_key_id,
            window_start=sa.func.date_trunc("minute", sa.func.now()),
            count=1,
        )
        .on_conflict_do_update(
            index_elements=["api_key_id", "window_start"],
            set_={"count": ApiKeyUsage.count + 1},
        )
        .returning(ApiKeyUsage.count)
    )
    used = int(await session.scalar(statement) or 0)
    await session.commit()
    return used <= limit, max(limit - used, 0)


async def sweep(session: AsyncSession, older_than: timedelta) -> int:
    """Delete windows too old to count, and say how many.

    Nothing reads a closed window, and one row per key per minute adds up
    over a year. ``older_than`` is expected to be a generous multiple of the
    one-minute window so a sweep can never race a live count.
    """
    result = await session.execute(
        sa.delete(ApiKeyUsage).where(
            ApiKeyUsage.window_start
            < sa.func.now() - sa.literal(older_than, sa.Interval)
        )
    )
    await session.commit()
    return int(result.rowcount or 0)
