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


def test_previous_start_is_bucket_aligned_not_a_literal_duration_back() -> None:
    """12 months before 2023-04-01 is 2022-04-01 by bucket counting, but
    ``start - (end - start)`` would give 2022-03-31: April has 30 days and
    March has 31, so subtracting "the window's length" drifts off the 1st.
    ``previous_start`` must stay bucket-aligned to feed back into
    `bucket_starts` and to join against `date_trunc` output, so this is not
    a bug to "fix" back to the literal duration."""
    window = resolve_window(Range.m12, datetime(2024, 3, 15, tzinfo=UTC))

    assert window.previous_start == datetime(2022, 4, 1, tzinfo=UTC)
    assert window.previous_start != window.start - (window.end - window.start)


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
