# Analytics — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/analytics` real — six trend cards and a per-agent table computed live from the workspace's own conversations, messages and activity events, filtered by date range and assignee.

**Architecture:** A new `services/analytics.py` runs one aggregate query per metric against Postgres, grouped by a bucket whose size scales with the requested range. A new admin-only `GET /api/analytics` assembles them into the `MetricSeries` shape the console already renders. No rollup table, no Celery task, no cache.

**Tech Stack:** FastAPI, SQLAlchemy 2 (async), Postgres 16, Alembic, pytest. Console: Next 16 App Router, Recharts, vitest.

**Spec:** `docs/superpowers/specs/2026-09-08-analytics-design.md`

## Global Constraints

- `BACKLOG_STATUSES = {open, pending, on_hold}`. Terminal: `resolved`, `ignored`, `trash`.
- "Outbound reply" is always `direction = 'outbound' AND role IN ('agent', 'ai')`. Never `system`.
- Buckets are **UTC**. Never a viewer's timezone.
- Every query filters `workspace_id` from `WorkspaceScope`, never from a request parameter.
- Ranges are exactly `7d | 30d | 90d | 12m`. Granularity: `7d`/`30d` daily, `90d` weekly, `12m` monthly.
- The wire format is camelCase via `CamelModel`. Python stays snake_case.
- `headline` is a **preformatted string**; `delta` is an integer percent or `null`. This is fixed by `MetricSeries` in `apps/web/lib/types.ts:99` and must not change.
- Services `flush()`; routes `commit()`. (Analytics is read-only, so it does neither.)
- `ruff check src tests` must pass; line length 88.

---

## File Structure

**API — create**
- `src/relaydesk/services/analytics.py` — every aggregate query and the window arithmetic. One responsibility: turn a workspace + window + assignee into numbers.
- `src/relaydesk/schemas/analytics.py` — `MetricSeriesOut`, `MetricPointOut`, `AgentRowOut`, `AnalyticsOut`.
- `src/relaydesk/api/analytics.py` — one route, admin gate, parameter validation.
- `migrations/versions/0020_analytics_indexes.py`
- `tests/test_analytics_windows.py`, `tests/test_analytics_series.py`, `tests/test_analytics_backlog.py`, `tests/test_analytics_agents.py`, `tests/test_analytics_api.py`, `tests/test_analytics_migration.py`

**API — modify**
- `src/relaydesk/services/ingest.py:487` — record the reopen (Task 1)
- `src/relaydesk/api/router.py` — mount the router

**Console — create**
- `apps/web/lib/api/analytics.ts`
- `apps/web/components/analytics/agent-table.tsx`
- `apps/web/components/analytics/metric-card.test.tsx`

**Console — modify**
- `apps/web/app/(console)/analytics/page.tsx` — real data, read filters from `searchParams`
- `apps/web/components/analytics/analytics-filters.tsx` — drive the URL
- `apps/web/components/analytics/metric-card.tsx` — hour-scale durations, fix the deprecated type import
- `apps/web/lib/types.ts` — add `AgentRow`, `AnalyticsResponse`
- `apps/web/lib/mock/analytics.ts` — **deleted** in the final task

Why `services/analytics.py` is one file and not six: the queries share the window arithmetic, the assignee predicate and the bucket-filling helper. Split by metric and every file imports the same four helpers from a seventh. It stays under ~350 lines.

---

### Task 1: Record a reopen in the activity trail

Spec §6. A prerequisite: the backlog series (Task 6) cannot see a reopen that was never written. It also repairs a pre-existing gap — the conversation's own timeline has never shown reopens.

**Files:**
- Modify: `apps/api/src/relaydesk/services/ingest.py:487-489`
- Test: `apps/api/tests/test_ingest_reopen_activity.py` (create)

**Interfaces:**
- Consumes: `conversations.record(session, conversation, actor, kind, verb, value, status)` — already exists at `services/conversations.py:336`.
- Produces: an `ActivityEvent(kind=status, status="open")` on every inbound reply that reopens. Task 6 depends on this.

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_ingest_reopen_activity.py
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models import ActivityEvent, ActivityKind, ConversationStatus
from relaydesk.services import conversations
from tests.factories import make_conversation, make_member, make_workspace


async def test_an_inbound_reply_to_a_resolved_ticket_records_the_reopen(
    db_session: AsyncSession,
) -> None:
    """Without this event the backlog series cannot see the reopen: the
    ticket silently re-enters the backlog and every earlier point is short
    by one. The conversation's own timeline was missing it too."""
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    conversation = await make_conversation(db_session, workspace)
    await conversations.set_status(
        db_session,
        workspace.id,
        conversation.id,
        ConversationStatus.resolved,
        conversations.Actor(name=user.name, user_id=user.id),
    )

    await deliver_inbound_reply(db_session, workspace, conversation)

    events = list(
        await db_session.scalars(
            sa.select(ActivityEvent)
            .where(
                ActivityEvent.conversation_id == conversation.id,
                ActivityEvent.kind == ActivityKind.status,
            )
            .order_by(ActivityEvent.at)
        )
    )
    assert [event.status for event in events] == ["resolved", "open"]
```

`deliver_inbound_reply` is a helper you write in the same file. Read
`tests/test_ingest.py` first and copy the way it builds and feeds a raw
message — do not invent a new path into `ingest`. Check the real signature
of `conversations.set_status` and `Actor` in
`src/relaydesk/services/conversations.py` before writing the arrange block;
adapt the two lines above to match rather than guessing.

- [ ] **Step 2: Run it and watch it fail**

Run: `docker compose exec api python -m pytest tests/test_ingest_reopen_activity.py -q`
Expected: FAIL — `assert ['resolved'] == ['resolved', 'open']`. If it errors instead, fix the helper until it *fails* on that assertion.

- [ ] **Step 3: Record the transition**

`services/ingest.py`, replacing lines 487-489:

```python
    elif conversation.status in REOPENING_STATUSES:
        conversation.status = ConversationStatus.open
        # The customer's reply is what reopened it, so the trail says so.
        # Written here rather than left implicit because a status the
        # timeline never mentions is a status the analytics backlog series
        # cannot reconstruct -- see the analytics design, section 6.
        conversations.record(
            session,
            conversation,
            Actor(name=contact.name),
            ActivityKind.status,
            "reopened this",
            "Open",
            ConversationStatus.open.value,
        )
```

Confirm `record`'s parameter order and the `Actor` import against
`services/conversations.py:336` — the branch directly above this one already
constructs `Actor(name=contact.name)`, so copy its call shape.

- [ ] **Step 4: Run the test, then the ingest suite**

Run: `docker compose exec api python -m pytest tests/test_ingest_reopen_activity.py tests/test_ingest.py tests/test_ingest_untagged_reply.py -q`
Expected: all PASS. A pre-existing ingest test that counted activity rows may now see one more — if so, that test's expectation is what changes, not this behavior.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/relaydesk/services/ingest.py apps/api/tests/test_ingest_reopen_activity.py
git commit -m "fix(ingest): record the reopen a customer's reply causes"
```

---

### Task 2: Ranges, windows and buckets

Pure arithmetic, no database. Everything else depends on it.

**Files:**
- Create: `apps/api/src/relaydesk/services/analytics.py`
- Test: `apps/api/tests/test_analytics_windows.py`

**Interfaces:**
- Produces:
  - `class Range(StrEnum)`: `d7 = "7d"`, `d30 = "30d"`, `d90 = "90d"`, `m12 = "12m"`
  - `class Bucket(StrEnum)`: `day`, `week`, `month` — the value is passed straight to `date_trunc`.
  - `@dataclass(frozen=True) Window(start, end, bucket, previous_start)` — `start` inclusive, `end` exclusive, both `datetime` (UTC, tz-aware). `previous_start` is the same **number of buckets** before `start`, and is itself bucket-aligned — not the literal `start - (end - start)`. For day and week buckets the two are identical; for months they diverge whenever a leap day falls in one period and not the other. Bucket alignment is the load-bearing property: Task 8 wraps `previous_start` in a `Window` and calls `bucket_starts()` on it, and an unaligned month start (say the 31st) makes `_step_back`'s `.replace(month=...)` raise `ValueError: day is out of range for month`. It also has to line up with `date_trunc` output or the previous period's join matches nothing and every delta reads `null`.
  - `resolve_window(range_: Range, now: datetime) -> Window`
  - `bucket_starts(window: Window) -> list[datetime]`

