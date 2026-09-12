"""Reading and writing one workspace's model configuration.

The key is write-only throughout: ``get_or_create`` returns the row, and it
is the schema layer that refuses to serialise ``api_key``. Keeping that
refusal in one place -- ``AiConfigOut`` has no field for it -- is what stops
a future endpoint leaking it by accident.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Invalid
from relaydesk.models.ai_config import AiConfig


async def get_or_create(session: AsyncSession, workspace_id: uuid.UUID) -> AiConfig:
    config = await session.get(AiConfig, workspace_id)
    if config is None:
        config = AiConfig(workspace_id=workspace_id)
        session.add(config)
        await session.flush()
    return config


async def update(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    daily_token_budget: int | None = None,
    enabled: bool | None = None,
) -> AiConfig:
    config = await get_or_create(session, workspace_id)
    if provider is not None:
        config.provider = provider
    if model is not None:
        config.model = model.strip()
    if api_key is not None:
        # An empty string is how the console clears a key; omitting the
        # field entirely leaves the installed one alone.
        config.api_key = api_key.strip() or None
    if base_url is not None:
        config.base_url = base_url.strip() or None
    if daily_token_budget is not None:
        if daily_token_budget < 0:
            raise Invalid("A budget cannot be negative.")
        config.daily_token_budget = daily_token_budget
    if enabled is not None:
        config.enabled = enabled
    await session.flush()
    return config
