"""Public API request and response shapes.

Deliberately **not** ``CamelModel``. The console's schemas are camelCase and
carry fields rendered for one particular sidebar -- ``age`` as "3h", ``date``
as "Sep 4", ``has_draft`` -- and serving those here would freeze a UI's
rendering decisions into a third-party contract (spec D6). Everything in this
module is snake_case, with ISO-8601 timestamps and no derived display fields.

Response models are **constructed by the helpers at the bottom of this
module, never by ``model_validate`` on an ORM object**. ``Conversation`` has
no ``metadata`` attribute -- reading it returns SQLAlchemy's ``MetaData``,
because Declarative owns that name -- so the column is reached as ``.meta``,
and that fact is confined to ``conversation_out``.
"""

import json
import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

from relaydesk.models import (
    Contact,
    Conversation,
    ConversationStatus,
    Label,
    Message,
    Priority,
)

METADATA_MAX_BYTES = 8192
METADATA_MAX_KEYS = 50


def _bounded_metadata(value: dict[str, Any]) -> dict[str, Any]:
    """Keep ``metadata`` a place for an order id, not a blob store.

    It lives inside ``conversations``, the hottest table in the product, and
    it is unindexed, so an unbounded field would cost every inbox query
    without ever being queryable itself.
    """
    if len(value) > METADATA_MAX_KEYS:
        raise ValueError(f"metadata accepts at most {METADATA_MAX_KEYS} keys.")
    encoded = json.dumps(value, separators=(",", ":")).encode()
    if len(encoded) > METADATA_MAX_BYTES:
        raise ValueError(f"metadata must be under {METADATA_MAX_BYTES} bytes.")
    return value


Metadata = Annotated[dict[str, Any], AfterValidator(_bounded_metadata)]


class V1Model(BaseModel):
    """Every public schema inherits this. snake_case on the wire."""

    model_config = ConfigDict(from_attributes=False)


class ContactOut(V1Model):
    id: str
    email: str
    name: str


class ConversationOut(V1Model):
    id: str
    number: int
    subject: str
    preview: str
    status: str
    priority: str
    channel: str
    customer: ContactOut
    assignee_id: str | None
    label_ids: list[str]
    external_id: str | None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime


class ConversationPage(V1Model):
    data: list[ConversationOut]
    next_cursor: str | None = None


class MessageOut(V1Model):
    id: str
    conversation_id: str
    role: str
    direction: str
    author_name: str
    body: str
    sent_at: datetime


class ConversationCreate(V1Model):
    """The body ``components/settings/code-sample.tsx`` publishes.

    ``customer_email`` and ``message`` are required; everything else is
    optional, exactly as the sample's own description says.
    """

    customer_email: EmailStr
    message: str = Field(min_length=1)
    # Bounded to ``Contact.name``'s own ``String(160)``. Unbounded, a
    # 200-character name for an address the workspace has not seen reached
    # ``contacts.upsert`` untruncated and Postgres raised
    # ``StringDataRightTruncation`` -> SQLAlchemy ``DataError``, which is
    # *not* an ``IntegrityError``, so ``create_from_api``'s guarded flush did
    # not catch it and the public API answered a bare 500 with no
    # ``{"error": {...}}`` envelope. Every other string on this path is
    # already bounded -- ``external_id`` here, ``subject`` by
    # ``create_conversation``'s ``[:400]``, ``message`` by
    # ``ticket_message_max_chars``, ``Message.author_name`` by
    # ``append_message``'s ``[:160]`` -- so this one refuses with a 422 like
    # the rest of the body rather than being the one field that 500s.
    customer_name: str = Field(default="", max_length=160)
    subject: str = ""
    priority: Priority = Priority.medium
    external_id: str | None = Field(default=None, max_length=200)
    metadata: Metadata = Field(default_factory=dict)


class ConversationUpdate(V1Model):
    """Every field optional. An omitted field is left alone, which is what
    makes it safe for two integrations to update different fields of the
    same conversation without either clobbering the other."""

    status: ConversationStatus | None = None
    priority: Priority | None = None
    assignee_id: uuid.UUID | None = None


class MessageCreate(V1Model):
    body: str = Field(min_length=1)


class LabelOut(V1Model):
    id: str
    name: str
    color: str


class LabelCreate(V1Model):
    name: str = Field(min_length=1, max_length=80)


class ContactPage(V1Model):
    data: list[ContactOut]
    next_cursor: str | None = None


def label_out(label: Label) -> LabelOut:
    return LabelOut(id=str(label.id), name=label.name, color=label.color.value)


def contact_out(contact: Contact) -> ContactOut:
    return ContactOut(id=str(contact.id), email=contact.email, name=contact.name)


def conversation_out(conversation: Conversation) -> ConversationOut:
    return ConversationOut(
        id=str(conversation.id),
        number=conversation.number,
        subject=conversation.subject,
        preview=conversation.preview,
        status=conversation.status.value,
        priority=conversation.priority.value,
        channel=conversation.channel.value,
        customer=contact_out(conversation.contact),
        assignee_id=(
            str(conversation.assignee_id) if conversation.assignee_id else None
        ),
        label_ids=[str(label.id) for label in conversation.labels],
        external_id=conversation.external_id,
        # ``.meta``, not ``.metadata`` -- see this module's docstring.
        metadata=conversation.meta,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        last_message_at=conversation.last_message_at,
    )


def message_out(message: Message) -> MessageOut:
    return MessageOut(
        id=str(message.id),
        conversation_id=str(message.conversation_id),
        role=message.role.value,
        direction=message.direction.value,
        author_name=message.author_name,
        body=message.body,
        sent_at=message.sent_at,
    )
