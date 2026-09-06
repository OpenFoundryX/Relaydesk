from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models.rate_limit import RateLimitHit


async def check(
    session: AsyncSession,
    bucket: str,
    key: str,
    *,
    limit: int,
    window: timedelta,
) -> bool:
    """Record a call and say whether the caller is still within the limit.

    Counted in Postgres rather than in process memory on purpose: the API
    runs several workers, and a per-process counter would hand each of them
    its own allowance, multiplying the real limit by the worker count.
    """
    since = datetime.now(UTC) - window
    used = await session.scalar(
        sa.select(sa.func.count())
        .select_from(RateLimitHit)
        .where(
            RateLimitHit.bucket == bucket,
            RateLimitHit.key == key,
            RateLimitHit.created_at >= since,
        )
    )
    if int(used or 0) >= limit:
        return False

    session.add(RateLimitHit(bucket=bucket, key=key[:64]))
    await session.flush()
    return True
