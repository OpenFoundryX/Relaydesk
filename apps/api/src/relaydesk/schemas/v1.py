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
from datetime import datetime
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict

from relaydesk.models import Contact, Conversation, Message

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
