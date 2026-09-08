from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models import ConversationStatus
from relaydesk.services import analytics
from relaydesk.services.analytics import Filters, Range, resolve_window
from tests.factories import add_status, make_conversation, make_member, make_workspace

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
TODAY = datetime(2026, 8, 30, tzinfo=UTC)
NO_FILTER = Filters(assignee_id=None, unassigned=False)


async def test_an_open_ticket_sits_in_the_backlog(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    conversation.created_at = NOW - timedelta(days=3)
    await db_session.flush()

    series = await analytics.backlog(
        db_session, workspace.id, resolve_window(Range.d7, NOW), NO_FILTER
    )

    assert series[TODAY] == 1


async def test_resolving_a_ticket_takes_it_out_of_the_backlog(
    db_session: AsyncSession,
) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    conversation = await make_conversation(db_session, workspace)
    conversation.created_at = NOW - timedelta(days=3)
    conversation.status = ConversationStatus.resolved
    await db_session.flush()
    await add_status(
        db_session, workspace, conversation, "resolved", NOW - timedelta(days=1), user
    )

    series = await analytics.backlog(
        db_session, workspace.id, resolve_window(Range.d7, NOW), NO_FILTER
    )

    assert series[TODAY] == 0
    # It was still in the backlog the day before it was closed.
    assert series[datetime(2026, 8, 28, tzinfo=UTC)] == 1


async def test_moving_between_two_backlog_statuses_changes_nothing(
    db_session: AsyncSession,
) -> None:
    """`open -> pending` is triage, not progress. Counting destinations
    alone would score it as an entry and inflate the backlog every time
    somebody touched a ticket."""
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    conversation = await make_conversation(db_session, workspace)
    conversation.created_at = NOW - timedelta(days=3)
    conversation.status = ConversationStatus.pending
    await db_session.flush()
    await add_status(
        db_session, workspace, conversation, "pending", NOW - timedelta(days=1), user
    )

    series = await analytics.backlog(
        db_session, workspace.id, resolve_window(Range.d7, NOW), NO_FILTER
    )

    # Every bucket from creation onward stays at 1: the open->pending move
    # is triage, not an entry or an exit, so it leaves no mark. (Buckets
    # before creation are correctly 0 -- the ticket didn't exist yet -- so
    # asserting over the whole window rather than since creation would be
    # wrong.)
    since_creation = {
        v for k, v in series.items() if k >= datetime(2026, 8, 27, tzinfo=UTC)
    }
    assert since_creation == {1}


async def test_a_reopen_puts_a_ticket_back(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    conversation = await make_conversation(db_session, workspace)
    conversation.created_at = NOW - timedelta(days=5)
    await db_session.flush()
    await add_status(
        db_session, workspace, conversation, "resolved", NOW - timedelta(days=3), user
    )
    await add_status(
        db_session, workspace, conversation, "open", NOW - timedelta(days=1), user
    )

    series = await analytics.backlog(
        db_session, workspace.id, resolve_window(Range.d7, NOW), NO_FILTER
    )

    assert series[TODAY] == 1
    assert series[datetime(2026, 8, 28, tzinfo=UTC)] == 0


async def test_a_status_event_with_no_status_is_ignored(
    db_session: AsyncSession,
) -> None:
    """`services/ingest.py` records a mail delivery failure as a
    `kind='status'` event with no status. It is not a status change, and
    treating it as one would corrupt every earlier point."""
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    conversation = await make_conversation(db_session, workspace)
    conversation.created_at = NOW - timedelta(days=3)
    await db_session.flush()
    await add_status(
        db_session, workspace, conversation, None, NOW - timedelta(days=1), user
    )

    series = await analytics.backlog(
        db_session, workspace.id, resolve_window(Range.d7, NOW), NO_FILTER
    )

    # Every bucket from creation onward stays at 1: the null-status event is
    # skipped entirely, so it can neither add nor remove a ticket. (Buckets
    # before creation are correctly 0 -- the ticket didn't exist yet -- so
    # asserting over the whole window rather than since creation would be
    # wrong.)
    since_creation = {
        v for k, v in series.items() if k >= datetime(2026, 8, 27, tzinfo=UTC)
    }
    assert since_creation == {1}


async def test_todays_value_is_counted_not_replayed(
    db_session: AsyncSession,
) -> None:
    """The anchor. A conversation whose history predates the window still
    shows up in today's number, because today's number is a count of the
    conversations table rather than the end of a replay."""
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    conversation.created_at = NOW - timedelta(days=400)
    await db_session.flush()

    series = await analytics.backlog(
        db_session, workspace.id, resolve_window(Range.d7, NOW), NO_FILTER
    )

    assert series[TODAY] == 1
    assert series[resolve_window(Range.d7, NOW).start] == 1


async def test_a_ticket_created_and_resolved_in_the_same_bucket_nets_to_zero(
    db_session: AsyncSession,
) -> None:
    """One entry and one exit in the same bucket must cancel out exactly --
    a naive implementation that counts entries and exits independently
    without netting them against each other in the walk-back would still
    get this wrong if the arithmetic were off by a sign."""
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    conversation = await make_conversation(db_session, workspace)
    conversation.created_at = NOW - timedelta(hours=2)
    conversation.status = ConversationStatus.resolved
    await db_session.flush()
    await add_status(
        db_session, workspace, conversation, "resolved", NOW - timedelta(hours=1), user
    )

    series = await analytics.backlog(
        db_session, workspace.id, resolve_window(Range.d7, NOW), NO_FILTER
    )

    assert series[TODAY] == 0
    assert set(series.values()) == {0}
