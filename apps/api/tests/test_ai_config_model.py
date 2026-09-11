import pytest
import sqlalchemy as sa

from relaydesk.models.ai_config import AiConfig
from tests.factories import make_workspace


async def test_defaults_are_off_and_unconfigured(db_session) -> None:
    """A workspace that has never touched AI must look exactly like one that never will."""
    workspace = await make_workspace(db_session)
    config = AiConfig(workspace_id=workspace.id)
    db_session.add(config)
    await db_session.flush()

    assert config.enabled is False
    assert config.api_key is None
    assert config.model == "claude-opus-5"
    assert config.provider == "anthropic"
    assert config.daily_token_budget == 200_000


async def test_one_config_per_workspace(db_session) -> None:
    workspace = await make_workspace(db_session)
    db_session.add(AiConfig(workspace_id=workspace.id))
    await db_session.flush()
    db_session.add(AiConfig(workspace_id=workspace.id))

    with pytest.raises(sa.exc.IntegrityError):
        await db_session.flush()
