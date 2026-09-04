import uuid
from datetime import UTC, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from pydantic import Field

from relaydesk.models import ActivityEvent, Conversation, Message
from relaydesk.schemas.base import CamelModel


def humanize_age(moment: datetime, now: datetime | None = None) -> str:
    """The list's compact age column: "now", "12m", "3h", "2d"."""
    now = now or datetime.now(UTC)
    seconds = max(int((now - moment).total_seconds()), 0)
    if seconds < 60:
        return "now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"
    return f"{hours // 24}d"


def calendar_date(moment: datetime, timezone: str) -> str:
    """The short calendar label, e.g. "Sep 4", in the workspace's timezone."""
    local = moment.astimezone(ZoneInfo(timezone))
    return f"{local:%b} {local.day}"


class ConversationOut(CamelModel):
    id: str
    number: int
    subject: str
    preview: str
    customer_name: str
    customer_email: str
    channel: str
    status: str
    priority: str
    age: str
    date: str
    assignee: str | None
    assignee_id: str | None
    label_ids: list[str]
    has_draft: bool
    unread: bool
    summary: str | None
    summary_state: str


class ConversationPage(CamelModel):
    items: list[ConversationOut]
    next_cursor: str | None = None


class StatusCountOut(CamelModel):
    status: str
    count: int


class CountsResponse(CamelModel):
    statuses: list[StatusCountOut]
    drafts: int


class MessageOut(CamelModel):
    id: str
    author: str
    to: str
    role: str
    body: str
    sent_at: str


class DraftOut(CamelModel):
    body: str


class ActivityEventOut(CamelModel):
    id: str
    conversation_id: str
    actor: str
    kind: str
    verb: str
    value: str
    status: str | None = None
    at: str


class LabelOut(CamelModel):
    id: str
    name: str
    color: str


class LabelCreateRequest(CamelModel):
    name: str


class ConversationPatch(CamelModel):
    status: str | None = None
    priority: str | None = None
    assignee_id: uuid.UUID | None = None


class BulkStatusRequest(CamelModel):
    # Capped to match the list route's `limit` bound (Query(ge=1, le=200)).
    ids: Annotated[list[uuid.UUID], Field(max_length=200)]
    status: str


class ReplyRequest(CamelModel):
    body: str
    resolve: bool = False


def conversation_out(conversation: Conversation, timezone: str) -> ConversationOut:
    """Serialize a conversation for the wire.

    ``draft`` and ``labels`` are ``lazy="selectin"`` relationships loaded
    once and cached on the instance. The session's ``expire_on_commit=False``
    means a mutation in the *same* session that inserts a ``Draft`` or a
    ``ConversationLabel`` row and then serializes this same in-memory object
    will silently read the pre-mutation ``labelIds``/``hasDraft: false`` —
    no exception, just stale output. Call
    ``await session.refresh(conversation, ["draft", "labels", "assignee"])``
    after such a mutation and before calling this function.
    """
    return ConversationOut(
        id=str(conversation.id),
        number=conversation.number,
        subject=conversation.subject,
        preview=conversation.preview,
        customer_name=conversation.contact.name,
        customer_email=conversation.contact.email,
        channel=conversation.channel.value,
        status=conversation.status.value,
        priority=conversation.priority.value,
        age=humanize_age(conversation.last_message_at),
        date=calendar_date(conversation.last_message_at, timezone),
        assignee=conversation.assignee.name if conversation.assignee else None,
        assignee_id=str(conversation.assignee_id) if conversation.assignee_id else None,
        label_ids=[str(label.id) for label in conversation.labels],
        has_draft=conversation.draft is not None,
        unread=conversation.unread,
        summary=conversation.summary,
        summary_state=conversation.summary_state.value,
    )


def message_out(message: Message, timezone: str) -> MessageOut:
    local = message.sent_at.astimezone(ZoneInfo(timezone))
    return MessageOut(
        id=str(message.id),
        author=message.author_name,
        to=message.to_address,
        role=message.role.value,
        body=message.body,
        sent_at=f"{local:%b} {local.day}, {local:%-I:%M %p}",
    )


def activity_out(event: ActivityEvent, timezone: str) -> ActivityEventOut:
    local = event.at.astimezone(ZoneInfo(timezone))
    return ActivityEventOut(
        id=str(event.id),
        conversation_id=str(event.conversation_id),
        actor=event.actor_name,
        kind=event.kind.value,
        verb=event.verb,
        value=event.value,
        status=event.status,
        at=f"{local:%b} {local.day}, {local:%-I:%M %p}",
    )
