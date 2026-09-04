import uuid
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Invalid, NotFound
from relaydesk.models import Label, Membership, MembershipStatus, Workspace


async def active_seat_count(session: AsyncSession, workspace_id: uuid.UUID) -> int:
    """Count users with an active membership in the workspace."""
    count = await session.scalar(
        sa.select(sa.func.count())
        .select_from(Membership)
        .where(
            Membership.workspace_id == workspace_id,
            Membership.status == MembershipStatus.active,
        )
    )
    return count or 0


@dataclass(slots=True)
class SetupTask:
    id: str
    label: str
    href: str
    done: bool


async def setup_tasks(
    session: AsyncSession, workspace_id: uuid.UUID
) -> list[SetupTask]:
    """The sidebar checklist, computed rather than stored.

    Tasks whose subsystem does not exist yet report ``done: False``; their
    slices flip them by making the underlying count real.
    """
    members = await session.scalar(
        sa.select(sa.func.count())
        .select_from(Membership)
        .where(
            Membership.workspace_id == workspace_id,
            Membership.status == MembershipStatus.active,
        )
    )
    labels = await session.scalar(
        sa.select(sa.func.count())
        .select_from(Label)
        .where(Label.workspace_id == workspace_id)
    )

    return [
        SetupTask("channel", "Connect a channel", "/settings/channels", False),
        SetupTask("team", "Invite your team", "/settings/team", (members or 0) > 1),
        SetupTask(
            "integrations", "Connect an integration", "/settings/integrations", False
        ),
        SetupTask(
            "labels", "Create your first label", "/conversations", (labels or 0) > 0
        ),
        SetupTask("portal", "Launch your user portal", "/user-portal/general", False),
        SetupTask("triage", "Turn on AI triage", "/settings/ai-triage", False),
        SetupTask("billing", "Choose a plan", "/settings/billing", False),
    ]


def _valid_timezone(value: str) -> str:
    """Reject anything ``ZoneInfo`` cannot load.

    Every conversation, message and activity serializer resolves the
    workspace timezone with ``ZoneInfo(...)``. An unvalidated string stored
    here would therefore 500 the whole inbox for every member until an
    admin corrected it, so the bad value never reaches the column.
    """
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise Invalid("That is not a recognised IANA time zone.") from error
    return value


async def update_workspace(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    name: str | None,
    timezone: str | None,
) -> Workspace:
    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise NotFound("Workspace not found.")
    if name is not None:
        workspace.name = name
    if timezone is not None:
        workspace.timezone = _valid_timezone(timezone)
    await session.commit()
    return workspace
