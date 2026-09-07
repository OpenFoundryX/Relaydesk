import base64
import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Invalid, NotFound
from relaydesk.models import (
    ActivityEvent,
    ActivityKind,
    Channel,
    Contact,
    Conversation,
    ConversationLabel,
    ConversationStatus,
    DeliveryState,
    Draft,
    Label,
    Membership,
    MembershipStatus,
    Message,
    MessageDirection,
    MessageRole,
    Priority,
    User,
    Workspace,
)
from relaydesk.services import notifications, outbound, queue
from relaydesk.services.actors import Actor

DEFAULT_LIMIT = 50


def encode_cursor(conversation: Conversation) -> str:
    raw = f"{conversation.last_message_at.isoformat()}|{conversation.id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    moment, identifier = raw.split("|", 1)
    return datetime.fromisoformat(moment), uuid.UUID(identifier)


async def allocate_number(session: AsyncSession, workspace_id: uuid.UUID) -> int:
    """Per-workspace sequential ticket number.

    Allocated with UPDATE ... RETURNING inside the caller's transaction, so
    concurrent inserts cannot collide and ticket volume does not leak across
    tenants the way a global sequence would.
    """
    number = await session.scalar(
        sa.update(Workspace)
        .where(Workspace.id == workspace_id)
        .values(conversation_seq=Workspace.conversation_seq + 1)
        .returning(Workspace.conversation_seq)
    )
    if number is None:
        raise NotFound("That workspace does not exist.")
    return int(number)


async def create_conversation(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    contact: Contact,
    subject: str,
    channel: Channel,
    sent_at: datetime,
) -> Conversation:
    conversation = Conversation(
        workspace_id=workspace_id,
        number=await allocate_number(session, workspace_id),
        subject=subject[:400],
        contact_id=contact.id,
        channel=channel,
        status=ConversationStatus.open,
        priority=Priority.medium,
        preview="",
        last_message_at=sent_at,
        unread=True,
    )
    session.add(conversation)
    await session.flush()
    return conversation


async def append_message(
    session: AsyncSession,
    conversation: Conversation,
    *,
    role: MessageRole,
    direction: MessageDirection,
    author_name: str,
    body: str,
    sent_at: datetime,
    to_address: str = "",
    body_html: str | None = None,
    external_id: str | None = None,
    in_reply_to: str | None = None,
    channel_account_id: uuid.UUID | None = None,
    raw_message_id: uuid.UUID | None = None,
    delivery_state: DeliveryState = DeliveryState.none,
) -> Message:
    message = Message(
        workspace_id=conversation.workspace_id,
        conversation_id=conversation.id,
        role=role,
        direction=direction,
        author_name=author_name[:160],
        to_address=to_address,
        body=body,
        body_html=body_html,
        sent_at=sent_at,
        external_id=external_id,
        in_reply_to=in_reply_to,
        channel_account_id=channel_account_id,
        raw_message_id=raw_message_id,
        delivery_state=delivery_state,
    )
    session.add(message)

    # Denormalized onto the conversation because the inbox list is the
    # hottest query in the product and must not join to messages per row.
    conversation.preview = " ".join(body.split())[:200]
    conversation.last_message_at = max(conversation.last_message_at, sent_at)
    await session.flush()
    return message


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


STATUS_LABEL = {
    ConversationStatus.open: "Open",
    ConversationStatus.pending: "Pending",
    ConversationStatus.resolved: "Resolved",
    ConversationStatus.on_hold: "On hold",
    ConversationStatus.ignored: "Ignored",
    ConversationStatus.trash: "Trash",
}
PRIORITY_LABEL = {
    Priority.urgent: "Urgent",
    Priority.high: "High",
    Priority.medium: "Medium",
    Priority.low: "Low",
}


def record(
    session: AsyncSession,
    conversation: Conversation,
    actor: Actor | None,
    kind: ActivityKind,
    verb: str,
    value: str,
    status: str | None = None,
) -> None:
    """Append to the conversation's history.

    Every mutation calls this, so the detail panel's timeline is a
    consequence of the change rather than a second thing to remember.

    ``actor`` is ``None`` only for activity with no nameable cause at all;
    everything else passes an ``Actor``, including inbound mail, which
    passes one carrying just a display name and neither key. The separate
    ``actor_name`` parameter this used to take is gone -- ``Actor`` is that
    parameter, with somewhere to put an identity when there is one.
    """
    session.add(
        ActivityEvent(
            workspace_id=conversation.workspace_id,
            conversation_id=conversation.id,
            actor_user_id=actor.user_id if actor else None,
            actor_api_key_id=actor.api_key_id if actor else None,
            actor_name=actor.name if actor else "Relaydesk",
            kind=kind,
            verb=verb,
            value=value,
            status=status,
            at=datetime.now(UTC),
        )
    )


def _apply_status(
    session: AsyncSession,
    conversation: Conversation,
    status: ConversationStatus,
    actor: Actor,
) -> None:
    """Mutate and record a status change without committing.

    Shared by ``set_status`` (one conversation, one commit) and
    ``bulk_set_status`` (many conversations, one commit) so a bulk update is
    all-or-nothing instead of leaving earlier ids committed when a later one
    fails.
    """
    if conversation.status is status:
        return
    conversation.status = status
    conversation.unread = False
    record(
        session,
        conversation,
        actor,
        ActivityKind.status,
        "marked this as",
        STATUS_LABEL[status],
        status.value,
    )


