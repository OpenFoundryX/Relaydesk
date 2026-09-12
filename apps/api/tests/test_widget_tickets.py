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


async def test_submit_really_commits(client, db_session, commit_spy) -> None:
    """`submit` must commit its own write, not just flush it.

    `get_session` has no commit-on-exit, so an uncommitted flush vanishes
    when the request ends and the ticket silently never exists. The shared
    -session `client` fixture hides exactly this: a bare flush is already
    visible to every other assertion in this file, committed or not,
    because it is the same session and the same transaction. `commit_spy`
    is the one thing here that can tell the two apart -- see
    `test_widget_keys_api.py::test_create_really_commits`.

    Asserted as ``>= 3`` rather than ``>= 1``: `ratelimit.check` commits on
    its own (it must -- a charge has to outlive a request refused further
    down), and this route calls it twice before it ever reaches
    `tickets.submit`, so those two commits alone would satisfy a bare
    ``>= 1`` even with the route's own commit deleted entirely. Only a
    count that has to include the route's *own* commit -- the two rate
    -limit commits plus this one -- actually pins it.
    """
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    await db_session.commit()
    commit_spy.clear()  # The setup above commits too.

    response = await client.post(
        f"/api/widget/{key.key}/tickets",
        data={"email": "wren@lantern.co", "message": "Hello"},
    )

    assert response.status_code == 201, response.text
    assert len(commit_spy) >= 3


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
