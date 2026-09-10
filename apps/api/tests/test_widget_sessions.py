import uuid

import pytest
import sqlalchemy as sa

from relaydesk.models.widget_session import WidgetSession
from relaydesk.services import widget_keys, widget_sessions
from tests.factories import make_workspace


async def test_first_event_opens_the_session(db_session):
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    session_id = uuid.uuid4()

    await widget_sessions.record(db_session, key, session_id, "searched")

    row = await db_session.scalar(
        sa.select(WidgetSession).where(WidgetSession.id == session_id)
    )
    assert row.searched is True
    assert row.submitted is False
    assert row.workspace_id == workspace.id


async def test_repeating_an_event_writes_one_row(db_session):
    """A visitor who searches four times is one session, not four."""
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    session_id = uuid.uuid4()

    for _ in range(4):
        await widget_sessions.record(db_session, key, session_id, "searched")

    count = await db_session.scalar(
        sa.select(sa.func.count()).select_from(WidgetSession)
    )
    assert count == 1


async def test_flags_accumulate_and_never_lower(db_session):
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    session_id = uuid.uuid4()

    await widget_sessions.record(db_session, key, session_id, "searched")
    await widget_sessions.record(db_session, key, session_id, "read")
    await widget_sessions.record(db_session, key, session_id, "submitted")

    row = await db_session.scalar(
        sa.select(WidgetSession).where(WidgetSession.id == session_id)
    )
    assert (row.searched, row.read_article, row.submitted) == (True, True, True)


async def test_an_unknown_kind_is_refused(db_session):
    from relaydesk.errors import Invalid

    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")

    with pytest.raises(Invalid):
        await widget_sessions.record(db_session, key, uuid.uuid4(), "purchased")


async def test_the_route_commits_the_flag(client, db_session):
    """A route test, not just a service test: this slice already shipped an
    uncommitted-flush defect twice, and only a request through `client`
    exercises the same session lifecycle a real visitor's request does."""
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    await db_session.commit()
    session_id = uuid.uuid4()

    response = await client.post(
        f"/api/widget/{key.key}/sessions/{session_id}", json={"kind": "searched"}
    )

    assert response.status_code == 204
    row = await db_session.scalar(
        sa.select(WidgetSession).where(WidgetSession.id == session_id)
    )
    assert row is not None
    assert row.searched is True


async def test_the_route_refuses_an_unknown_kind(client, db_session):
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    await db_session.commit()

    response = await client.post(
        f"/api/widget/{key.key}/sessions/{uuid.uuid4()}", json={"kind": "purchased"}
    )

    assert response.status_code == 422


async def test_the_route_404s_for_an_unknown_key(client, db_session):
    response = await client.post(
        f"/api/widget/rdw_{'0' * 32}/sessions/{uuid.uuid4()}",
        json={"kind": "searched"},
    )

    assert response.status_code == 404
