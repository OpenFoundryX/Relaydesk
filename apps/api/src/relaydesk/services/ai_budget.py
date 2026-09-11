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
