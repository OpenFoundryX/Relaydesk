"""Routing, classification, threading, and appending.

Order matters: route, classify, thread, append. Classification runs before
anything is created so a bounce or a newsletter never becomes a ticket.
"""

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as SATimeoutError
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
from relaydesk.services.actors import Actor

logger = logging.getLogger(__name__)

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

# The sender's Date: header is attacker-controlled, but Conversation.
# last_message_at -- the sort key for the keyset-paginated inbox -- is set
# straight from it (via create_conversation / append_message). An unclamped
# Date far in the past sorts a live ticket below every 50-row page forever
# *and* falls outside resolve_thread's SUBJECT_WINDOW lookback, so a later
# reply with no In-Reply-To opens a duplicate ticket instead of threading;
# one far in the future pins it to the top permanently, because
# append_message's max() means no later, honest message can ever move it
# back down. Clamping to RawMessage.received_at -- the time this poller
# actually fetched the bytes, which the sender never controls -- with a
# small allowance either direction keeps the header useful for display
# (Message.sent_at) while making it harmless as a sort key. The floor is
# relative for the same reason the ceiling is: a bare absolute floor (e.g.
# year 2000) still leaves the entire 2000-to-today range unclamped, which
# is exactly as capable of parking a ticket outside both the inbox's
# recent pages and the threading window as no floor at all.
_MAX_FUTURE_SKEW = timedelta(hours=1)
_MAX_PAST_SKEW = timedelta(days=3)


def _clamp_sent_at(sent_at: datetime, received_at: datetime) -> datetime:
    ceiling = received_at + _MAX_FUTURE_SKEW
    floor = received_at - _MAX_PAST_SKEW
    if sent_at > ceiling:
        return ceiling
    if sent_at < floor:
        return floor
    return sent_at


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
    return await _route_by_reference(session, message)


async def _route_by_reference(
    session: AsyncSession, message: InboundMessage
) -> Route | None:
    """Find the workspace from the threading headers, for a reply that came
    back to an address carrying no token.

    This exists for one case. ``OUTBOUND_FROM_ADDRESS`` puts a plain mailbox
    in the From while Reply-To keeps the tokenized address; a client that
    ignores Reply-To answers the From instead, and the reply arrives with
    nothing in its recipients for ``route`` to match on. Without this it is
    filed ``unrouted`` and the customer is simply never answered.

    **The sender check below is what makes this safe, and it is not
    optional.** ``resolve_thread`` already matches these same headers, but
    only *after* the workspace is known, and every query there is scoped to
    it -- an attacker-supplied header can pick a thread inside a tenant they
    had already reached, never the tenant itself. Here the header chooses the
    tenant, so that reasoning does not carry over: every customer can read
    real Message-IDs out of the mail we send them, and a leaked one would
    otherwise be a way into that conversation from any address at all.
    Requiring the sender to be the conversation's own contact closes it --
    a stranger holding the id still has nowhere to put it.

    Ordered like ``resolve_thread``: In-Reply-To, then References right to
    left, nearest ancestor first.
    """
    recipient = next(
        (a for a in (*message.delivered_to, *message.to, *message.cc) if a), ""
    )
    candidates = [message.in_reply_to, *reversed(message.references)]
    for external_id in [c for c in candidates if c]:
        # Not limit(1): ``messages.external_id`` carries no global unique
        # constraint, and stopping at an arbitrary row would let one whose
        # contact does not match hide a sibling whose contact does.
        matches = list(
            await session.scalars(
                sa.select(Conversation)
                .join(Message, Message.conversation_id == Conversation.id)
                .where(Message.external_id == external_id)
            )
        )
        for conversation in matches:
            contact = conversation.contact
            if contact is None or contact.email.lower() != message.from_email:
                continue
            accounts = await channel_accounts.list_for(
                session, conversation.workspace_id
            )
            if accounts:
                return Route(account=accounts[0], address=recipient)
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


async def requeue_unprocessed(
    session: AsyncSession, older_than: timedelta
) -> list[uuid.UUID]:
    """Raw messages the poller stored but never got onto the broker.

    ``imap_poll`` writes ``raw_messages`` rows and then publishes one
    ``ingest_message`` per row. The publish is not part of that transaction,
    and the queue seam swallows broker failures by design, so a RabbitMQ
    outage leaves rows sitting in ``fetched`` with nothing to pick them up.
    Re-enqueuing is safe because ``ingest_raw`` returns early for any row
    whose state is not ``fetched``.
    """
    cutoff = datetime.now(UTC) - older_than
    result = await session.scalars(
        sa.select(RawMessage.id).where(
            RawMessage.state == RawMessageState.fetched,
            RawMessage.created_at < cutoff,
        )
    )
    return list(result)


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
    sent_at: datetime,
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
        sent_at=sent_at,
    )
    conversations.record(
        session,
        conversation,
        Actor(name="Mail delivery"),
        ActivityKind.status,
        "reported",
        "a delivery failure",
    )
    return RawMessageState.ingested


