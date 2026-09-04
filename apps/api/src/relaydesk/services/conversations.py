import base64
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Invalid, NotFound
from relaydesk.models import (
    ActivityEvent,
    Conversation,
    ConversationLabel,
    ConversationStatus,
    Draft,
    Message,
)

DEFAULT_LIMIT = 50


def encode_cursor(conversation: Conversation) -> str:
    raw = f"{conversation.last_message_at.isoformat()}|{conversation.id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    moment, identifier = raw.split("|", 1)
    return datetime.fromisoformat(moment), uuid.UUID(identifier)


async def list_conversations(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    status: ConversationStatus | None = None,
    label_id: uuid.UUID | None = None,
    assignee_id: uuid.UUID | None = None,
    has_draft: bool | None = None,
    include_trash: bool = False,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> tuple[list[Conversation], str | None]:
    """Keyset-paginated inbox list, newest first.

    Ordering by ``(last_message_at, id)`` makes the cursor stable even when
    two conversations share a timestamp.

    ``include_trash`` has no caller yet: every route today either passes an
    explicit ``status`` or relies on the default (trash excluded). It is
    plumbed through for a future "trash" view, not evidence one exists.
    """
    query = sa.select(Conversation).where(Conversation.workspace_id == workspace_id)

    if status is not None:
        query = query.where(Conversation.status == status)
    elif not include_trash:
        query = query.where(Conversation.status != ConversationStatus.trash)

    if label_id is not None:
        query = query.join(
            ConversationLabel, ConversationLabel.conversation_id == Conversation.id
        ).where(ConversationLabel.label_id == label_id)
    if assignee_id is not None:
        query = query.where(Conversation.assignee_id == assignee_id)
    if has_draft:
        query = query.join(Draft, Draft.conversation_id == Conversation.id)

    if cursor:
        try:
            moment, identifier = decode_cursor(cursor)
        except ValueError as error:
            # binascii.Error and UnicodeDecodeError both subclass ValueError,
            # so this also catches a malformed base64 payload.
            raise Invalid("Invalid cursor.") from error
        query = query.where(
            sa.tuple_(Conversation.last_message_at, Conversation.id)
            < (moment, identifier)
        )

    query = query.order_by(
        Conversation.last_message_at.desc(), Conversation.id.desc()
    ).limit(limit + 1)

    rows = list(await session.scalars(query))
    next_cursor = encode_cursor(rows[limit - 1]) if len(rows) > limit else None
    return rows[:limit], next_cursor


async def get_conversation(
    session: AsyncSession, workspace_id: uuid.UUID, conversation_id: uuid.UUID
) -> Conversation:
    """Cross-workspace ids raise NotFound, never Forbidden."""
    conversation = await session.scalar(
        sa.select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.workspace_id == workspace_id,
        )
    )
    if conversation is None:
        raise NotFound("Conversation not found.")
    return conversation


async def list_messages(
    session: AsyncSession, workspace_id: uuid.UUID, conversation_id: uuid.UUID
) -> list[Message]:
    await get_conversation(session, workspace_id, conversation_id)
    return list(
        await session.scalars(
            sa.select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.workspace_id == workspace_id,
            )
            .order_by(Message.sent_at)
        )
    )


async def get_draft(
    session: AsyncSession, workspace_id: uuid.UUID, conversation_id: uuid.UUID
) -> Draft:
    await get_conversation(session, workspace_id, conversation_id)
    draft = await session.scalar(
        sa.select(Draft).where(
            Draft.conversation_id == conversation_id,
            Draft.workspace_id == workspace_id,
        )
    )
    if draft is None:
        raise NotFound("No draft for this conversation.")
    return draft


async def list_activity(
    session: AsyncSession, workspace_id: uuid.UUID, conversation_id: uuid.UUID
) -> list[ActivityEvent]:
    await get_conversation(session, workspace_id, conversation_id)
    return list(
        await session.scalars(
            sa.select(ActivityEvent)
            .where(
                ActivityEvent.conversation_id == conversation_id,
                ActivityEvent.workspace_id == workspace_id,
            )
            .order_by(ActivityEvent.at.desc())
        )
    )


async def status_counts(
    session: AsyncSession, workspace_id: uuid.UUID
) -> dict[ConversationStatus, int]:
    rows = await session.execute(
        sa.select(Conversation.status, sa.func.count())
        .where(Conversation.workspace_id == workspace_id)
        .group_by(Conversation.status)
    )
    counted = dict(rows.all())
    return {status: counted.get(status, 0) for status in ConversationStatus}


async def draft_count(session: AsyncSession, workspace_id: uuid.UUID) -> int:
    return (
        await session.scalar(
            sa.select(sa.func.count())
            .select_from(Draft)
            .join(Conversation, Conversation.id == Draft.conversation_id)
            .where(
                Draft.workspace_id == workspace_id,
                Conversation.status != ConversationStatus.trash,
            )
        )
    ) or 0
