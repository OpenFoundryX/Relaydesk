from datetime import UTC, datetime

from relaydesk.models import Role
from relaydesk.services.analytics import format_duration, percent_delta
from tests.factories import (
    add_reply,
    make_conversation,
    make_member,
    make_workspace,
    sign_in,
)

NOW = datetime.now(UTC)


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
    sara = await make_member(db_session, workspace, email="sara@relaydesk.dev")
    conversation = await make_conversation(db_session, workspace)
    await add_reply(db_session, workspace, conversation, at=NOW, author=sara)
    await db_session.commit()

    everyone = (await client.get("/api/analytics", headers=headers)).json()
    filtered = (
        await client.get("/api/analytics?assignee=unassigned", headers=headers)
    ).json()

    assert everyone["agents"] == filtered["agents"]
    assert len(everyone["agents"]) == 1


async def test_a_real_assignee_narrows_the_cards(client, db_session) -> None:
    """A regression guard for `_parsed_filters` comparing a parsed
    `uuid.UUID` against `TeamMember.user_id`, which is a `str` -- that
    comparison is always `False`, so every real, in-workspace assignee was
    rejected with a 422 and the whole filter was dead. Asserted as "fewer
    than the unfiltered total" rather than a hardcoded count, so this does
    not depend on how `make_conversation` stamps `created_at`."""
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)
    sara = await make_member(db_session, workspace, email="sara@relaydesk.dev")
    await make_conversation(db_session, workspace, assignee=sara)
    await make_conversation(db_session, workspace, contact_email="other@northwind.io")

    response = await client.get(
        f"/api/analytics?assignee={sara.id}", headers=headers
    )
    everyone = (await client.get("/api/analytics", headers=headers)).json()

    assert response.status_code == 200, response.text
    filtered = response.json()
    filtered_total = int(filtered["series"][0]["headline"])
    everyone_total = int(everyone["series"][0]["headline"])
    assert filtered["series"][0]["id"] == "tickets-created"
    assert filtered_total < everyone_total


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