- [ ] **Step 1: Write the failing tests**

```python
# apps/api/tests/test_analytics_windows.py
from datetime import UTC, datetime

import pytest

from relaydesk.services.analytics import Bucket, Range, bucket_starts, resolve_window

NOW = datetime(2026, 8, 30, 14, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("range_", "bucket", "points"),
    [
        (Range.d7, Bucket.day, 7),
        (Range.d30, Bucket.day, 30),
        (Range.d90, Bucket.week, 13),
        (Range.m12, Bucket.month, 12),
    ],
)
def test_every_range_yields_between_7_and_30_points(range_, bucket, points) -> None:
    """A year bucketed by day is 365 points: a smear the card cannot draw and
    a year of events to scan. Granularity scales so the response, and the
    work behind it, stay the same size whatever is asked for."""
    window = resolve_window(range_, NOW)

    assert window.bucket is bucket
    assert len(bucket_starts(window)) == points


def test_the_window_ends_after_now_so_today_is_in_it() -> None:
    window = resolve_window(Range.d30, NOW)

    assert window.end > NOW
    assert bucket_starts(window)[-1] == datetime(2026, 8, 30, tzinfo=UTC)


def test_the_window_starts_on_a_bucket_boundary() -> None:
    window = resolve_window(Range.d30, NOW)

    assert window.start == datetime(2026, 8, 1, tzinfo=UTC)


def test_the_previous_window_is_the_same_length_immediately_before() -> None:
    window = resolve_window(Range.d30, NOW)

    assert window.previous_start == datetime(2026, 7, 2, tzinfo=UTC)
    assert window.start - window.previous_start == window.end - window.start


def test_monthly_buckets_land_on_the_first_of_each_month() -> None:
    starts = bucket_starts(resolve_window(Range.m12, NOW))

    assert starts[0] == datetime(2025, 9, 1, tzinfo=UTC)
    assert starts[-1] == datetime(2026, 8, 1, tzinfo=UTC)
    assert all(start.day == 1 for start in starts)


def test_weekly_buckets_land_on_mondays() -> None:
    """`date_trunc('week', ...)` in Postgres starts weeks on Monday, and
    these buckets are joined against it."""
    starts = bucket_starts(resolve_window(Range.d90, NOW))

    assert all(start.weekday() == 0 for start in starts)
```

- [ ] **Step 2: Run and watch it fail**

Run: `docker compose exec api python -m pytest tests/test_analytics_windows.py -q`
Expected: collection error — `cannot import name 'Range' from 'relaydesk.services.analytics'`.

- [ ] **Step 3: Implement**

```python
# apps/api/src/relaydesk/services/analytics.py
import enum
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


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
```

`_step_back` with a negative count steps forward — check that
`_step_back(datetime(2026, 12, 1), Bucket.month, -1)` returns January 2027
and not a `ValueError`, and fix the month arithmetic if it does.

- [ ] **Step 4: Run and watch it pass**

Run: `docker compose exec api python -m pytest tests/test_analytics_windows.py -q`
Expected: 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/relaydesk/services/analytics.py apps/api/tests/test_analytics_windows.py
git commit -m "feat(analytics): resolve a range into a bucketed window"
```

---

### Task 3: Indexes for the analytics queries

**Files:**
- Create: `apps/api/migrations/versions/0020_analytics_indexes.py`
- Test: `apps/api/tests/test_analytics_migration.py`

**Interfaces:**
- Produces: `ix_activity_events_workspace_kind_at`, `ix_messages_workspace_direction_sent_at`.

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_analytics_migration.py
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

INDEXES = [
    ("activity_events", "ix_activity_events_workspace_kind_at"),
    ("messages", "ix_messages_workspace_direction_sent_at"),
]


async def test_the_analytics_indexes_exist(db_session: AsyncSession) -> None:
    """Every analytics query filters one of these two tables by workspace and
    a time column. Without the indexes each card is a sequential scan."""
    for table, index in INDEXES:
        found = await db_session.scalar(
            sa.text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = :table AND indexname = :index"
            ),
            {"table": table, "index": index},
        )
        assert found == index, f"{index} missing from {table}"
```

- [ ] **Step 2: Run and watch it fail**

Run: `docker compose exec api python -m pytest tests/test_analytics_migration.py -q`
Expected: FAIL — `assert None == 'ix_activity_events_workspace_kind_at'`.

- [ ] **Step 3: Write the migration**

```python
# apps/api/migrations/versions/0020_analytics_indexes.py
"""analytics indexes

Two composite indexes covering the access pattern the analytics queries
introduce. Both lead with ``workspace_id`` because every one of those
queries is tenant-scoped before it is anything else, then narrow on the
discriminator the query already knows, then range-scan the time column.

Revision ID: 0020
Revises: 0019
Create Date: 2026-09-08 15:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0020"
down_revision: str | Sequence[str] | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Resolved counts, resolution times and the whole backlog replay read
    # activity events this way and no other.
    op.create_index(
        "ix_activity_events_workspace_kind_at",
        "activity_events",
        ["workspace_id", "kind", "at"],
    )
    # First-reply lookups: outbound only, ordered by when it was sent.
    op.create_index(
        "ix_messages_workspace_direction_sent_at",
        "messages",
        ["workspace_id", "direction", "sent_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_messages_workspace_direction_sent_at", table_name="messages"
    )
    op.drop_index(
        "ix_activity_events_workspace_kind_at", table_name="activity_events"
    )
```

- [ ] **Step 4: Migrate and run**

```bash
docker compose exec api alembic upgrade head
docker compose exec api python -m pytest tests/test_analytics_migration.py -q
```
Expected: PASS. The test suite recreates its database from migrations, so it proves the migration and not just the dev database.

- [ ] **Step 5: Commit**

```bash
git add apps/api/migrations/versions/0020_analytics_indexes.py apps/api/tests/test_analytics_migration.py
git commit -m "feat(analytics): index the two tables every metric reads"
```

---

### Task 4: The three count series

**Files:**
- Modify: `apps/api/src/relaydesk/services/analytics.py`
- Test: `apps/api/tests/test_analytics_series.py`

**Interfaces:**
- Consumes: `Window`, `Bucket`, `bucket_starts` (Task 2).
- Produces:
  - `Filters(assignee_id: uuid.UUID | None, unassigned: bool)` — `unassigned=True` means `assignee_id IS NULL`; the two are mutually exclusive.
  - `async def counts(session, workspace_id, window, filters, metric: CountMetric) -> dict[datetime, int]`
  - `class CountMetric(StrEnum)`: `created`, `responded`, `resolved`
  - `def filled(values: dict[datetime, float], window) -> list[tuple[datetime, float]]`

- [ ] **Step 1: Write the failing tests**

```python
# apps/api/tests/test_analytics_series.py
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

# `ruff check src tests` runs over this file, so import exactly what the
# tests and your two helpers use -- an unused name fails the lint.
from relaydesk.models import (
    ActivityEvent,
    ActivityKind,
    Message,
    MessageDirection,
    MessageRole,
)
from relaydesk.services import analytics
from relaydesk.services.analytics import CountMetric, Filters, Range, resolve_window
from tests.factories import make_conversation, make_member, make_workspace

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
    # `name` must be passed: make_member defaults it to "Nilesh Pant", which
    # would collide with the other member these tests create and break any
    # assertion keyed by name.
    sara = await make_member(
        db_session, workspace, email="sara@relaydesk.dev", name="Sara Duval"
    )
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
    # `name` must be passed: make_member defaults it to "Nilesh Pant", which
    # would collide with the other member these tests create and break any
    # assertion keyed by name.
    sara = await make_member(
        db_session, workspace, email="sara@relaydesk.dev", name="Sara Duval"
    )
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
```

Write `add_reply` and `add_status` as helpers at the top of the file.
`add_reply` inserts a `Message` with `direction=outbound`, `role` defaulting
to `MessageRole.agent`, and the given `sent_at`. `add_status` inserts an
`ActivityEvent` with `kind=ActivityKind.status`, the given status string,
`at`, and `actor_user_id`. Read `tests/factories.py` and the two models for
the required non-null columns before writing them — `Message.body`,
`Message.author_name` and `ActivityEvent.verb` all have no default.

Note `make_conversation` commits and sets `created_at` itself, which is why
these tests reassign `created_at` and `flush()`.

