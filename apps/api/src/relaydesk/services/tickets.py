import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.config import get_settings
from relaydesk.email_parse.normalize import ParsedAttachment
from relaydesk.errors import Invalid
from relaydesk.models.conversation import Channel, Conversation
from relaydesk.models.message import MessageDirection, MessageRole
from relaydesk.services import attachments as attachment_store
from relaydesk.services import contacts, conversations, ingest


async def submit(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    email: str,
    name: str,
    subject: str,
    message: str,
    attachments: Sequence[ParsedAttachment],
) -> Conversation:
    """Turn an anonymous portal submission into an ordinary inbox ticket.

    Composes the same services email ingest uses, so a portal ticket and an
    emailed one are the same rows -- the only difference is the channel,
    which records that the sender's address was never attested (spec D1/D2).
    """
    settings = get_settings()

    body = message.strip()
    if not body:
        raise Invalid("A message is required.")
    if len(body) > settings.ticket_message_max_chars:
        raise Invalid("That message is too long.")
    if len(attachments) > settings.ticket_attachment_max_count:
        raise Invalid("Too many attachments.")
    for item in attachments:
        if item.content_type.lower() not in attachment_store.INLINE_SAFE_TYPES:
            raise Invalid("That file type is not accepted.")

    if await ingest._over_cap(session, workspace_id, email):
        raise Invalid("Too many messages from this address just now.")

    display_name = name.strip() or email
    contact = await contacts.upsert(session, workspace_id, email, display_name)

    now = datetime.now(UTC)
    conversation = await conversations.create_conversation(
        session,
        workspace_id,
        contact,
        subject.strip() or f"Message from {display_name}",
        Channel.portal,
        now,
    )
    # ``create_conversation`` sets ``contact_id`` but never touches the
    # ``contact`` relationship, and that relationship's ``lazy="selectin"``
    # strategy only fires for objects returned by a query -- not for one
    # this call just constructed and flushed. Without this, the very next
    # line to read ``conversation.contact`` on the object this function
    # returns would try a synchronous lazy load outside of any awaited
    # call and blow up with ``MissingGreenlet``. We already hold the exact
    # ``Contact`` instance, so assign it directly instead of paying for a
    # refresh.
    conversation.contact = contact
    appended = await conversations.append_message(
        session,
        conversation,
        role=MessageRole.customer,
        direction=MessageDirection.inbound,
        author_name=display_name,
        body=body,
        sent_at=now,
    )
    if attachments:
        await attachment_store.store(session, appended, attachments)

    await session.flush()
    return conversation
