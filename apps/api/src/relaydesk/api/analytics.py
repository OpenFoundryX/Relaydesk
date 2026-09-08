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
    # `team.list_members` returns `TeamMember` rows whose `user_id` is a
    # string (or None for a pending invite), so the membership check
    # compares against the string form rather than the parsed UUID.
    members = await team.list_members(session, scope.workspace_id)
    if not any(member.user_id == str(assignee_id) for member in members):
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