# SQLSTATE class prefixes (the first two digits) that Postgres reserves for
# conditions retrying is actually likely to fix: 08 connection exception,
# 40 transaction rollback (deadlock, serialization failure), 53
# insufficient resources, 57 operator intervention (admin shutdown, cannot
# connect now, statement/query canceled), 58 system error. Everything else
# -- 22 data exception, 23 integrity constraint violation, 42 syntax/access
# rule violation, and any non-database exception -- is deterministic: the
# same input produces the same failure on every retry.
#
# Classified by SQLSTATE rather than by sqlalchemy.exc's own subclass
# hierarchy because asyncpg's dialect only maps a handful of asyncpg
# exception types to a specific sqlalchemy.exc.* class (see
# PGDialect_asyncpg._asyncpg_error_translate); most asyncpg errors --
# transient or not -- surface as the same generic sqlalchemy.exc.DBAPIError,
# so `isinstance(exc, sa.exc.OperationalError)` would not actually catch a
# real deadlock or a dropped connection under this driver.
_TRANSIENT_SQLSTATE_CLASSES = frozenset({"08", "40", "53", "57", "58"})


def _is_transient_db_error(exc: BaseException) -> bool:
    """A dropped connection, a deadlock, a serialization failure, a
    statement timeout under a reset -- these self-heal, and
    ``ingest_message``'s own ``autoretry_for``/``retry_backoff`` already
    exists to ride them out (the same reasoning ``outbound.py``'s
    ``_COMMIT_RETRIES`` applies one layer down, for the same class of
    failure). Marking the row ``failed`` on the first occurrence of one of
    these would trade a loud infinite loop for a quiet one-shot failure on
    an error that almost always resolves on its own -- Celery's retry
    budget would become dead code for ingest.
    """
    sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None) or getattr(
        exc, "sqlstate", None
    )
    if sqlstate:
        return sqlstate[:2] in _TRANSIENT_SQLSTATE_CLASSES
    # No SQLSTATE at all means this either never reached Postgres (a
    # connection couldn't be established, a pool checkout timed out) or
    # isn't a database error in the first place -- the former is exactly as
    # transient as a SQLSTATE-08 error, and OperationalError/TimeoutError
    # are what those actually surface as.
    transient_types = (OperationalError, SATimeoutError, ConnectionError, TimeoutError)
    return isinstance(exc, transient_types)


async def ingest_raw(
    session: AsyncSession, raw_message_id: uuid.UUID
) -> RawMessageState:
    """Route, classify, thread, and append -- or fail the row terminally.

    A deterministic failure (a database constraint this module didn't
    anticipate, a genuine bug) aborts the transaction it ran in, which
    discards every mutation this call made, including any it made to
    ``row`` itself -- so the row cannot be marked ``failed`` inside the
    same transaction that raised. Instead: roll back the poisoned
    transaction, then record the failure in a fresh one. Without a terminal
    state, ``row.state`` stays ``fetched`` forever: ``ingest_message``
    exhausts its five retries hitting the same error every time, and
    ``reconcile_inbound`` re-enqueues the row every five minutes after that,
    forever -- silent, permanent message loss with no operator-visible
    trace. ``failed`` rows show up in ``relaydesk unrouted list`` precisely
    so there is one.

    A *transient* failure (see ``_is_transient_db_error``) is different:
    retrying is likely to succeed, so this re-raises instead, letting
    ``ingest_message``'s own ``autoretry_for``/``retry_backoff`` ride it
    out rather than giving up after the first occurrence.
    """
    row = await session.get(RawMessage, raw_message_id)
    if row is None:
        return RawMessageState.failed
    if row.state is not RawMessageState.fetched:
        # Redelivered task for a message already handled.
        return row.state

    try:
        return await _ingest_routed(session, row)
    except Exception as exc:
        await session.rollback()
        if _is_transient_db_error(exc):
            logger.warning(
                "ingest_raw hit a transient error for raw message %s;"
                " leaving it at `fetched` for Celery's own retry",
                raw_message_id,
                exc_info=True,
            )
            raise
        failed = await session.get(RawMessage, raw_message_id)
        if failed is not None:
            failed.state = RawMessageState.failed
            failed.error = str(exc)[:2000]
            await session.commit()
        logger.exception(
            "ingest_raw failed permanently for raw message %s", raw_message_id
        )
        return RawMessageState.failed


async def _ingest_routed(session: AsyncSession, row: RawMessage) -> RawMessageState:
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
    sent_at = _clamp_sent_at(message.sent_at, row.received_at)

    if await _already_ingested(session, matched.account.id, message.message_id):
        row.state = RawMessageState.ingested
        await session.commit()
        return row.state

    disposition = classify(message)
    if disposition is Disposition.bounce:
        row.state = await _handle_bounce(
            session, workspace_id, message, matched.address, sent_at
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
            sent_at,
        )
        conversations.record(
            session,
            conversation,
            Actor(name=contact.name),
            ActivityKind.created,
            "opened this",
            contact.name,
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
        sent_at=sent_at,
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
