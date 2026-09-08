"""Ranges, windows and buckets shared by every analytics query.

A caller picks a ``Range`` (a UI concept: "last 30 days"); ``resolve_window``
turns that into a ``Window`` (a query concept: the half-open interval to
filter on, and the bucket size to group by). Every later analytics query
builds on the ``Window`` this module produces, so a wrong bucket boundary
here silently corrupts every chart downstream — hence this module is pure
arithmetic with no database access, easy to test exhaustively on its own.
"""

import enum
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models import ActivityEvent, Conversation, Message


class Range(enum.StrEnum):
    d7 = "7d"
    d30 = "30d"
    d90 = "90d"
    m12 = "12m"


class Bucket(enum.StrEnum):
    """The value is handed straight to Postgres's ``date_trunc``."""

    day = "day"
    week = "week"
    month = "month"


#: How each range is cut up. The point count is the product: every response
#: carries between 7 and 30 points regardless of the span asked for.
GRANULARITY: dict[Range, tuple[Bucket, int]] = {
    Range.d7: (Bucket.day, 7),
    Range.d30: (Bucket.day, 30),
    Range.d90: (Bucket.week, 13),
    Range.m12: (Bucket.month, 12),
}


@dataclass(frozen=True, slots=True)
class Window:
    """A half-open interval ``[start, end)`` and how to cut it up.

    ``end`` is the start of the bucket *after* the one containing "now", so
    the current partial day (or week, or month) is inside the window and
    shows up as the last point.

    ``previous_start`` is ``count`` buckets before ``start`` — bucket-aligned,
    *not* ``start - (end - start)``. For day and week buckets those two are
    the same thing, but months have unequal lengths, so counting buckets and
    subtracting a duration diverge for ``m12`` (e.g. 12 months back from an
    April 1st can land on March 31st by duration, but bucket counting always
    lands on the 1st). Alignment is not optional: ``previous_start`` is
    itself fed back into ``bucket_starts``, whose month step assumes a
    day-1 start, and it has to join against Postgres ``date_trunc`` output,
    which is always aligned too.
    """

    start: datetime
    end: datetime
    bucket: Bucket
    previous_start: datetime


def _truncate(moment: datetime, bucket: Bucket) -> datetime:
    """The UTC equivalent of ``date_trunc``, so Python and Postgres agree on
    where a bucket begins."""
    day = moment.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    if bucket is Bucket.day:
        return day
    if bucket is Bucket.week:
        # Postgres starts a week on Monday; `weekday()` is 0 there too.
        return day - timedelta(days=day.weekday())
    return day.replace(day=1)


