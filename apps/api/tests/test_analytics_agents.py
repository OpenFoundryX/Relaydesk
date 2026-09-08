from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.services import analytics
from relaydesk.services.analytics import Range, resolve_window
from tests.factories import add_reply, make_conversation, make_member, make_workspace

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)


async def test_a_reply_is_credited_to_whoever_wrote_it_not_the_assignee(
    db_session: AsyncSession,
) -> None:
    """Sara answers and hands the ticket to Nilesh. The reply is Sara's."""
    workspace = await make_workspace(db_session)
    sara = await make_member(
        db_session, workspace, email="sara@relaydesk.dev", name="Sara Blake"
    )
    nilesh = await make_member(
        db_session, workspace, email="nilesh@relaydesk.dev", name="Nilesh Pant"
    )
    conversation = await make_conversation(db_session, workspace, assignee=nilesh)
    await add_reply(db_session, workspace, conversation, at=NOW, author=sara)

    rows = await analytics.agent_rows(
        db_session, workspace.id, resolve_window(Range.d7, NOW)
    )

    assert [(row.name, row.handled) for row in rows] == [(sara.name, 1)]


async def test_a_member_who_did_nothing_has_no_row(db_session: AsyncSession) -> None:
    """The table is a record of activity, not a roster."""
    workspace = await make_workspace(db_session)
    await make_member(db_session, workspace, email="idle@relaydesk.dev")

    rows = await analytics.agent_rows(
        db_session, workspace.id, resolve_window(Range.d7, NOW)
    )

    assert rows == []


async def test_replying_second_leaves_first_response_unset(
    db_session: AsyncSession,
) -> None:
    """The honest answer for somebody who only ever picks up threads others
    opened -- not a zero, and not somebody else's number."""
    workspace = await make_workspace(db_session)
    sara = await make_member(
        db_session, workspace, email="sara@relaydesk.dev", name="Sara Blake"
    )
    nilesh = await make_member(
        db_session, workspace, email="nilesh@relaydesk.dev", name="Nilesh Pant"
    )
    conversation = await make_conversation(db_session, workspace)
    conversation.created_at = NOW - timedelta(minutes=10)
    await db_session.flush()
    await add_reply(
        db_session, workspace, conversation, at=NOW - timedelta(minutes=5), author=sara
    )
    await add_reply(db_session, workspace, conversation, at=NOW, author=nilesh)

    rows = {
        row.name: row
        for row in await analytics.agent_rows(
            db_session, workspace.id, resolve_window(Range.d7, NOW)
        )
    }

    assert rows[sara.name].first_response_seconds == 300
    assert rows[nilesh.name].first_response_seconds is None
    assert rows[nilesh.name].handled == 1


async def test_rows_are_ordered_by_how_much_was_handled(
    db_session: AsyncSession,
) -> None:
    workspace = await make_workspace(db_session)
    sara = await make_member(
        db_session, workspace, email="sara@relaydesk.dev", name="Sara Blake"
    )
    nilesh = await make_member(
        db_session, workspace, email="nilesh@relaydesk.dev", name="Nilesh Pant"
    )
    for index in range(2):
        busy = await make_conversation(db_session, workspace, subject=f"Busy {index}")
        await add_reply(db_session, workspace, busy, at=NOW, author=sara)
    quiet = await make_conversation(db_session, workspace, subject="Quiet")
    await add_reply(db_session, workspace, quiet, at=NOW, author=nilesh)

    rows = await analytics.agent_rows(
        db_session, workspace.id, resolve_window(Range.d7, NOW)
    )

    assert [row.handled for row in rows] == [2, 1]
    assert rows[0].name == sara.name


async def test_another_workspaces_agents_are_absent(db_session: AsyncSession) -> None:
    one = await make_workspace(db_session, slug="chronon")
    two = await make_workspace(db_session, slug="northwind")
    other = await make_member(db_session, two, email="elsewhere@northwind.io")
    conversation = await make_conversation(db_session, two)
    await add_reply(db_session, two, conversation, at=NOW, author=other)

    rows = await analytics.agent_rows(db_session, one.id, resolve_window(Range.d7, NOW))

    assert rows == []
