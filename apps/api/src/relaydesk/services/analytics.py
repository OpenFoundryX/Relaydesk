"""Ranges, windows and buckets shared by every analytics query.

A caller picks a ``Range`` (a UI concept: "last 30 days"); ``resolve_window``
turns that into a ``Window`` (a query concept: the half-open interval to
filter on, and the bucket size to group by). Every later analytics query
builds on the ``Window`` this module produces, so a wrong bucket boundary
here silently corrupts every chart downstream — hence this module is pure
arithmetic with no database access, easy to test exhaustively on its own.
"""

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
    """Step ``start`` back by ``count`` buckets. A negative ``count`` steps
    forward instead, which is how ``resolve_window`` finds the window's
    exclusive end and ``bucket_starts`` walks forward through it."""
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
