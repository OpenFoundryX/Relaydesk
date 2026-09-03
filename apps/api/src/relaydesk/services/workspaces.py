import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models import Membership, MembershipStatus


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
