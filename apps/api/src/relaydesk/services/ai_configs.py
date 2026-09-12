"""Reading and writing one workspace's model configuration.

The key is write-only throughout: ``get_or_create`` returns the row, and it
is the schema layer that refuses to serialise ``api_key``. Keeping that
refusal in one place -- ``AiConfigOut`` has no field for it -- is what stops
a future endpoint leaking it by accident.
"""

import uuid
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Invalid
from relaydesk.models.ai_config import AiConfig


def _validate_base_url(value: str) -> None:
    """Reject anything that is not an absolute ``https://`` URL.

    ``ai_provider.for_config`` passes ``base_url`` straight to the
    Anthropic client, unvalidated, and ``ai_answers`` treats its mere
    presence as a reason to skip PII redaction (spec D6). An admin who
    types a bare host, a typo, or an ``http://`` URL would have this
    workspace's provider key -- and every visitor question sent to it,
    redacted or not -- POSTed to whatever they typed, potentially in the
    clear. Requiring an absolute ``https`` URL closes the "in the clear"
    half of that and catches the malformed-input case with a 422 instead
    of the 500 an admin would otherwise get from deep inside
    ``anthropic.AsyncAnthropic``.

    Deliberately does **not** block private, loopback or link-local
    addresses (``http://localhost:11434``, ``https://10.0.0.4:8080``, a
    ``169.254.169.254`` metadata endpoint, and so on). Self-hosted
    inference on a workspace's own private network -- the entire reason
    this field exists, per ``AiConfig.base_url``'s docstring -- routes
    through exactly such an address, and blocking it would break the
    field for the deployments most likely to use it. Nothing here can
    verify that a given ``https`` host really is the workspace's own
    deployment rather than a third party the admin was tricked into
    typing -- that is a property of the admin's judgement, not of this
    function -- and the docstrings that used to claim otherwise have been
    corrected to say so.
    """
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise Invalid("Base URL must be an absolute https:// URL.")


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
        stripped = base_url.strip()
        if stripped:
            _validate_base_url(stripped)
        config.base_url = stripped or None
    if daily_token_budget is not None:
        if daily_token_budget < 0:
            raise Invalid("A budget cannot be negative.")
        config.daily_token_budget = daily_token_budget
    if enabled is not None:
        config.enabled = enabled
    await session.flush()
    return config
