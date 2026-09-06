import hashlib
from datetime import timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models.rate_limit import RateLimitHit


def _lock_id(bucket: str, key: str) -> int:
    """One 64-bit lock per ``bucket:key``, for ``pg_advisory_xact_lock``.

    Hashed rather than derived from the string some other way because the
    lock space is a single flat int64 namespace shared by the whole
    database: two different keys colliding costs only a little needless
    serialisation, whereas two different keys *not* mapping to distinct
    locks would be a correctness bug.
    """
    digest = hashlib.blake2b(f"{bucket}:{key}".encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big", signed=True)


async def check(
    session: AsyncSession,
    bucket: str,
    key: str,
    *,
    limit: int,
    window: timedelta,
) -> bool:
    """Record a call and say whether the caller is still within the limit.

    **This commits.** The charge has to outlive the request that earned it
    whatever else that request goes on to do -- a caller refused further
    down (the honeypot, the per-email cap) must still have paid for the
    call it just made, and `get_session` rolls back any session that ends
    without an explicit commit. Committing here rather than leaving it to
    the caller is deliberate: a second caller that forgot the commit would
    silently reintroduce that hole with a green suite, and would *also*
    hold the advisory lock taken below for the rest of its request,
    stalling every other caller sharing the key. Both failure modes are
    invisible at the call site, so neither is left to it.

    The cost of that choice is the usual one for a service that commits:
    anything else already pending on this session is committed with it, so
    call this before the writes a request might want to roll back, not
    after. The portal router does -- nothing is pending there but reads.

    Counted in Postgres rather than in process memory on purpose: the API
    runs several workers, and a per-process counter would hand each of them
    its own allowance, multiplying the real limit by the worker count.
    """
    # Truncated once, up front, so the lookup, the insert and the lock all
    # agree on the same value -- counting the raw key while storing the
    # truncated one would let any key longer than the column width dodge
    # the limit forever, since its stored rows could never match the
    # untruncated lookup.
    key = key[:64]

    # Serialise same-key callers *before* the count. Counting and then
    # inserting is not atomic on its own: under READ COMMITTED, N
    # concurrent requests sharing a key all read the same pre-insert count,
    # all find room, and all insert -- so the effective cap becomes the
    # attacker's connection count rather than `limit`. Since the address is
    # never attested and the per-email cap is evaded by varying the address,
    # this IP limit is the only real abuse control the public ticket form
    # has, and a 40x multiplier on it is the same as not having one.
    #
    # A transaction-scoped advisory lock is the cheapest fix that keeps
    # different keys running in parallel: it takes no row locks, blocks
    # only callers hashing to the same `bucket:key`, and Postgres drops it
    # when the transaction ends -- which the commit below makes happen one
    # round trip later, on both the allowed and the refused path.
    await session.execute(
        sa.select(sa.func.pg_advisory_xact_lock(_lock_id(bucket, key)))
    )

    used = await session.scalar(
        sa.select(sa.func.count())
        .select_from(RateLimitHit)
        .where(
            RateLimitHit.bucket == bucket,
            RateLimitHit.key == key,
            # The window's start is computed by Postgres, not by this
            # process. `created_at` is filled in by the database's `now()`;
            # if the app's clock ran ahead of the database's by more than
            # `window`, an app-computed `since` would put every existing
            # hit outside the window, the count would always be zero, and
            # the limit would silently never fire. One clock decides both
            # sides of the comparison.
            RateLimitHit.created_at >= sa.func.now() - sa.literal(window, sa.Interval),
        )
    )
    if int(used or 0) >= limit:
        # Nothing to persist, but the lock still has to go.
        await session.commit()
        return False

    session.add(RateLimitHit(bucket=bucket, key=key))
    await session.commit()
    return True


async def sweep(session: AsyncSession, older_than: timedelta) -> int:
    """Delete hits too old to count against any window, and say how many.

    Nothing ever reads an individual row, and every allowed call -- every
    caught honeypot submission included -- adds one, so without this the
    table only grows. Scheduled from `relaydesk.worker.app`'s beat
    schedule; `older_than` is expected to be a generous multiple of the
    longest window any caller of `check` uses, so a sweep can never race a
    live count.
    """
    result = await session.execute(
        sa.delete(RateLimitHit).where(
            RateLimitHit.created_at
            < sa.func.now() - sa.literal(older_than, sa.Interval)
        )
    )
    await session.commit()
    return int(result.rowcount or 0)
