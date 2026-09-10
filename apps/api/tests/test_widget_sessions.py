import asyncio
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models.widget_session import WidgetSession
from relaydesk.models.workspace import Workspace
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


async def test_concurrent_events_on_one_session_do_not_conflict(engine):
    """Two real, independent connections raise different flags on the same
    session id at once -- the exact race ``record()``'s
    ``ON CONFLICT DO UPDATE`` exists to survive (see its docstring).

    Deliberately not built on ``db_session``: that fixture wraps every
    write in *one* connection's savepoint-nested transaction, rolled back
    at the end of the test, so two calls made through it only ever
    serialise on that single session and never reach the database as two
    independent transactions -- it cannot produce a genuine conflict, only
    a slower version of ``test_flags_accumulate_and_never_lower``. This
    test instead opens two separate connections against the same engine,
    each with its own ``AsyncSession`` and a real commit, so Postgres
    itself -- not this test's bookkeeping -- has to arbitrate the two
    upserts against one row. A read-then-write ``record()`` reliably fails
    this: both connections' reads can see no row yet, both then try to
    insert, and the second commit raises a primary-key violation instead
    of updating.
    """
    async with engine.connect() as setup_connection:
        setup_session = AsyncSession(bind=setup_connection, expire_on_commit=False)
        workspace = await make_workspace(setup_session, slug="concurrency-check")
        key = await widget_keys.create(setup_session, workspace.id, "Site")
        # A real commit, unlike every other test here -- this row must be
        # visible to the two independent connections below, not just to
        # this one's own transaction.
        await setup_session.commit()

    session_id = uuid.uuid4()

    async def raise_flag(kind: str) -> None:
        async with engine.connect() as connection:
            session = AsyncSession(bind=connection, expire_on_commit=False)
            await widget_sessions.record(session, key, session_id, kind)
            await session.commit()

    try:
        await asyncio.gather(raise_flag("searched"), raise_flag("read"))

        async with engine.connect() as check_connection:
            check_session = AsyncSession(bind=check_connection, expire_on_commit=False)
            row = await check_session.scalar(
                sa.select(WidgetSession).where(WidgetSession.id == session_id)
            )
            assert row is not None
            assert (row.searched, row.read_article) == (True, True)
    finally:
        # This test committed for real, so -- unlike every other test in
        # this file -- it is responsible for its own cleanup. Deleting the
        # workspace cascades to its widget key and this session row.
        async with engine.connect() as cleanup_connection:
            cleanup_session = AsyncSession(
                bind=cleanup_connection, expire_on_commit=False
            )
            await cleanup_session.execute(
                sa.delete(Workspace).where(Workspace.id == workspace.id)
            )
            await cleanup_session.commit()
