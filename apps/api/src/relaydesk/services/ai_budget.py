"""The ceiling on what one workspace's widget can spend in a day.

An anonymous endpoint that costs money on every call is a different animal
from an anonymous endpoint that reads public rows, and anyone who views a
customer's page source is holding the key that reaches it. The per-key
hourly cap bounds a single embed; this bounds the workspace.

Deliberately a token count rather than a currency amount. Tokens are what
the provider reports and what this table records, so the ceiling is checked
against the same unit it is spent in, with no conversion to get wrong.
"""

import uuid
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models.ai_call import AiCall
from relaydesk.models.ai_config import AiConfig

WINDOW = timedelta(days=1)


async def spent_today(session: AsyncSession, workspace_id: uuid.UUID) -> int:
    since = datetime.now(UTC) - WINDOW
    total = await session.scalar(
        sa.select(
            sa.func.coalesce(
                sa.func.sum(AiCall.input_tokens + AiCall.output_tokens), 0
            )
        ).where(AiCall.workspace_id == workspace_id, AiCall.created_at >= since)
    )
    return int(total or 0)


async def within_budget(session: AsyncSession, config: AiConfig) -> bool:
    """Whether this workspace may make another call in the current window.

    Checked before the call rather than after it, so the ceiling is a
    ceiling rather than a report of one having been passed. The cost is
    that a single call can carry the total slightly beyond the limit; the
    alternative -- reserving tokens up front -- would need an estimate of
    output length that nothing can give honestly.
    """
    return await spent_today(session, config.workspace_id) < config.daily_token_budget


BREAKER_THRESHOLD = 5
BREAKER_WINDOW = timedelta(minutes=15)


async def breaker_open(session: AsyncSession, workspace_id: uuid.UUID) -> bool:
    """Whether recent provider failures should stop us calling out again.

    Counts only ``provider_unavailable``. A workspace that has not
    configured a key degrades on every request by design, and treating that
    as an outage would mean a breaker permanently open on a workspace that
    never had a provider to begin with.

    Closes on its own when the window rolls forward: there is no half-open
    probe because the next question after the window *is* the probe, and a
    visitor waiting on one is a cheaper test than a background job.

    Uses the same ``(workspace_id, created_at)`` index ``spent_today``
    does -- ``ix_ai_calls_workspace_created`` -- rather than declaring a
    second one over what is, for this query, the same leading columns.
    """
    since = datetime.now(UTC) - BREAKER_WINDOW
    failures = await session.scalar(
        sa.select(sa.func.count())
        .select_from(AiCall)
        .where(
            AiCall.workspace_id == workspace_id,
            AiCall.reason == "provider_unavailable",
            AiCall.created_at >= since,
        )
    )
    return int(failures or 0) >= BREAKER_THRESHOLD
