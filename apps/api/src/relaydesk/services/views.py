import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import NotFound
from relaydesk.models import Conversation, ConversationStatus, Priority, SavedView, User


async def list_views(session: AsyncSession, workspace_id: uuid.UUID) -> list[SavedView]:
    return list(
        await session.scalars(
            sa.select(SavedView)
            .where(SavedView.workspace_id == workspace_id)
            .order_by(SavedView.position, SavedView.name)
        )
    )


async def get_view(
    session: AsyncSession, workspace_id: uuid.UUID, view_id: uuid.UUID
) -> SavedView:
    view = await session.scalar(
        sa.select(SavedView).where(
            SavedView.id == view_id, SavedView.workspace_id == workspace_id
        )
    )
    if view is None:
        raise NotFound("View not found.")
    return view


def apply_view(query: sa.Select, view: SavedView, viewer: User) -> sa.Select:
    """Narrow a conversation query by a stored filter definition.

    Filters are a small closed vocabulary rather than arbitrary SQL, so a
    stored view can never widen its own scope beyond the workspace. Unknown
    keys and values are ignored rather than raised: ``filters`` is
    hand-editable JSONB, and a stray or future key should degrade to "no
    extra narrowing" rather than 500 the whole view list.
    """
    filters = view.filters or {}

    status = filters.get("status")
    if status is None:
        query = query.where(Conversation.status != ConversationStatus.trash)
    else:
        try:
            query = query.where(Conversation.status == ConversationStatus(status))
        except ValueError:
            pass  # Unrecognised status: ignore rather than 500 on stray JSONB.

    priority = filters.get("priority")
    if priority is not None:
        try:
            query = query.where(Conversation.priority == Priority(priority))
        except ValueError:
            pass  # Unrecognised priority: ignore, same reasoning as status.

    assignee = filters.get("assignee")
    if assignee == "unassigned":
        query = query.where(Conversation.assignee_id.is_(None))
    elif assignee == "me":
        query = query.where(Conversation.assignee_id == viewer.id)

    return query


async def count_for_view(
    session: AsyncSession, workspace_id: uuid.UUID, view: SavedView, viewer: User
) -> int:
    query = sa.select(Conversation.id).where(Conversation.workspace_id == workspace_id)
    query = apply_view(query, view, viewer)
    return (
        await session.scalar(sa.select(sa.func.count()).select_from(query.subquery()))
    ) or 0
