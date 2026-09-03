import uuid
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import NotFound
from relaydesk.models import Membership, MembershipStatus, Workspace


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
    # Label is introduced in Task 7. Hardcoded until then; the setup-tasks
    # test in Task 6 does not assert on the labels task, so this keeps the
    # suite green without a forward reference to a model that doesn't exist.
    members = await session.scalar(
        sa.select(sa.func.count())
        .select_from(Membership)
        .where(
            Membership.workspace_id == workspace_id,
            Membership.status == MembershipStatus.active,
        )
    )
    labels = 0

    return [
        SetupTask("channel", "Connect a channel", "/settings/channels", False),
        SetupTask("team", "Invite your team", "/settings/team", (members or 0) > 1),
        SetupTask(
            "integrations", "Connect an integration", "/settings/integrations", False
        ),
        SetupTask("labels", "Create your first label", "/conversations", labels > 0),
        SetupTask("portal", "Launch your user portal", "/user-portal/general", False),
        SetupTask("triage", "Turn on AI triage", "/settings/ai-triage", False),
        SetupTask("billing", "Choose a plan", "/settings/billing", False),
    ]


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
        workspace.timezone = timezone
    await session.commit()
    return workspace
