import pytest
import sqlalchemy as sa

from relaydesk.models.widget_key import WidgetKey
from tests.factories import make_workspace


async def test_key_is_stored_verbatim(db_session):
    """The credential is public by construction; a digest could never be re-shown."""
    workspace = await make_workspace(db_session)
    db_session.add(
        WidgetKey(workspace_id=workspace.id, name="Marketing site", key="rdw_abc123")
    )
    await db_session.flush()

    stored = await db_session.scalar(sa.select(WidgetKey.key))
    assert stored == "rdw_abc123"


async def test_defaults_refuse_embedding(db_session):
    """An unconfigured key allows nobody -- empty means refuse, not permit."""
    workspace = await make_workspace(db_session)
    key = WidgetKey(workspace_id=workspace.id, name="Site", key="rdw_def456")
    db_session.add(key)
    await db_session.flush()

    assert key.allowed_origins == []
    assert key.settings == {}
    assert key.active is True
    assert key.last_seen_at is None


async def test_key_is_unique_across_workspaces(db_session):
    one = await make_workspace(db_session, slug="one")
    two = await make_workspace(db_session, slug="two")
    db_session.add(WidgetKey(workspace_id=one.id, name="A", key="rdw_same"))
    await db_session.flush()
    db_session.add(WidgetKey(workspace_id=two.id, name="B", key="rdw_same"))

    with pytest.raises(sa.exc.IntegrityError):
        await db_session.flush()