- [ ] **Step 2: Run and watch them fail**

Run: `docker compose exec api python -m pytest tests/test_analytics_series.py -q`
Expected: collection error on `CountMetric`.

- [ ] **Step 3: Implement**

Append to `services/analytics.py`:

```python
import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models import ActivityEvent, Conversation, Message

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
    return (
        sa.select(
            ActivityEvent.conversation_id.label("conversation_id"),
            _bucket(ActivityEvent.at, window).label("bucket"),
            sa.func.min(ActivityEvent.at).label("at"),
        )
        .where(
            ActivityEvent.workspace_id == workspace_id,
            ActivityEvent.kind == "status",
            ActivityEvent.status == "resolved",
            ActivityEvent.at >= window.start,
            ActivityEvent.at < window.end,
        )
        .group_by(ActivityEvent.conversation_id, _bucket(ActivityEvent.at, window))
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
        query = (
            sa.select(
                _bucket(Conversation.created_at, window),
                sa.func.count(),
            )
            .where(
                Conversation.workspace_id == workspace_id,
                Conversation.created_at >= window.start,
                Conversation.created_at < window.end,
                *where,
            )
            .group_by(1)
        )
    elif metric is CountMetric.responded:
        replies = _first_reply(workspace_id)
        query = (
            sa.select(_bucket(replies.c.at, window), sa.func.count())
            .select_from(replies)
            .join(Conversation, Conversation.id == replies.c.conversation_id)
            .where(
                replies.c.at >= window.start,
                replies.c.at < window.end,
                *where,
            )
            .group_by(1)
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
    return {bucket: int(value) for bucket, value in rows.all()}


def filled(
    values: dict[datetime, float], window: Window
) -> list[tuple[datetime, float]]:
    return [(start, values.get(start, 0)) for start in bucket_starts(window)]
```

`date_trunc` returns a timezone-aware `datetime` for a `timestamptz` column.
If the dict keys come back naive, the comparisons in these tests fail —
coerce with `.replace(tzinfo=UTC)` in the `counts` comprehension and say so
in a comment.

- [ ] **Step 4: Run and watch them pass**

Run: `docker compose exec api python -m pytest tests/test_analytics_series.py -q`
Expected: 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/relaydesk/services/analytics.py apps/api/tests/test_analytics_series.py
git commit -m "feat(analytics): count tickets created, answered and resolved"
```

---

### Task 5: The two duration series

**Files:**
- Modify: `apps/api/src/relaydesk/services/analytics.py`
- Test: `apps/api/tests/test_analytics_series.py` (append)

**Interfaces:**
- Produces:
  - `class DurationMetric(StrEnum)`: `first_response`, `resolution`
  - `async def durations(session, workspace_id, window, filters, metric) -> dict[datetime, float]` — mean seconds per bucket
  - `async def duration_mean(session, workspace_id, start, end, filters, metric) -> float | None` — one mean over the whole interval, for the headline

- [ ] **Step 1: Write the failing tests**

```python
async def test_first_response_is_measured_from_the_tickets_creation(
    db_session: AsyncSession,
) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    conversation.created_at = NOW - timedelta(minutes=30)
    await db_session.flush()
    await add_reply(db_session, workspace, conversation, at=NOW - timedelta(minutes=20))

    series = await analytics.durations(
        db_session,
        workspace.id,
        resolve_window(Range.d7, NOW),
        NO_FILTER,
        analytics.DurationMetric.first_response,
    )

    assert series[datetime(2026, 8, 30, tzinfo=UTC)] == 600


async def test_resolution_time_is_measured_from_creation_not_from_the_last_reply(
    db_session: AsyncSession,
) -> None:
    """A reopened-then-resolved ticket reports the whole elapsed ordeal."""
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    conversation = await make_conversation(db_session, workspace)
    conversation.created_at = NOW - timedelta(hours=4)
    await db_session.flush()
    await add_status(db_session, workspace, conversation, "resolved", NOW, user)

    series = await analytics.durations(
        db_session,
        workspace.id,
        resolve_window(Range.d7, NOW),
        NO_FILTER,
        analytics.DurationMetric.resolution,
    )

    assert series[datetime(2026, 8, 30, tzinfo=UTC)] == 4 * 3600


async def test_a_ticket_with_no_reply_is_absent_rather_than_zero(
    db_session: AsyncSession,
) -> None:
    """Counting an unanswered ticket as a zero-second response would drag
    the average toward zero and report the opposite of the truth."""
    workspace = await make_workspace(db_session)
    answered = await make_conversation(db_session, workspace)
    answered.created_at = NOW - timedelta(minutes=10)
    await db_session.flush()
    await add_reply(db_session, workspace, answered, at=NOW)
    await make_conversation(db_session, workspace, subject="Nobody answered me")

    series = await analytics.durations(
        db_session,
        workspace.id,
        resolve_window(Range.d7, NOW),
        NO_FILTER,
        analytics.DurationMetric.first_response,
    )

    assert series[datetime(2026, 8, 30, tzinfo=UTC)] == 600


async def test_the_headline_mean_is_over_conversations_not_over_daily_means(
    db_session: AsyncSession,
) -> None:
    """One slow reply yesterday and three fast ones today. The mean of the
    two daily means is 450s; the mean over the four conversations is 225s.
    Only the second is a number a customer experienced."""
    workspace = await make_workspace(db_session)
    window = resolve_window(Range.d7, NOW)

    slow = await make_conversation(db_session, workspace, subject="Slow")
    slow.created_at = NOW - timedelta(days=1, minutes=15)
    await db_session.flush()
    await add_reply(db_session, workspace, slow, at=NOW - timedelta(days=1))

    for index in range(3):
        fast = await make_conversation(db_session, workspace, subject=f"Fast {index}")
        # Answered the instant it arrived, so the three fast tickets
        # contribute zero and the two means below are 450 and 225. With any
        # non-zero fast response the property under test still holds, but
        # the arithmetic in the assertions has to move with it.
        fast.created_at = NOW
        await db_session.flush()
        await add_reply(db_session, workspace, fast, at=NOW)

    series = await analytics.durations(
        db_session, workspace.id, window, NO_FILTER, analytics.DurationMetric.first_response
    )
    headline = await analytics.duration_mean(
        db_session,
        workspace.id,
        window.start,
        window.end,
        NO_FILTER,
        analytics.DurationMetric.first_response,
    )

    daily = sum(series.values()) / len(series)
    assert daily == 450
    assert headline == 225


async def test_the_headline_is_none_when_nothing_qualifies(
    db_session: AsyncSession,
) -> None:
    workspace = await make_workspace(db_session)
    window = resolve_window(Range.d7, NOW)

    headline = await analytics.duration_mean(
        db_session,
        workspace.id,
        window.start,
        window.end,
        NO_FILTER,
        analytics.DurationMetric.first_response,
    )

    assert headline is None
```

- [ ] **Step 2: Run and watch them fail**

Run: `docker compose exec api python -m pytest tests/test_analytics_series.py -q`
Expected: `AttributeError: module 'relaydesk.services.analytics' has no attribute 'DurationMetric'`.

- [ ] **Step 3: Implement**

```python
class DurationMetric(enum.StrEnum):
    first_response = "first_response"
    resolution = "resolution"


