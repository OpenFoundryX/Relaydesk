"""Routing, classification, threading, and appending.

Order matters: route, classify, thread, append. Classification runs before
anything is created so a bounce or a newsletter never becomes a ticket.
"""

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.email_parse import normalize
from relaydesk.email_parse.classify import Disposition, classify
from relaydesk.email_parse.normalize import InboundMessage
from relaydesk.models.activity import ActivityKind
from relaydesk.models.channel_account import ChannelAccount
from relaydesk.models.contact import Contact
from relaydesk.models.conversation import Channel, Conversation, ConversationStatus
from relaydesk.models.message import Message, MessageDirection, MessageRole
from relaydesk.models.raw_message import RawMessage, RawMessageState
from relaydesk.services import attachments, channel_accounts, contacts, conversations

CONTACT_HOURLY_CAP = 20
SUBJECT_WINDOW = timedelta(days=7)
REOPENING_STATUSES = frozenset(
    {
        ConversationStatus.resolved,
        ConversationStatus.on_hold,
        ConversationStatus.pending,
    }
)

_SUBJECT_NOISE = re.compile(
    r"^(?:\s*(?:re|fw|fwd|aw|sv|vs)\s*:\s*|\s*\[[^\]]{1,40}\]\s*)+", re.IGNORECASE
)


@dataclass(frozen=True)
class Route:
    account: ChannelAccount
    address: str


def normalize_subject(subject: str) -> str:
    previous = None
    current = subject.strip()
    # Repeated prefixes ("Re: Fwd: Re:") need more than one pass.
    while previous != current:
        previous = current
        current = _SUBJECT_NOISE.sub("", current).strip()
    return current.lower()


async def route(session: AsyncSession, message: InboundMessage) -> Route | None:
    """Delivered-To and X-Original-To first, then To and Cc.

    Forwarding does not rewrite To:, so for a brand-new ticket the ingest
    address usually appears only in a Delivered-To header the forwarder
    added. Replies are unaffected: the customer replies straight to the
    tokenized address.
    """
    for address in (*message.delivered_to, *message.to, *message.cc):
        token = channel_accounts.token_from_address(address)
        if token is None:
            continue
        account = await channel_accounts.find_by_token(session, token)
        if account is not None:
            return Route(account=account, address=address)
    return None


async def resolve_thread(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    message: InboundMessage,
    conversation_number: int | None,
) -> Conversation | None:
    # 1. The +c tag. The number is guessable, so it only threads when the
    #    sender is the conversation's own contact -- otherwise a stranger who
    #    learned the ingest address could post into any open thread.
    if conversation_number is not None:
        conversation = await session.scalar(
            sa.select(Conversation).where(
                Conversation.workspace_id == workspace_id,
                Conversation.number == conversation_number,
            )
        )
        if (
            conversation is not None
            and conversation.contact is not None
            and conversation.contact.email.lower() == message.from_email
        ):
            return conversation

    # 2. In-Reply-To, then References right to left (nearest ancestor first).
    #    Always scoped to the workspace: these headers are attacker-supplied.
    #    Unlike the +c tag above, this branch has no sender check -- accepted
    #    as a residual, not an oversight. The +c tag is a small guessable
    #    integer; a Message-ID is not, so forging one requires already
    #    knowing a specific message's id rather than just this workspace's
    #    ingest address.
    candidates = [message.in_reply_to, *reversed(message.references)]
    for external_id in [c for c in candidates if c]:
        conversation = await session.scalar(
            sa.select(Conversation)
            .join(Message, Message.conversation_id == Conversation.id)
            .where(
                Conversation.workspace_id == workspace_id,
                Message.workspace_id == workspace_id,
                Message.external_id == external_id,
            )
            .limit(1)
        )
        if conversation is not None:
            return conversation

    # 3. Same contact, same subject, recently. Both the contact and the
    #    subject are filtered in SQL before the LIMIT: a workspace with more
    #    than 50 conversations touched in the window must not push the
    #    sender's own thread out of the window, which would otherwise open a
    #    duplicate ticket for every reply in a busy workspace.
    subject = normalize_subject(message.subject[:400])
    if not subject:
        return None
    since = datetime.now(UTC) - SUBJECT_WINDOW
    result = await session.scalars(
        sa.select(Conversation)
        .join(Conversation.contact)
        .where(
            Conversation.workspace_id == workspace_id,
            Conversation.last_message_at >= since,
            Contact.email == message.from_email,
        )
        .order_by(Conversation.last_message_at.desc())
        .limit(50)
    )
    for conversation in result:
        if normalize_subject(conversation.subject) == subject:
            return conversation
    return None