async def set_status(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    status: ConversationStatus,
    actor: Actor,
) -> Conversation:
    conversation = await get_conversation(session, workspace_id, conversation_id)
    _apply_status(session, conversation, status, actor)
    await session.commit()
    return conversation


async def bulk_set_status(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    conversation_ids: list[uuid.UUID],
    status: ConversationStatus,
    actor: Actor,
) -> None:
    """Update every id in one transaction.

    Every id is resolved (404 on the first missing/foreign one) before any
    row is touched, and everything commits together: a bad id at position
    *n* must not leave ``0..n-1`` already committed while the caller sees a
    404.
    """
    target_conversations = [
        await get_conversation(session, workspace_id, conversation_id)
        for conversation_id in conversation_ids
    ]
    for conversation in target_conversations:
        _apply_status(session, conversation, status, actor)
    await session.commit()


async def set_priority(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    priority: Priority,
    actor: Actor,
) -> Conversation:
    conversation = await get_conversation(session, workspace_id, conversation_id)
    if conversation.priority is priority:
        return conversation
    conversation.priority = priority
    record(
        session,
        conversation,
        actor,
        ActivityKind.priority,
        "set priority to",
        PRIORITY_LABEL[priority],
    )
    await session.commit()
    return conversation


async def set_assignee(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    assignee_id: uuid.UUID | None,
    actor: Actor,
) -> Conversation:
    conversation = await get_conversation(session, workspace_id, conversation_id)
    if conversation.assignee_id == assignee_id:
        return conversation

    previous = conversation.assignee.name if conversation.assignee else None
    if assignee_id is None:
        verb, value = "unassigned this from", previous or "everyone"
    else:
        assignee = await session.scalar(
            sa.select(User)
            .join(Membership, Membership.user_id == User.id)
            .where(
                User.id == assignee_id,
                Membership.workspace_id == workspace_id,
                Membership.status == MembershipStatus.active,
            )
        )
        if assignee is None:
            raise NotFound("That team member does not exist.")
        verb, value = "assigned this to", assignee.name

    conversation.assignee_id = assignee_id
    record(session, conversation, actor, ActivityKind.assignee, verb, value)
    await session.commit()
    await session.refresh(conversation, ["draft", "labels", "assignee"])
    if conversation.assignee is not None:
        notifications.notify_assignment(conversation, conversation.assignee, actor)
    return conversation


async def add_label(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    label_id: uuid.UUID,
    actor: Actor,
) -> Conversation:
    conversation = await get_conversation(session, workspace_id, conversation_id)
    label = await session.scalar(
        sa.select(Label).where(Label.id == label_id, Label.workspace_id == workspace_id)
    )
    if label is None:
        raise NotFound("Label not found.")
    if any(existing.id == label.id for existing in conversation.labels):
        return conversation

    session.add(ConversationLabel(conversation_id=conversation.id, label_id=label.id))
    record(session, conversation, actor, ActivityKind.label, "added label", label.name)
    await session.commit()
    await session.refresh(conversation, ["draft", "labels", "assignee"])
    return conversation


async def remove_label(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    label_id: uuid.UUID,
    actor: Actor,
) -> Conversation:
    conversation = await get_conversation(session, workspace_id, conversation_id)
    label = await session.scalar(
        sa.select(Label).where(Label.id == label_id, Label.workspace_id == workspace_id)
    )
    if label is None:
        raise NotFound("Label not found.")
    if not any(existing.id == label.id for existing in conversation.labels):
        return conversation

    await session.execute(
        sa.delete(ConversationLabel).where(
            ConversationLabel.conversation_id == conversation.id,
            ConversationLabel.label_id == label.id,
        )
    )
    record(
        session, conversation, actor, ActivityKind.label, "removed label", label.name
    )
    await session.commit()
    await session.refresh(conversation, ["draft", "labels", "assignee"])
    return conversation


async def add_reply(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    body: str,
    actor: Actor,
) -> Conversation:
    """Append an agent reply, updating the denormalized list fields."""
    conversation = await get_conversation(session, workspace_id, conversation_id)
    trimmed = body.strip()
    if not trimmed:
        raise Invalid("A reply needs a body.")

    now = datetime.now(UTC)
    message = Message(
        workspace_id=workspace_id,
        conversation_id=conversation.id,
        role=MessageRole.agent,
        author_name=actor.name,
        author_user_id=actor.user_id,
        author_api_key_id=actor.api_key_id,
        to_address=conversation.contact.email,
        body=trimmed,
        sent_at=now,
        direction=MessageDirection.outbound,
        external_id=outbound.new_message_id(),
        delivery_state=DeliveryState.queued,
    )
    session.add(message)
    conversation.preview = trimmed
    conversation.last_message_at = now
    conversation.unread = False

    await session.execute(
        sa.delete(Draft).where(Draft.conversation_id == conversation.id)
    )
    record(
        session,
        conversation,
        actor,
        ActivityKind.reply,
        "replied to",
        conversation.contact.name,
    )
    await session.commit()
    await session.refresh(conversation, ["draft", "labels", "assignee"])
    queue.enqueue_reply(message.id)
    return conversation


async def discard_draft(
    session: AsyncSession, workspace_id: uuid.UUID, conversation_id: uuid.UUID
) -> None:
    conversation = await get_conversation(session, workspace_id, conversation_id)
    await session.execute(
        sa.delete(Draft).where(Draft.conversation_id == conversation.id)
    )
    await session.commit()
    await session.refresh(conversation, ["draft", "labels", "assignee"])
