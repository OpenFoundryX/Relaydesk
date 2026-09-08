from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models import MessageRole
from relaydesk.services import analytics
from relaydesk.services.analytics import CountMetric, Filters, Range, resolve_window
from tests.factories import (
    add_reply,
    add_status,
    make_conversation,
    make_member,
    make_workspace,
)

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
NO_FILTER = Filters(assignee_id=None, unassigned=False)


async def test_a_ticket_counts_on_the_day_it_was_created(
    db_session: AsyncSession,
) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    conversation.created_at = NOW - timedelta(days=2)
    await db_session.flush()

    series = await analytics.counts(
        db_session,
        workspace.id,
        resolve_window(Range.d7, NOW),
        NO_FILTER,
        CountMetric.created,
    )

    assert series[datetime(2026, 8, 28, tzinfo=UTC)] == 1
    assert series.get(datetime(2026, 8, 30, tzinfo=UTC), 0) == 0


async def test_a_ticket_counts_as_responded_on_the_day_of_its_first_reply(
    db_session: AsyncSession,
) -> None:
    """The bucket of the reply, not of the ticket -- the number reads as
    'tickets we answered that day'."""
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    conversation.created_at = NOW - timedelta(days=4)
    await add_reply(db_session, workspace, conversation, at=NOW - timedelta(days=1))
    await add_reply(db_session, workspace, conversation, at=NOW)

    series = await analytics.counts(
        db_session,
        workspace.id,
        resolve_window(Range.d7, NOW),
        NO_FILTER,
        CountMetric.responded,
    )

    # Counted once, on the first reply's day, not on both.
    assert series[datetime(2026, 8, 29, tzinfo=UTC)] == 1
    assert series.get(datetime(2026, 8, 30, tzinfo=UTC), 0) == 0


async def test_a_system_message_is_not_a_response(db_session: AsyncSession) -> None:
    """A bounce notice is not an answer to the customer."""
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    await add_reply(
        db_session, workspace, conversation, at=NOW, role=MessageRole.system
    )

    series = await analytics.counts(
        db_session,
        workspace.id,
        resolve_window(Range.d7, NOW),
        NO_FILTER,
        CountMetric.responded,
    )

    assert sum(series.values()) == 0


async def test_a_ticket_resolved_twice_in_one_day_counts_once(
    db_session: AsyncSession,
) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    conversation = await make_conversation(db_session, workspace)
    await add_status(db_session, workspace, conversation, "resolved", NOW, user)
    await add_status(db_session, workspace, conversation, "open", NOW, user)
    await add_status(db_session, workspace, conversation, "resolved", NOW, user)

    series = await analytics.counts(
        db_session,
        workspace.id,
        resolve_window(Range.d7, NOW),
        NO_FILTER,
        CountMetric.resolved,
    )

    assert series[datetime(2026, 8, 30, tzinfo=UTC)] == 1


async def test_another_workspaces_tickets_are_not_counted(
    db_session: AsyncSession,
) -> None:
    one = await make_workspace(db_session, slug="chronon")
    two = await make_workspace(db_session, slug="northwind")
    await make_conversation(db_session, two)

    series = await analytics.counts(
        db_session,
        one.id,
        resolve_window(Range.d7, NOW),
        NO_FILTER,
        CountMetric.created,
    )

    assert sum(series.values()) == 0


async def test_the_assignee_filter_narrows_to_one_persons_tickets(
    db_session: AsyncSession,
) -> None:
    workspace = await make_workspace(db_session)
    sara = await make_member(db_session, workspace, email="sara@relaydesk.dev")
    mine = await make_conversation(db_session, workspace, assignee=sara)
    await make_conversation(db_session, workspace, subject="Someone else's")
    mine.created_at = NOW
    await db_session.flush()

    series = await analytics.counts(
        db_session,
        workspace.id,
        resolve_window(Range.d7, NOW),
        Filters(assignee_id=sara.id, unassigned=False),
        CountMetric.created,
    )

    assert sum(series.values()) == 1


async def test_unassigned_selects_tickets_with_no_assignee(
    db_session: AsyncSession,
) -> None:
    workspace = await make_workspace(db_session)
    sara = await make_member(db_session, workspace, email="sara@relaydesk.dev")
    await make_conversation(db_session, workspace, assignee=sara)
    loose = await make_conversation(db_session, workspace, subject="Nobody's")
    loose.created_at = NOW
    await db_session.flush()

    series = await analytics.counts(
        db_session,
        workspace.id,
        resolve_window(Range.d7, NOW),
        Filters(assignee_id=None, unassigned=True),
        CountMetric.created,
    )

    assert sum(series.values()) == 1


async def test_filled_puts_a_zero_in_a_quiet_bucket(db_session: AsyncSession) -> None:
    """A gap is not the same as a zero, and the console must not have to
    tell them apart."""
    window = resolve_window(Range.d7, NOW)

    points = analytics.filled({datetime(2026, 8, 30, tzinfo=UTC): 3}, window)

    assert len(points) == 7
    assert points[-1] == (datetime(2026, 8, 30, tzinfo=UTC), 3)
    assert points[0][1] == 0