async def _already_ingested(
    session: AsyncSession, account_id: uuid.UUID, external_id: str | None
) -> bool:
    if external_id is None:
        return False
    found = await session.scalar(
        sa.select(Message.id).where(
            Message.channel_account_id == account_id,
            Message.external_id == external_id,
        )
    )
    return found is not None


async def _over_cap(session: AsyncSession, workspace_id: uuid.UUID, email: str) -> bool:
    since = datetime.now(UTC) - timedelta(hours=1)
    count = await session.scalar(
        sa.select(sa.func.count())
        .select_from(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .join(Conversation.contact)
        .where(
            Message.workspace_id == workspace_id,
            Message.direction == MessageDirection.inbound,
            Message.created_at >= since,
            Contact.email == email,
        )
    )
    return int(count or 0) >= CONTACT_HOURLY_CAP


async def _handle_bounce(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    message: InboundMessage,
    to_address: str,
) -> RawMessageState:
    conversation = await resolve_thread(session, workspace_id, message, None)
    if conversation is None:
        # Routed to a workspace, but couldn't be threaded to a conversation
        # -- reuses `unrouted` rather than a new state (see cli.unrouted's
        # docstring, which now says what the listing actually contains).
        return RawMessageState.unrouted

    if conversation.contact is not None:
        conversation.contact.bounced_at = datetime.now(UTC)

    await conversations.append_message(
        session,
        conversation,
        role=MessageRole.system,
        direction=MessageDirection.inbound,
        author_name="Mail delivery",
        to_address=to_address,
        body=f"Delivery failed: {message.subject}",
        sent_at=message.sent_at,
    )
    conversations.record(
        session,
        conversation,
        None,
        ActivityKind.status,
        "reported",
        "a delivery failure",
        actor_name="Mail delivery",
    )
    return RawMessageState.ingested


async def ingest_raw(
    session: AsyncSession, raw_message_id: uuid.UUID
) -> RawMessageState:
    row = await session.get(RawMessage, raw_message_id)
    if row is None:
        return RawMessageState.failed
    if row.state is not RawMessageState.fetched:
        # Redelivered task for a message already handled.
        return row.state

    message = normalize.parse(row.raw)
    row.external_id = message.message_id

    matched = await route(session, message)
    if matched is None:
        row.state = RawMessageState.unrouted
        await session.commit()
        return row.state

    row.workspace_id = matched.account.workspace_id
    row.channel_account_id = matched.account.id
    workspace_id = matched.account.workspace_id

    if await _already_ingested(session, matched.account.id, message.message_id):
        row.state = RawMessageState.ingested
        await session.commit()
        return row.state

    disposition = classify(message)
    if disposition is Disposition.bounce:
        row.state = await _handle_bounce(
            session, workspace_id, message, matched.address
        )
        await session.commit()
        return row.state
    if disposition in (Disposition.bulk, Disposition.auto_reply):
        # Filed, never answered: this is the half of loop prevention that
        # stops a vacation responder and this inbox mailing each other.
        row.state = RawMessageState.ingested
        await session.commit()
        return row.state

    if await _over_cap(session, workspace_id, message.from_email):
        row.state = RawMessageState.throttled
        await session.commit()
        return row.state

    contact = await contacts.upsert(
        session, workspace_id, message.from_email, message.from_name
    )
    conversation = await resolve_thread(
        session,
        workspace_id,
        message,
        channel_accounts.conversation_number_from_address(matched.address),
    )
    if conversation is None:
        conversation = await conversations.create_conversation(
            session,
            workspace_id,
            contact,
            message.subject,
            Channel.email,
            message.sent_at,
        )
        conversations.record(
            session,
            conversation,
            None,
            ActivityKind.created,
            "opened this",
            contact.name,
            actor_name=contact.name,
        )
    elif conversation.status in REOPENING_STATUSES:
        conversation.status = ConversationStatus.open

    conversation.unread = True
    appended = await conversations.append_message(
        session,
        conversation,
        role=MessageRole.customer,
        direction=MessageDirection.inbound,
        author_name=contact.name,
        to_address=matched.address,
        body=message.text_body,
        body_html=message.html_body,
        sent_at=message.sent_at,
        external_id=message.message_id,
        in_reply_to=message.in_reply_to,
        channel_account_id=matched.account.id,
        raw_message_id=row.id,
    )
    if message.attachments:
        await attachments.store(session, appended, message.attachments)

    row.state = RawMessageState.ingested
    await session.commit()
    return row.state
