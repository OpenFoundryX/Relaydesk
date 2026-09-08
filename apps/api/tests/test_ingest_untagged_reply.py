"""Routing a reply that came back to an untagged address.

Replies normally carry the tokenized ingest address, because that is what
Relaydesk puts in Reply-To. When `OUTBOUND_FROM_ADDRESS` moves the From onto
a plain mailbox, a client that ignores Reply-To answers the From instead --
an address with no token in it. `ingest.route` then has nothing to match on
and the reply is lost.

These cover recovering that case from the threading headers, and the guard
that keeps the recovery from becoming a way into somebody else's inbox.
"""

from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.utils import format_datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.config import get_settings
from relaydesk.models.conversation import Conversation
from relaydesk.models.message import Message
from relaydesk.models.raw_message import RawMessage, RawMessageState
from relaydesk.services import channel_accounts, ingest
from tests.factories import make_workspace

_SENT_AT = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=1)


def _raw(to: str, sender: str = "ada@example.com", **headers) -> bytes:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = to
    message["Subject"] = headers.pop("subject", "Refund please")
    message["Date"] = format_datetime(_SENT_AT)
    message["Message-ID"] = headers.pop("message_id", "<a1@example.com>")
    for name, value in headers.items():
        message[name.replace("_", "-")] = value
    message.set_content("Please refund my order.")
    return message.as_bytes()


async def _store(session, raw: bytes, uid: int) -> RawMessage:
    row = RawMessage(
        mailbox="INBOX", uidvalidity=1, uid=uid, raw=raw, received_at=datetime.now(UTC)
    )
    session.add(row)
    await session.flush()
    return row


def _untagged() -> str:
    return f"info@{get_settings().inbound_domain}"


async def _opened_conversation(session: AsyncSession, slug: str):
    """One ingested customer message, so a conversation and contact exist."""
    workspace = await make_workspace(session, slug=slug)
    account = await channel_accounts.create(session, workspace.id, "Support")
    await session.flush()
    tagged = channel_accounts.address_for(account, slug)
    first = await _store(
        session, _raw(tagged, message_id="<one@example.com>"), uid=1
    )
    await ingest.ingest_raw(session, first.id)
    return workspace


async def test_a_reply_to_an_untagged_address_reaches_its_conversation(
    db_session: AsyncSession,
) -> None:
    """The client answered the From, not the Reply-To. The threading headers
    are the only thing left that says where this belongs."""
    await _opened_conversation(db_session, "acme-untagged")

    reply = await _store(
        db_session,
        _raw(
            _untagged(),
            sender="ada@example.com",
            subject="Re: Refund please",
            message_id="<two@example.com>",
            In_Reply_To="<one@example.com>",
        ),
        uid=2,
    )
    await ingest.ingest_raw(db_session, reply.id)

    assert (
        await db_session.scalar(sa.select(sa.func.count()).select_from(Conversation))
        == 1
    )
    assert await db_session.scalar(sa.select(sa.func.count()).select_from(Message)) == 2


async def test_a_stranger_cannot_ride_a_reference_into_someone_elses_conversation(
    db_session: AsyncSession,
) -> None:
    """The guard that makes the recovery safe.

    Every customer can read real Message-IDs out of the mail we send them, so
    without a sender check a leaked id would be a way into that conversation
    from an untagged address -- no ingest token needed.
    """
    await _opened_conversation(db_session, "acme-stranger")

    forged = await _store(
        db_session,
        _raw(
            _untagged(),
            sender="mallory@evil.example",
            subject="Re: Refund please",
            message_id="<evil@example.com>",
            In_Reply_To="<one@example.com>",
        ),
        uid=2,
    )
    state = await ingest.ingest_raw(db_session, forged.id)

    assert state is RawMessageState.unrouted
    assert await db_session.scalar(sa.select(sa.func.count()).select_from(Message)) == 1


async def test_an_untagged_message_matching_nothing_stays_unrouted(
    db_session: AsyncSession,
) -> None:
    """The fallback must not invent a workspace for mail that simply has no
    business here -- that is the whole point of keeping unrouted mail."""
    await _opened_conversation(db_session, "acme-nomatch")

    stray = await _store(
        db_session,
        _raw(
            _untagged(),
            sender="ada@example.com",
            message_id="<stray@example.com>",
            In_Reply_To="<never-sent@example.com>",
        ),
        uid=2,
    )
    state = await ingest.ingest_raw(db_session, stray.id)

    assert state is RawMessageState.unrouted
