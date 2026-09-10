import pytest
import sqlalchemy as sa

from relaydesk.models.conversation import Conversation
from relaydesk.services import widget_keys
from tests.factories import make_workspace


async def test_submission_creates_a_conversation(client, db_session):
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    await db_session.commit()

    response = await client.post(
        f"/api/widget/{key.key}/tickets",
        data={"email": "wren@lantern.co", "subject": "Refund", "message": "Hello"},
    )
    assert response.status_code == 201

    count = await db_session.scalar(
        sa.select(sa.func.count())
        .select_from(Conversation)
        .where(Conversation.workspace_id == workspace.id)
    )
    assert count == 1


async def test_per_key_cap_refuses_beyond_its_budget(client, db_session, monkeypatch):
    """One abused embed exhausts its own budget, not the workspace's."""
    from relaydesk.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("WIDGET_KEY_HOURLY_CAP", "2")

    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    await db_session.commit()

    for index in range(2):
        accepted = await client.post(
            f"/api/widget/{key.key}/tickets",
            data={"email": f"a{index}@lantern.co", "message": "Hello"},
        )
        assert accepted.status_code == 201

    refused = await client.post(
        f"/api/widget/{key.key}/tickets",
        data={"email": "c@lantern.co", "message": "Hello"},
    )
    assert refused.status_code == 429
    get_settings.cache_clear()