def _duration_source(workspace_id, window, metric: DurationMetric):
    """`(bucket_column, seconds_column, join_target)` for a duration metric.

    Both metrics are "some later moment minus the conversation's creation",
    differing only in which moment and which rows qualify, so the query is
    written once.
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


def _duration_query(workspace_id, window, filters, metric, start, end):
    source, bucket, seconds, moment = _duration_source(workspace_id, window, metric)
    query = (
        sa.select(bucket, sa.func.avg(seconds))
        .select_from(source)
        .join(Conversation, Conversation.id == source.c.conversation_id)
        .where(moment >= start, moment < end, *_assignee_clause(filters))
    )
    return query, bucket, seconds, source, moment


async def durations(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    window: Window,
    filters: Filters,
    metric: DurationMetric,
) -> dict[datetime, float]:
    query, bucket, _, _, _ = _duration_query(
        workspace_id, window, filters, metric, window.start, window.end
    )
    rows = await session.execute(query.group_by(bucket))
    return {at: float(value) for at, value in rows.all() if value is not None}


async def duration_mean(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    start: datetime,
    end: datetime,
    filters: Filters,
    metric: DurationMetric,
) -> float | None:
    """One mean over every qualifying conversation in `[start, end)`.

    Deliberately not the mean of `durations()`'s values: a day with one slow
    reply would weigh as much as a day with two hundred fast ones, and the
    headline would report a number nobody experienced.
    """
    # The window only supplies the bucket expression here, which this query
    # does not group by -- the interval is the one passed in, so the same
    # call serves the previous period for the delta.
    window = Window(start=start, end=end, bucket=Bucket.day, previous_start=start)
    source, _, seconds, moment = _duration_source(workspace_id, window, metric)
    value = await session.scalar(
        sa.select(sa.func.avg(seconds))
        .select_from(source)
        .join(Conversation, Conversation.id == source.c.conversation_id)
        .where(moment >= start, moment < end, *_assignee_clause(filters))
    )
    return None if value is None else float(value)
```

`_resolves` bounds itself by `window.start`/`window.end`, so
`duration_mean` for the *previous* period must build its subquery from the
window it was passed — that is why `duration_mean` constructs a local
`Window`. Verify the previous-period resolution mean is non-zero in a quick
REPL check before moving on; if `_resolves` is still bounded by the current
window, the delta for `resolution-time` will always be `null`.

- [ ] **Step 4: Run and watch them pass**

Run: `docker compose exec api python -m pytest tests/test_analytics_series.py -q`
Expected: 13 PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/relaydesk/services/analytics.py apps/api/tests/test_analytics_series.py
git commit -m "feat(analytics): average first response and resolution time"
```

---

### Task 6: The backlog series

Spec §4.6. The subtlest query here — read the spec section before starting.

**Files:**
- Modify: `apps/api/src/relaydesk/services/analytics.py`
- Test: `apps/api/tests/test_analytics_backlog.py`

**Interfaces:**
- Produces: `async def backlog(session, workspace_id, window, filters) -> dict[datetime, int]`

- [ ] **Step 1: Write the failing tests**

```python
# apps/api/tests/test_analytics_backlog.py
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models import ConversationStatus
from relaydesk.services import analytics
from relaydesk.services.analytics import Filters, Range, resolve_window
from tests.factories import make_conversation, make_member, make_workspace

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

    # Only from the day it was created. The buckets before that are
    # legitimately zero -- the conversation did not exist yet -- so
    # asserting over every value would demand a backlog of one on days
    # nothing was in it.
    since_creation = {
        value for at, value in series.items()
        if at >= datetime(2026, 8, 27, tzinfo=UTC)
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

    # Only from the day it was created. The buckets before that are
    # legitimately zero -- the conversation did not exist yet -- so
    # asserting over every value would demand a backlog of one on days
    # nothing was in it.
    since_creation = {
        value for at, value in series.items()
        if at >= datetime(2026, 8, 27, tzinfo=UTC)
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
```

Reuse the `add_status` helper from Task 4 — move it into `tests/factories.py`
as `make_status_event(session, workspace, conversation, status, at, user)` so
both modules share it, and update Task 4's imports.

- [ ] **Step 2: Run and watch them fail**

Run: `docker compose exec api python -m pytest tests/test_analytics_backlog.py -q`
Expected: `AttributeError: ... has no attribute 'backlog'`.

- [ ] **Step 3: Implement**

```python
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
    moves = await session.execute(
        sa.select(
            _bucket(timeline.c.at, window),
            sa.func.count().filter(entered & ~left),
            sa.func.count().filter(left & ~entered),
        )
        .where(timeline.c.at >= window.start, timeline.c.at < window.end)
        .group_by(1)
    )
    deltas = {at: (int(into), int(out)) for at, into, out in moves.all()}

    created = await session.execute(
        sa.select(_bucket(Conversation.created_at, window), sa.func.count())
        .where(
            Conversation.workspace_id == workspace_id,
            Conversation.created_at >= window.start,
            Conversation.created_at < window.end,
            *where,
        )
        .group_by(1)
    )
    opened = {at: int(count) for at, count in created.all()}

    series: dict[datetime, int] = {}
    running = int(current or 0)
    for start in reversed(bucket_starts(window)):
        series[start] = running
        entries, exits = deltas.get(start, (0, 0))
        running = running - (entries + opened.get(start, 0)) + exits
    return series
```

Two things to check against the database rather than assume:
`func.count().filter(...)` renders as `count(*) FILTER (WHERE ...)`, which
Postgres supports — confirm the generated SQL with `print(query)` if a test
fails oddly. And a conversation created *and* resolved inside the same
bucket contributes one entry and one exit, netting zero; add a test for that
if the arithmetic surprises you.

- [ ] **Step 4: Run and watch them pass**

Run: `docker compose exec api python -m pytest tests/test_analytics_backlog.py -q`
Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/relaydesk/services/analytics.py apps/api/tests/test_analytics_backlog.py apps/api/tests/factories.py
git commit -m "feat(analytics): reconstruct the backlog backwards from today"
```

---

### Task 7: The per-agent table

Spec §4.7. Attribution is by who **acted**, never by who the ticket is assigned to now, and the `assignee` filter does not apply.

**Files:**
- Modify: `apps/api/src/relaydesk/services/analytics.py`
- Test: `apps/api/tests/test_analytics_agents.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) AgentRow(user_id: uuid.UUID, name: str, handled: int, first_response_seconds: float | None, resolved: int)`
  - `async def agent_rows(session, workspace_id, window) -> list[AgentRow]`

- [ ] **Step 1: Write the failing tests**

```python
# apps/api/tests/test_analytics_agents.py
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.services import analytics
from relaydesk.services.analytics import Range, resolve_window
from tests.factories import make_conversation, make_member, make_workspace

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)


async def test_a_reply_is_credited_to_whoever_wrote_it_not_the_assignee(
    db_session: AsyncSession,
) -> None:
    """Sara answers and hands the ticket to Nilesh. The reply is Sara's."""
    workspace = await make_workspace(db_session)
    # `name` must be passed: make_member defaults it to "Nilesh Pant", which
    # would collide with the other member these tests create and break any
    # assertion keyed by name.
    sara = await make_member(
        db_session, workspace, email="sara@relaydesk.dev", name="Sara Duval"
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
    # `name` must be passed: make_member defaults it to "Nilesh Pant", which
    # would collide with the other member these tests create and break any
    # assertion keyed by name.
    sara = await make_member(
        db_session, workspace, email="sara@relaydesk.dev", name="Sara Duval"
    )
    nilesh = await make_member(
        db_session, workspace, email="nilesh@relaydesk.dev", name="Nilesh Pant"
    )
    conversation = await make_conversation(db_session, workspace)
    conversation.created_at = NOW - timedelta(minutes=10)
    await db_session.flush()
    await add_reply(db_session, workspace, conversation, at=NOW - timedelta(minutes=5), author=sara)
    await add_reply(db_session, workspace, conversation, at=NOW, author=nilesh)

    rows = {row.name: row for row in await analytics.agent_rows(
        db_session, workspace.id, resolve_window(Range.d7, NOW)
    )}

    assert rows[sara.name].first_response_seconds == 300
    assert rows[nilesh.name].first_response_seconds is None
    assert rows[nilesh.name].handled == 1


async def test_rows_are_ordered_by_how_much_was_handled(
    db_session: AsyncSession,
) -> None:
    workspace = await make_workspace(db_session)
    # `name` must be passed: make_member defaults it to "Nilesh Pant", which
    # would collide with the other member these tests create and break any
    # assertion keyed by name.
    sara = await make_member(
        db_session, workspace, email="sara@relaydesk.dev", name="Sara Duval"
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


async def test_a_resolution_is_credited_to_whoever_closed_it(
    db_session: AsyncSession,
) -> None:
    """`resolved` is a third of this table and nothing else here touches it.
    A wrong kind/status match, a non-distinct count, or the wrong timestamp
    column would otherwise reach the page unnoticed."""
    workspace = await make_workspace(db_session)
    sara = await make_member(
        db_session, workspace, email="sara@relaydesk.dev", name="Sara Duval"
    )
    conversation = await make_conversation(db_session, workspace)
    await add_reply(db_session, workspace, conversation, at=NOW, author=sara)
    await add_status(db_session, workspace, conversation, "resolved", NOW, sara)

    rows = await analytics.agent_rows(
        db_session, workspace.id, resolve_window(Range.d7, NOW)
    )

    assert [(row.name, row.handled, row.resolved) for row in rows] == [
        (sara.name, 1, 1)
    ]


async def test_resolving_without_replying_still_earns_a_row(
    db_session: AsyncSession,
) -> None:
    """Somebody who closes a ticket another agent answered has handled
    nothing and resolved one. The row exists because an action was taken,
    and the first-reply column is null because they never opened a thread."""
    workspace = await make_workspace(db_session)
    closer = await make_member(
        db_session, workspace, email="dana@relaydesk.dev", name="Dana Okafor"
    )
    conversation = await make_conversation(db_session, workspace)
    await add_status(db_session, workspace, conversation, "resolved", NOW, closer)

    rows = await analytics.agent_rows(
        db_session, workspace.id, resolve_window(Range.d7, NOW)
    )

    assert [(row.name, row.handled, row.resolved) for row in rows] == [
        (closer.name, 0, 1)
    ]
    assert rows[0].first_response_seconds is None


async def test_another_workspaces_agents_are_absent(db_session: AsyncSession) -> None:
    one = await make_workspace(db_session, slug="chronon")
    two = await make_workspace(db_session, slug="northwind")
    other = await make_member(db_session, two, email="elsewhere@northwind.io")
    conversation = await make_conversation(db_session, two)
    await add_reply(db_session, two, conversation, at=NOW, author=other)

    rows = await analytics.agent_rows(
        db_session, one.id, resolve_window(Range.d7, NOW)
    )

    assert rows == []
```

Extend the shared `add_reply` helper with an `author: User | None = None`
parameter that sets `author_user_id` and `author_name`.

- [ ] **Step 2: Run and watch them fail**

Run: `docker compose exec api python -m pytest tests/test_analytics_agents.py -q`
Expected: `AttributeError: ... has no attribute 'agent_rows'`.

- [ ] **Step 3: Implement**

```python
@dataclass(frozen=True, slots=True)
class AgentRow:
    user_id: uuid.UUID
    name: str
    handled: int
    first_response_seconds: float | None
    resolved: int


async def agent_rows(
    session: AsyncSession, workspace_id: uuid.UUID, window: Window
) -> list[AgentRow]:
    """Who did what in the window.

    Attributed by action -- `messages.author_user_id` and
    `activity_events.actor_user_id` -- not by `conversations.assignee_id`. A
    ticket answered and handed on is the answerer's work. For the same
    reason `Filters` is not a parameter here: narrowing a per-agent
    breakdown to one agent leaves a table with one row.
    """
    handled = await session.execute(
        sa.select(
            Message.author_user_id,
            sa.func.count(sa.distinct(Message.conversation_id)),
        )
        .where(
            Message.workspace_id == workspace_id,
            Message.direction == "outbound",
            Message.role.in_(REPLY_ROLES),
            Message.author_user_id.is_not(None),
            Message.sent_at >= window.start,
            Message.sent_at < window.end,
        )
        .group_by(Message.author_user_id)
    )

    # DISTINCT ON gives the first reply per thread together with its author,
    # which a MIN() aggregate cannot -- the aggregate loses the row.
    first = (
        sa.select(Message.conversation_id, Message.sent_at, Message.author_user_id)
        .where(
            Message.workspace_id == workspace_id,
            Message.direction == "outbound",
            Message.role.in_(REPLY_ROLES),
        )
        .distinct(Message.conversation_id)
        .order_by(Message.conversation_id, Message.sent_at)
        .subquery()
    )
    responses = await session.execute(
        sa.select(
            first.c.author_user_id,
            sa.func.avg(
                sa.func.extract("epoch", first.c.sent_at - Conversation.created_at)
            ),
        )
        .select_from(first)
        .join(Conversation, Conversation.id == first.c.conversation_id)
        .where(
            first.c.author_user_id.is_not(None),
            first.c.sent_at >= window.start,
            first.c.sent_at < window.end,
        )
        .group_by(first.c.author_user_id)
    )

    resolved = await session.execute(
        sa.select(
            ActivityEvent.actor_user_id,
            sa.func.count(sa.distinct(ActivityEvent.conversation_id)),
        )
        .where(
            ActivityEvent.workspace_id == workspace_id,
            ActivityEvent.kind == "status",
            ActivityEvent.status == "resolved",
            ActivityEvent.actor_user_id.is_not(None),
            ActivityEvent.at >= window.start,
            ActivityEvent.at < window.end,
        )
        .group_by(ActivityEvent.actor_user_id)
    )

    by_user = {user_id: int(count) for user_id, count in handled.all()}
    means = {user_id: float(value) for user_id, value in responses.all() if value}
    closes = {user_id: int(count) for user_id, count in resolved.all()}

    names = dict(
        (
            await session.execute(
                sa.select(User.id, User.name).where(
                    User.id.in_(set(by_user) | set(closes))
                )
            )
        ).all()
    )

    rows = [
        AgentRow(
            user_id=user_id,
            name=names.get(user_id, "Removed member"),
            handled=by_user.get(user_id, 0),
            first_response_seconds=means.get(user_id),
            resolved=closes.get(user_id, 0),
        )
        for user_id in set(by_user) | set(closes)
    ]
    return sorted(rows, key=lambda row: (-row.handled, row.name))
```

Add `User` to the model imports at the top of the module.

- [ ] **Step 4: Run and watch them pass**

Run: `docker compose exec api python -m pytest tests/test_analytics_agents.py -q`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/relaydesk/services/analytics.py apps/api/tests/test_analytics_agents.py apps/api/tests/factories.py
git commit -m "feat(analytics): credit replies and resolutions to who did them"
```

---

### Task 8: Headlines, deltas, and the endpoint

**Files:**
- Create: `apps/api/src/relaydesk/schemas/analytics.py`, `apps/api/src/relaydesk/api/analytics.py`
- Modify: `apps/api/src/relaydesk/services/analytics.py`, `apps/api/src/relaydesk/api/router.py`
- Test: `apps/api/tests/test_analytics_api.py`

**Interfaces:**
- Produces: `GET /api/analytics?range=&assignee=` returning `AnalyticsOut`, and `async def report(session, workspace_id, range_, filters, now) -> Report`.
- Headline formatting: counts are `str(int)`. Durations are `"8m 24s"` under an hour, `"4h 12m"` at or above one, `"—"` when `None`.
- `delta` is `round((current - previous) / previous * 100)`, `None` when `previous` is zero or either side is `None`.

- [ ] **Step 1: Write the failing tests**

```python
# apps/api/tests/test_analytics_api.py
from relaydesk.models import Role
from tests.factories import make_member, make_workspace, sign_in


async def admin_headers(client, db_session, workspace):
    await make_member(db_session, workspace, email="admin@relaydesk.dev")
    await db_session.commit()
    return await sign_in(client, db_session, "admin@relaydesk.dev")


async def test_the_report_carries_six_series_and_an_agent_table(
    client, db_session
) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)

    response = await client.get("/api/analytics", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert [series["id"] for series in body["series"]] == [
        "tickets-created",
        "tickets-responded",
        "tickets-resolved",
        "first-response",
        "resolution-time",
        "backlog",
    ]
    assert "agents" in body


async def test_an_empty_workspace_reports_zeroes_and_no_deltas(
    client, db_session
) -> None:
    """No division by zero, and no "+100%" invented out of nothing."""
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)

    body = (await client.get("/api/analytics", headers=headers)).json()

    for series in body["series"]:
        assert series["delta"] is None, series["id"]
        assert all(point["value"] == 0 for point in series["points"])
    assert body["agents"] == []


async def test_the_range_sets_the_number_of_points(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)

    for range_, points in [("7d", 7), ("30d", 30), ("90d", 13), ("12m", 12)]:
        body = (
            await client.get(f"/api/analytics?range={range_}", headers=headers)
        ).json()
        assert len(body["series"][0]["points"]) == points, range_


async def test_an_agent_cannot_read_the_report(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    await make_member(
        db_session, workspace, email="agent@relaydesk.dev", role=Role.agent
    )
    await db_session.commit()
    headers = await sign_in(client, db_session, "agent@relaydesk.dev")

    response = await client.get("/api/analytics", headers=headers)

    assert response.status_code == 403


async def test_the_report_requires_a_session(client, db_session) -> None:
    await make_workspace(db_session)

    assert (await client.get("/api/analytics")).status_code == 401


async def test_an_unknown_range_is_a_422(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)

    response = await client.get("/api/analytics?range=all-time", headers=headers)

    assert response.status_code == 422


async def test_an_assignee_from_another_workspace_is_a_422(
    client, db_session
) -> None:
    """Not an empty result. A stale console must not silently render zeroes,
    and an id that is not ours must not be answerable by timing."""
    workspace = await make_workspace(db_session)
    other = await make_workspace(db_session, slug="northwind")
    stranger = await make_member(db_session, other, email="elsewhere@northwind.io")
    headers = await admin_headers(client, db_session, workspace)

    response = await client.get(
        f"/api/analytics?assignee={stranger.id}", headers=headers
    )

    assert response.status_code == 422


async def test_unassigned_is_accepted_as_an_assignee(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)

    response = await client.get("/api/analytics?assignee=unassigned", headers=headers)

    assert response.status_code == 200


async def test_the_agent_table_ignores_the_assignee_filter(
    client, db_session
) -> None:
    """Spec D3. Narrowing a per-agent breakdown to one agent leaves a table
    with one row, which answers nothing -- so the filter moves the cards and
    leaves the table alone."""
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)
    # `name` must be passed: make_member defaults it to "Nilesh Pant", which
    # would collide with the other member these tests create and break any
    # assertion keyed by name.
    sara = await make_member(
        db_session, workspace, email="sara@relaydesk.dev", name="Sara Duval"
    )
    conversation = await make_conversation(db_session, workspace)
    await add_reply(db_session, workspace, conversation, at=NOW, author=sara)
    await db_session.commit()

    everyone = (await client.get("/api/analytics", headers=headers)).json()
    filtered = (
        await client.get("/api/analytics?assignee=unassigned", headers=headers)
    ).json()

    assert everyone["agents"] == filtered["agents"]
    assert len(everyone["agents"]) == 1
```

Import `make_conversation` and the shared `add_reply` helper (moved to
`tests/factories.py` in Task 6) at the top of this module, and define
`NOW = datetime.now(UTC)` — this test asserts equality of two live
responses, so it does not depend on a frozen clock.

Plus a unit test module for the formatting, in the same file:

```python
from relaydesk.services.analytics import format_duration, percent_delta


def test_a_duration_under_an_hour_reads_in_minutes_and_seconds() -> None:
    assert format_duration(504) == "8m 24s"


def test_a_duration_over_an_hour_reads_in_hours_and_minutes() -> None:
    """`4h 12m`, not `252m 0s`. Resolution times run to hours."""
    assert format_duration(15120) == "4h 12m"


def test_a_missing_duration_reads_as_a_dash() -> None:
    assert format_duration(None) == "—"


def test_a_delta_against_nothing_is_none() -> None:
    """A percentage change from zero is not a number."""
    assert percent_delta(12, 0) is None
    assert percent_delta(12, None) is None


def test_a_delta_is_a_rounded_percentage() -> None:
    assert percent_delta(112, 100) == 12
    assert percent_delta(78, 100) == -22
```

- [ ] **Step 2: Run and watch them fail**

Run: `docker compose exec api python -m pytest tests/test_analytics_api.py -q`
Expected: 404s on every route test, ImportError on the formatting tests.

- [ ] **Step 3: Implement the formatting and the report assembler**

Append to `services/analytics.py`:

```python
#: Card order on the page, and the vocabulary the console renders. `hint`
#: matches the copy the mock shipped, so nothing on screen changes wording.
SERIES_SPEC = [
    ("tickets-created", "Tickets created", None, "count"),
    (
        "tickets-responded",
        "Tickets responded",
        "Tickets that received at least one reply from an agent or the AI.",
        "count",
    ),
    ("tickets-resolved", "Tickets resolved", None, "count"),
    (
        "first-response",
        "Avg first response time",
        "Measured from ingestion to the first outbound message.",
        "duration",
    ),
    (
        "resolution-time",
        "Avg time to resolve",
        "Measured from ingestion to the moment it was marked resolved.",
        "duration",
    ),
    ("backlog", "Open backlog", None, "count"),
]


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    total = int(round(seconds))
    hours, rest = divmod(total, 3600)
    minutes, remainder = divmod(rest, 60)
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m {remainder}s"


def percent_delta(current: float | None, previous: float | None) -> int | None:
    """`None` rather than a number when there is nothing to compare against.

    A workspace's first period has no previous one, and a change from zero
    is not a percentage. `MetricCard` already renders a null delta as no
    delta at all.
    """
    if current is None or not previous:
        return None
    return round((current - previous) / previous * 100)
```

Then the assembler, also in `services/analytics.py`:

```python
@dataclass(frozen=True, slots=True)
class Series:
    id: str
    label: str
    hint: str | None
    headline: str
    delta: int | None
    format: str
    points: list[tuple[datetime, float]]


@dataclass(frozen=True, slots=True)
class Report:
    series: list[Series]
    agents: list[AgentRow]


def _previous(window: Window) -> Window:
    return Window(
        start=window.previous_start,
        end=window.start,
        bucket=window.bucket,
        previous_start=window.previous_start,
    )


async def report(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    range_: Range,
    filters: Filters,
    now: datetime,
) -> Report:
    window = resolve_window(range_, now)
    previous = _previous(window)

    built: dict[str, tuple[str, int | None, list[tuple[datetime, float]]]] = {}

    for metric, key in [
        (CountMetric.created, "tickets-created"),
        (CountMetric.responded, "tickets-responded"),
        (CountMetric.resolved, "tickets-resolved"),
    ]:
        values = await counts(session, workspace_id, window, filters, metric)
        before = await counts(session, workspace_id, previous, filters, metric)
        total = sum(values.values())
        built[key] = (
            str(total),
            percent_delta(total, sum(before.values())),
            filled(values, window),
        )

    for metric, key in [
        (DurationMetric.first_response, "first-response"),
        (DurationMetric.resolution, "resolution-time"),
    ]:
        values = await durations(session, workspace_id, window, filters, metric)
        mean = await duration_mean(
            session, workspace_id, window.start, window.end, filters, metric
        )
        before = await duration_mean(
            session, workspace_id, previous.start, previous.end, filters, metric
        )
        built[key] = (
            format_duration(mean),
            # A duration falling is an improvement, but the sign stays
            # honest here -- MetricCard flips the colour, not the number.
            percent_delta(mean, before),
            filled(values, window),
        )

    # Backlog is a level, not a flow, so its headline is the newest point and
    # its delta compares that against the newest point of the previous
    # period. Both come from a single walk across both periods: `backlog()`
    # anchors on *today* and steps backwards, so asking it for the previous
    # window alone would start from today's count and skip every event
    # between that window's end and now.
    span = Window(
        start=previous.start,
        end=window.end,
        bucket=window.bucket,
        previous_start=previous.start,
    )
    levels = await backlog(session, workspace_id, span, filters)
    current_starts = bucket_starts(window)
    latest = levels[current_starts[-1]]
    built["backlog"] = (
        str(latest),
        percent_delta(latest, levels[bucket_starts(previous)[-1]]),
        [(start, levels[start]) for start in current_starts],
    )

    return Report(
        series=[
            Series(
                id=key,
                label=label,
                hint=hint,
                headline=built[key][0],
                delta=built[key][1],
                format=fmt,
                points=built[key][2],
            )
            for key, label, hint, fmt in SERIES_SPEC
        ],
        agents=await agent_rows(session, workspace_id, window),
    )
```

`schemas/analytics.py`:

```python
from relaydesk.schemas.base import CamelModel


class MetricPointOut(CamelModel):
    date: str
    value: float


class MetricSeriesOut(CamelModel):
    id: str
    label: str
    hint: str | None = None
    #: Preformatted by the API ("412", "8m 24s"). The console prints it
    #: verbatim; `format` drives the axis, not this.
    headline: str
    delta: int | None
    format: str
    points: list[MetricPointOut]


class AgentRowOut(CamelModel):
    user_id: str
    name: str
    handled: int
    first_response_seconds: float | None
    resolved: int


class AnalyticsOut(CamelModel):
    series: list[MetricSeriesOut]
    agents: list[AgentRowOut]
```

`api/analytics.py`:

```python
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter

from relaydesk.api.deps import DbSession, Scope
from relaydesk.errors import Invalid
from relaydesk.schemas.analytics import (
    AgentRowOut,
    AnalyticsOut,
    MetricPointOut,
    MetricSeriesOut,
)
from relaydesk.services import analytics, team

router = APIRouter()

#: The console's own word for "no assignee". Not a UUID, so it cannot
#: collide with one.
UNASSIGNED = "unassigned"


def _parsed_range(raw: str) -> analytics.Range:
    try:
        return analytics.Range(raw)
    except ValueError:
        raise Invalid(f"Unknown range {raw!r}.") from None


async def _parsed_filters(
    session: DbSession, scope: Scope, raw: str | None
) -> analytics.Filters:
    if raw is None:
        return analytics.Filters(assignee_id=None, unassigned=False)
    if raw == UNASSIGNED:
        return analytics.Filters(assignee_id=None, unassigned=True)
    try:
        assignee_id = uuid.UUID(raw)
    except ValueError:
        raise Invalid(f"Unknown assignee {raw!r}.") from None

    # Refused rather than answered with zeroes: a stale console must not
    # render an empty page that looks like a quiet month, and an id from
    # another tenant must not be distinguishable from a made-up one.
    members = await team.list_members(session, scope.workspace_id)
    if not any(member.user_id == assignee_id for member in members):
        raise Invalid("That assignee is not a member of this workspace.")
    return analytics.Filters(assignee_id=assignee_id, unassigned=False)


@router.get("", response_model=AnalyticsOut)
async def read_route(
    scope: Scope,
    session: DbSession,
    range: str = "30d",
    assignee: str | None = None,
) -> AnalyticsOut:
    scope.require_admin()
    built = await analytics.report(
        session,
        scope.workspace_id,
        _parsed_range(range),
        await _parsed_filters(session, scope, assignee),
        datetime.now(UTC),
    )
    return AnalyticsOut(
        series=[
            MetricSeriesOut(
                id=series.id,
                label=series.label,
                hint=series.hint,
                headline=series.headline,
                delta=series.delta,
                format=series.format,
                points=[
                    MetricPointOut(date=at.date().isoformat(), value=value)
                    for at, value in series.points
                ],
            )
            for series in built.series
        ],
        agents=[
            AgentRowOut(
                user_id=str(row.user_id),
                name=row.name,
                handled=row.handled,
                first_response_seconds=row.first_response_seconds,
                resolved=row.resolved,
            )
            for row in built.agents
        ],
    )
```

Check `team.list_members`' real return shape at `services/team.py:45` before
writing `_parsed_filters` — if it returns rows rather than objects with
`.user_id`, adapt the membership check and keep the behaviour.

Mount it in `api/router.py` beside the others:

```python
api_router.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
```

- [ ] **Step 4: Run the analytics suite and lint**

```bash
docker compose exec api python -m pytest tests/test_analytics_api.py -q
docker compose exec api ruff check src tests
```
Expected: all PASS, `All checks passed!`.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/relaydesk/services/analytics.py apps/api/src/relaydesk/schemas/analytics.py apps/api/src/relaydesk/api/analytics.py apps/api/src/relaydesk/api/router.py apps/api/tests/test_analytics_api.py
git commit -m "feat(analytics): serve the report from GET /api/analytics"
```

---

### Task 9: Duration formatting and types in the console

Done before the page is wired, so the card can render an hour-scale metric the moment real data arrives.

**Files:**
- Modify: `apps/web/components/analytics/metric-card.tsx`, `apps/web/lib/types.ts`
- Test: `apps/web/components/analytics/metric-card.test.tsx` (create)

**Interfaces:**
- Produces: `AgentRow`, `AnalyticsResponse` in `lib/types.ts`.

- [ ] **Step 1: Write the failing test**

```tsx
// apps/web/components/analytics/metric-card.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MetricCard } from "./metric-card";
import type { MetricSeries } from "@/lib/types";

const series: MetricSeries = {
  id: "resolution-time",
  label: "Avg time to resolve",
  headline: "4h 12m",
  delta: -8,
  format: "duration",
  points: [{ date: "2026-08-30", value: 15120 }],
};

describe("MetricCard", () => {
  it("renders the headline the API formatted", () => {
    render(<MetricCard series={series} />);

    expect(screen.getByText("4h 12m")).toBeTruthy();
  });

  it("renders no delta at all when there is none", () => {
    // A workspace's first period has nothing to compare against. An arrow
    // pointing somewhere would be an invention.
    render(<MetricCard series={{ ...series, delta: null }} />);

    expect(screen.queryByText("%", { exact: false })).toBeNull();
  });
});
```

Add a test for the axis formatter by exporting `formatDuration` from the
component module and asserting `formatDuration(15120) === "4h 12m"` and
`formatDuration(504) === "8m 24s"`.

- [ ] **Step 2: Run and watch it fail**

Run: `cd apps/web && npx vitest run components/analytics/metric-card.test.tsx`
Expected: FAIL — `formatDuration` is not exported, and the hour case returns `"252m"`.

- [ ] **Step 3: Fix the formatter and the import**

In `metric-card.tsx`, change the type import from the deprecated
`@/lib/mock/types` shim to `@/lib/types`, and replace `formatDuration`:

```tsx
export function formatDuration(seconds: number) {
  // Mirrors `format_duration` in the API's services/analytics.py. Resolution
  // times run to hours, and a Y axis reading "252m" is not a reading.
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours > 0) return `${hours}h ${minutes}m`;
  const rest = Math.round(seconds % 60);
  return rest === 0 ? `${minutes}m` : `${minutes}m ${rest}s`;
}
```

Add to `lib/types.ts`:

```ts
export interface AgentRow {
  userId: string;
  name: string;
  handled: number;
  /** Null when this member never opened a thread; the table shows an em dash. */
  firstResponseSeconds: number | null;
  resolved: number;
}

export interface AnalyticsResponse {
  series: MetricSeries[];
  agents: AgentRow[];
}
```

- [ ] **Step 4: Run and watch it pass**

Run: `cd apps/web && npx vitest run components/analytics && npx tsc --noEmit`
Expected: PASS, no type errors.

- [ ] **Step 5: Commit**

```bash
git add apps/web/components/analytics/metric-card.tsx apps/web/components/analytics/metric-card.test.tsx apps/web/lib/types.ts
git commit -m "feat(web): read hour-scale durations on a metric card"
```

---

### Task 10: Wire the page and the filters

**Files:**
- Create: `apps/web/lib/api/analytics.ts`, `apps/web/components/analytics/agent-table.tsx`
- Modify: `apps/web/app/(console)/analytics/page.tsx`, `apps/web/components/analytics/analytics-filters.tsx`
- Delete: `apps/web/lib/mock/analytics.ts`
- Test: `apps/web/components/analytics/analytics-filters.test.tsx` (create)

**Interfaces:**
- Consumes: `AnalyticsResponse` (Task 9), `GET /api/analytics` (Task 8).
- Produces: `getAnalytics(range, assignee)` in `lib/api/analytics.ts`.

- [ ] **Step 1: Write the failing test**

```tsx
// apps/web/components/analytics/analytics-filters.test.tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AnalyticsFilters } from "./analytics-filters";

const { replace } = vi.hoisted(() => ({ replace: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/analytics",
  useSearchParams: () => new URLSearchParams("range=30d"),
}));

const team = [{ id: "u1", name: "Sara Duval" }];

beforeEach(() => replace.mockReset());

describe("AnalyticsFilters", () => {
  it("puts the chosen range in the URL so the server re-queries", () => {
    // The filter has to reach the server component that fetches. Local
    // state would change the select and nothing else.
    render(<AnalyticsFilters team={team} range="30d" assignee={null} />);

    fireEvent.click(screen.getByLabelText("Date range"));
    fireEvent.click(screen.getByRole("option", { name: "Last 7 days" }));

    expect(replace).toHaveBeenCalledWith("/analytics?range=7d");
  });
});
```

Radix's `Select` opens on `pointerdown`, which jsdom does not synthesise
from a click. If the test cannot drive the select, assert against the
`onValueChange` path instead by extracting the URL-building into an exported
pure function `filterHref(pathname, range, assignee)` and testing that
directly — a smaller, more honest unit than a Radix interaction.

- [ ] **Step 2: Run and watch it fail**

Run: `cd apps/web && npx vitest run components/analytics/analytics-filters.test.tsx`
Expected: FAIL — the component takes no props and calls no router.

- [ ] **Step 3: Implement**

`lib/api/analytics.ts`:

```ts
import "server-only";

import { apiFetch } from "./client";
import type { AnalyticsResponse } from "@/lib/types";

/** Not `cache`d: the range and assignee are the whole point, and two
 *  different filters are two different requests. */
export async function getAnalytics(
  range: string,
  assignee: string | null,
): Promise<AnalyticsResponse> {
  const query = new URLSearchParams({ range });
  if (assignee) query.set("assignee", assignee);
  return apiFetch<AnalyticsResponse>(`/analytics?${query}`);
}
```

`analytics-filters.tsx` — the URL builder is exported so it can be tested
without driving Radix:

```tsx
"use client";

import { CalendarDays, Users } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";

import { RANGES } from "@/lib/analytics";

/** The URL a filter change navigates to. Pure, so the routing decision is
 *  testable without a Select. Omits defaults so the common case is a clean
 *  `/analytics`. */
export function filterHref(
  pathname: string,
  range: string,
  assignee: string | null,
): string {
  const query = new URLSearchParams();
  if (range !== "30d") query.set("range", range);
  if (assignee) query.set("assignee", assignee);
  const suffix = query.toString();
  return suffix ? `${pathname}?${suffix}` : pathname;
}

export function AnalyticsFilters({
  team,
  range,
  assignee,
}: {
  team: { id: string; name: string }[];
  range: string;
  assignee: string | null;
}) {
  const router = useRouter();
  const pathname = usePathname();

  return (
    <div className="flex items-center gap-2">
      <Select
        value={assignee ?? "all"}
        onValueChange={(next) =>
          router.replace(filterHref(pathname, range, next === "all" ? null : next))
        }
      >
        <SelectTrigger className="w-44" aria-label="Filter by assignee">
          <span className="flex items-center gap-2 truncate">
            <Users className="size-3.5 shrink-0 text-ink-400" />
            <SelectValue />
          </span>
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All assignees</SelectItem>
          {team.map((member) => (
            <SelectItem key={member.id} value={member.id}>
              {member.name}
            </SelectItem>
          ))}
          <SelectItem value="unassigned">Unassigned</SelectItem>
        </SelectContent>
      </Select>

      <Select
        value={range}
        onValueChange={(next) => router.replace(filterHref(pathname, next, assignee))}
      >
        <SelectTrigger className="w-40" aria-label="Date range">
          <span className="flex items-center gap-2 truncate">
            <CalendarDays className="size-3.5 shrink-0 text-ink-400" />
            <SelectValue />
          </span>
        </SelectTrigger>
        <SelectContent>
          {RANGES.map((option) => (
            <SelectItem key={option.id} value={option.id}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
```

Keep the existing `Select` imports from the current file. Create
`apps/web/lib/analytics.ts` holding the range vocabulary that both the page
and the filters need — it replaces the deleted mock's `dateRanges`:

```ts
export const RANGES = [
  { id: "7d", label: "Last 7 days" },
  { id: "30d", label: "Last 30 days" },
  { id: "90d", label: "Last 90 days" },
  { id: "12m", label: "Last 12 months" },
] as const;

/** Anything else in the URL falls back rather than 422-ing the page: a
 *  hand-edited query string should not be an error screen. The API is the
 *  authority and refuses an unknown range on its own. */
export function safeRange(raw: string | undefined): string {
  return RANGES.some((option) => option.id === raw) ? raw! : "30d";
}
```

`page.tsx`:

```tsx
import { AgentTable } from "@/components/analytics/agent-table";
import { AnalyticsFilters } from "@/components/analytics/analytics-filters";
import { MetricCard } from "@/components/analytics/metric-card";
import { PageHeader } from "@/components/console/page-header";
import { PageShell } from "@/components/console/page-shell";
import { getAnalytics } from "@/lib/api/analytics";
import { getTeam } from "@/lib/api/team";
import { requireAdmin } from "@/lib/api/workspace";
import { safeRange } from "@/lib/analytics";

export const metadata = { title: "Analytics" };

export default async function AnalyticsPage({
  searchParams,
}: {
  searchParams: Promise<{ range?: string; assignee?: string }>;
}) {
  await requireAdmin();

  const params = await searchParams;
  const range = safeRange(params.range);
  const assignee = params.assignee ?? null;
  const [report, team] = await Promise.all([
    getAnalytics(range, assignee),
    getTeam(),
  ]);

  return (
    <PageShell>
      <PageHeader
        title="Analytics"
        description="Ticket volume and response health across the selected period."
        actions={
          <AnalyticsFilters team={team} range={range} assignee={assignee} />
        }
      />

      <div className="grid gap-4 lg:grid-cols-2">
        {report.series.map((series) => (
          <MetricCard key={series.id} series={series} />
        ))}
      </div>

      <AgentTable rows={report.agents} />
    </PageShell>
  );
}
```

`getTeam()` returns the console's team shape — check it in `lib/api/team.ts`
and map it to `{ id, name }` here if the field names differ.

`agent-table.tsx`:

```tsx
import { formatDuration } from "@/components/analytics/metric-card";
import type { AgentRow } from "@/lib/types";

/** The §4.7 table. Every column counts an action, so the headings say so —
 *  these are not the tickets somebody is holding, they are the ones they
 *  worked. There is deliberately no "Unassigned" row: an action has an
 *  actor. */
export function AgentTable({ rows }: { rows: AgentRow[] }) {
  return (
    <section className="rounded-lg border border-ink-200 bg-white p-5">
      <h2 className="text-[13px] font-medium text-ink-600">By agent</h2>
      {rows.length > 0 ? (
        <table className="mt-3 w-full">
          <thead>
            <tr className="border-b border-ink-200 text-left">
              <th className="pb-2 text-[11px] font-semibold uppercase tracking-wider text-ink-400">
                Agent
              </th>
              {["Replied to", "First reply", "Resolved"].map((heading) => (
                <th
                  key={heading}
                  className="w-32 pb-2 text-right text-[11px] font-semibold uppercase tracking-wider text-ink-400"
                >
                  {heading}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.userId} className="border-b border-ink-200 last:border-b-0">
                <td className="py-2.5 text-[13px] font-medium text-ink-900">
                  {row.name}
                </td>
                <td className="tabular py-2.5 text-right text-[13px] text-ink-600">
                  {row.handled}
                </td>
                <td className="tabular py-2.5 text-right text-[13px] text-ink-600">
                  {row.firstResponseSeconds === null
                    ? "—"
                    : formatDuration(row.firstResponseSeconds)}
                </td>
                <td className="tabular py-2.5 text-right text-[13px] text-ink-600">
                  {row.resolved}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="mt-3 text-[13px] text-ink-500">
          No replies or resolutions in this period.
        </p>
      )}
    </section>
  );
}
```

Delete `lib/mock/analytics.ts`. Confirm nothing else imports it:

```bash
grep -rn "mock/analytics" apps/web --include="*.tsx" --include="*.ts"
```

- [ ] **Step 4: Verify the whole console**

```bash
cd apps/web && npx vitest run && npx eslint . && npx tsc --noEmit
```
Expected: all PASS, eslint silent, no type errors.

- [ ] **Step 5: Commit**

```bash
git add apps/web
git commit -m "feat(web): read analytics from the API, and filter it from the URL"
```

---

### Task 11: End-to-end check and the full suites

- [ ] **Step 1: Run both suites**

```bash
docker compose exec api python -m pytest -q
cd apps/web && npx vitest run
```

Expected: the analytics tests pass. **11 API tests fail before this work
starts** — `test_mailer`, `test_outbound`, `test_channel_accounts` and
`test_config` — because the deployment's gitignored `.env` points at real
SES rather than greenmail. Confirm the count is still 11 and the names are
the same; anything else is yours.

- [ ] **Step 2: Look at the page**

Seed if the workspace is empty, then open `http://localhost:3000/analytics`
as an admin and check: six cards, each with a headline and a sparkline; the
backlog card's last point equals the open count in the inbox; changing the
range changes the number of points; changing the assignee changes the cards
but leaves the agent table alone.

- [ ] **Step 3: Commit anything the check turned up**

---

## Out of scope for this plan

Named so nobody adds them mid-flight: rollups or caching, CSV export,
per-label/channel/priority breakdowns, a workspace timezone, SLA targets,
and making `MessageRole.ai` real.