def _step_back(start: datetime, bucket: Bucket, count: int) -> datetime:
    """Step ``start`` back by ``count`` buckets. A negative ``count`` steps
    forward instead, which is how ``resolve_window`` finds the window's
    exclusive end and ``bucket_starts`` walks forward through it.

    The month branch assumes ``start.day == 1``: every caller only ever
    passes a bucket-truncated value, and ``.replace(month=...)`` raises for
    an unaligned day that doesn't exist in the target month (e.g. the 31st
    stepped into April).
    """
    if bucket is Bucket.day:
        return start - timedelta(days=count)
    if bucket is Bucket.week:
        return start - timedelta(weeks=count)
    months = start.year * 12 + (start.month - 1) - count
    return start.replace(year=months // 12, month=months % 12 + 1)


def resolve_window(range_: Range, now: datetime) -> Window:
    bucket, count = GRANULARITY[range_]
    current = _truncate(now, bucket)
    start = _step_back(current, bucket, count - 1)
    end = _step_back(current, bucket, -1)
    return Window(
        start=start,
        end=end,
        bucket=bucket,
        previous_start=_step_back(start, bucket, count),
    )


def bucket_starts(window: Window) -> list[datetime]:
    """Every bucket in the window, ascending. The console needs a zero for a
    quiet day, not a gap it has to interpolate across."""
    starts: list[datetime] = []
    moment = window.start
    while moment < window.end:
        starts.append(moment)
        moment = _step_back(moment, window.bucket, -1)
    return starts


#: Statuses that keep a conversation in the backlog. Everything else --
#: resolved, ignored, trash -- is terminal.
BACKLOG_STATUSES = ("open", "pending", "on_hold")

#: A reply to the customer. `system` is excluded: a bounce notice belongs to
#: the thread but answers nobody.
REPLY_ROLES = ("agent", "ai")


class CountMetric(enum.StrEnum):
    created = "created"
    responded = "responded"
    resolved = "resolved"


@dataclass(frozen=True, slots=True)
class Filters:
    """Who the page is scoped to. Mutually exclusive by construction: the
    console's select offers one assignee or "Unassigned", never both."""

    assignee_id: uuid.UUID | None
    unassigned: bool


def _assignee_clause(filters: Filters) -> list:
    if filters.unassigned:
        return [Conversation.assignee_id.is_(None)]
    if filters.assignee_id is not None:
        return [Conversation.assignee_id == filters.assignee_id]
    return []


def _bucket(column, window: Window):
    return sa.func.date_trunc(window.bucket.value, column)


def _first_reply(workspace_id: uuid.UUID):
    """One row per conversation: when it was first answered.

    A subquery rather than a join, because "the first reply" is a property
    of the thread and every metric that needs it needs exactly one row.
    """
    return (
        sa.select(
            Message.conversation_id.label("conversation_id"),
            sa.func.min(Message.sent_at).label("at"),
        )
        .where(
            Message.workspace_id == workspace_id,
            Message.direction == "outbound",
            Message.role.in_(REPLY_ROLES),
        )
        .group_by(Message.conversation_id)
        .subquery()
    )


def _resolves(workspace_id: uuid.UUID, window: Window):
    """One row per (conversation, bucket) it was resolved in.

    Grouped, not raw: a ticket resolved, reopened and resolved again inside
    one bucket is one resolution that bucket, and `min` is the moment the
    resolution-time metric measures to.
    """
    # Same expression reused in the select list and the GROUP BY -- see the
    # comment in `counts` on why calling `_bucket` twice here would compile
    # to two distinct bound parameters that Postgres refuses to fold together.
    resolved_bucket = _bucket(ActivityEvent.at, window)
    return (
        sa.select(
            ActivityEvent.conversation_id.label("conversation_id"),
            resolved_bucket.label("bucket"),
            sa.func.min(ActivityEvent.at).label("at"),
        )
        .where(
            ActivityEvent.workspace_id == workspace_id,
            ActivityEvent.kind == "status",
            ActivityEvent.status == "resolved",
            ActivityEvent.at >= window.start,
            ActivityEvent.at < window.end,
        )
        .group_by(ActivityEvent.conversation_id, resolved_bucket)
        .subquery()
    )


async def counts(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    window: Window,
    filters: Filters,
    metric: CountMetric,
) -> dict[datetime, int]:
    where = _assignee_clause(filters)

    if metric is CountMetric.created:
        # Reuse one bucket expression for both the select list and the
        # GROUP BY: calling `_bucket` twice compiles to two separate bound
        # parameters for the `date_trunc` unit, and Postgres only folds a
        # GROUP BY entry into the select list when the two are the exact
        # same expression, not merely two parameters holding equal values.
        created_bucket = _bucket(Conversation.created_at, window)
        query = (
            sa.select(created_bucket, sa.func.count())
            .where(
                Conversation.workspace_id == workspace_id,
                Conversation.created_at >= window.start,
                Conversation.created_at < window.end,
                *where,
            )
            .group_by(created_bucket)
        )
    elif metric is CountMetric.responded:
        replies = _first_reply(workspace_id)
        reply_bucket = _bucket(replies.c.at, window)
        query = (
            sa.select(reply_bucket, sa.func.count())
            .select_from(replies)
            .join(Conversation, Conversation.id == replies.c.conversation_id)
            .where(
                replies.c.at >= window.start,
                replies.c.at < window.end,
                *where,
            )
            .group_by(reply_bucket)
        )
    else:
        resolves = _resolves(workspace_id, window)
        query = (
            sa.select(resolves.c.bucket, sa.func.count())
            .select_from(resolves)
            .join(Conversation, Conversation.id == resolves.c.conversation_id)
            .where(*where)
            .group_by(resolves.c.bucket)
        )

    rows = await session.execute(query)
    # `date_trunc` on a `timestamptz` column returns a tz-aware datetime, but
    # asyncpg hands it back naive (UTC wall-clock); reattach the tzinfo so
    # these keys compare equal to the tz-aware `bucket_starts` the caller
    # looks them up with.
    return {bucket.replace(tzinfo=UTC): int(value) for bucket, value in rows.all()}


def filled(
    values: dict[datetime, float], window: Window
) -> list[tuple[datetime, float]]:
    return [(start, values.get(start, 0)) for start in bucket_starts(window)]


class DurationMetric(enum.StrEnum):
    first_response = "first_response"
    resolution = "resolution"


def _duration_source(workspace_id: uuid.UUID, window: Window, metric: DurationMetric):
    """`(source, bucket, seconds, moment)` for a duration metric.

    Both metrics are "some later moment minus the conversation's creation",
    differing only in which moment and which rows qualify, so the query is
    written once. `bucket` is built exactly once per call and handed back
    for reuse in both the select list and the GROUP BY -- see the comment
    on `counts` for why calling `_bucket` twice would compile to two
    distinct bound parameters that Postgres refuses to fold together.
    """
    if metric is DurationMetric.first_response:
        source = _first_reply(workspace_id)
        moment = source.c.at
        bucket = _bucket(moment, window)
    else:
        source = _resolves(workspace_id, window)
        moment = source.c.at
        bucket = source.c.bucket
    seconds = sa.func.extract("epoch", moment - Conversation.created_at)
    return source, bucket, seconds, moment


async def durations(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    window: Window,
    filters: Filters,
    metric: DurationMetric,
) -> dict[datetime, float]:
    source, bucket, seconds, moment = _duration_source(workspace_id, window, metric)
    query = (
        sa.select(bucket, sa.func.avg(seconds))
        .select_from(source)
        .join(Conversation, Conversation.id == source.c.conversation_id)
        .where(
            moment >= window.start,
            moment < window.end,
            *_assignee_clause(filters),
        )
        .group_by(bucket)
    )
    rows = await session.execute(query)
    # Same tz-naive-from-asyncpg situation as `counts` -- see the comment
    # there. A conversation with no qualifying moment (no reply, never
    # resolved) simply has no row here rather than a zero, which is the
    # point of the "absent, not zero" test.
    return {
        at.replace(tzinfo=UTC): float(value)
        for at, value in rows.all()
        if value is not None
    }


async def duration_mean(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    start: datetime,
    end: datetime,
    filters: Filters,
    metric: DurationMetric,
) -> float | None:
    """One mean over every qualifying conversation in `[start, end)`.

    Deliberately not the mean of `durations()`'s per-bucket values: a day
    with one slow reply would weigh as much as a day with two hundred fast
    ones, and the headline would report a number no customer experienced.

    Takes `start`/`end` rather than a `Window` because this is also called
    for the *previous* period to compute the delta. `_resolves` bounds
    itself by `window.start`/`window.end`, so the local `Window` built here
    must carry the interval this call was actually asked about -- not some
    ambient "current" window -- or the previous-period call would silently
    query the current period's rows and the delta would always come back
    wrong.
    """
    window = Window(start=start, end=end, bucket=Bucket.day, previous_start=start)
    source, _, seconds, moment = _duration_source(workspace_id, window, metric)
    value = await session.scalar(
        sa.select(sa.func.avg(seconds))
        .select_from(source)
        .join(Conversation, Conversation.id == source.c.conversation_id)
        .where(moment >= start, moment < end, *_assignee_clause(filters))
    )
    return None if value is None else float(value)


async def backlog(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    window: Window,
    filters: Filters,
) -> dict[datetime, int]:
    """How many conversations were in the backlog at the end of each bucket.

    Anchored on today and walked backwards. Replaying forwards from zero
    would put every accumulated error at the right-hand edge -- the point
    the reader actually looks at -- and any status change older than the
    window would be missing from the sum entirely.
    """
    where = _assignee_clause(filters)

    current = await session.scalar(
        sa.select(sa.func.count())
        .select_from(Conversation)
        .where(
            Conversation.workspace_id == workspace_id,
            Conversation.status.in_(BACKLOG_STATUSES),
            *where,
        )
    )

    # Every status event for the workspace, with the status it moved *from*.
    # Deliberately unbounded by the window: an event's predecessor may be
    # older than the range being drawn, and without it the first transition
    # in view would be read against the wrong starting status.
    previous = sa.func.lag(ActivityEvent.status).over(
        partition_by=ActivityEvent.conversation_id, order_by=ActivityEvent.at
    )
    timeline = (
        sa.select(
            ActivityEvent.at.label("at"),
            # A conversation is created open, so the first recorded change
            # is always a move away from `open`.
            sa.func.coalesce(previous, "open").label("from_status"),
            ActivityEvent.status.label("to_status"),
        )
        .join(Conversation, Conversation.id == ActivityEvent.conversation_id)
        .where(
            ActivityEvent.workspace_id == workspace_id,
            ActivityEvent.kind == "status",
            ActivityEvent.status.is_not(None),
            *where,
        )
        .subquery()
    )

    entered = timeline.c.to_status.in_(BACKLOG_STATUSES)
    left = timeline.c.from_status.in_(BACKLOG_STATUSES)
    # `_bucket` is built once and reused in the select list and the GROUP
    # BY -- see the comment on `counts` for why calling it twice would
    # compile to two distinct bound parameters that Postgres refuses to
    # fold together.
    move_bucket = _bucket(timeline.c.at, window)
    moves = await session.execute(
        sa.select(
            move_bucket,
            sa.func.count().filter(entered & ~left),
            sa.func.count().filter(left & ~entered),
        )
        .where(timeline.c.at >= window.start, timeline.c.at < window.end)
        .group_by(move_bucket)
    )
    deltas = {
        at.replace(tzinfo=UTC): (int(into), int(out)) for at, into, out in moves.all()
    }

    created_bucket = _bucket(Conversation.created_at, window)
    created = await session.execute(
        sa.select(created_bucket, sa.func.count())
        .where(
            Conversation.workspace_id == workspace_id,
            Conversation.created_at >= window.start,
            Conversation.created_at < window.end,
            *where,
        )
        .group_by(created_bucket)
    )
    opened = {at.replace(tzinfo=UTC): int(count) for at, count in created.all()}

    series: dict[datetime, int] = {}
    running = int(current or 0)
    for start in reversed(bucket_starts(window)):
        series[start] = running
        entries, exits = deltas.get(start, (0, 0))
        running = running - (entries + opened.get(start, 0)) + exits
    return series
