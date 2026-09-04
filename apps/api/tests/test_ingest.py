from datetime import UTC, datetime
from email.message import EmailMessage

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models.contact import Contact
from relaydesk.models.conversation import Conversation, ConversationStatus
from relaydesk.models.message import Message, MessageDirection, MessageRole
from relaydesk.models.raw_message import RawMessage, RawMessageState
from relaydesk.services import channel_accounts, ingest
from tests.factories import make_workspace


async def _account(session, slug="acme"):
    workspace = await make_workspace(session, slug=slug)
    account = await channel_accounts.create(session, workspace.id, "Support")
    await session.flush()
    return workspace, account


def _raw(
    to: str, subject="Refund please", sender="ada@example.com", **headers
) -> bytes:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = to
    message["Subject"] = subject
    message["Date"] = "Tue, 2 Sep 2026 10:00:00 +0000"
    message["Message-ID"] = headers.pop("message_id", "<a1@example.com>")
    for name, value in headers.items():
        message[name.replace("_", "-")] = value
    message.set_content("Please refund my order.")
    return message.as_bytes()


async def _store(session, raw: bytes, uid: int = 1) -> RawMessage:
    row = RawMessage(
        mailbox="INBOX",
        uidvalidity=1,
        uid=uid,
        raw=raw,
        received_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()
    return row


async def test_a_new_message_becomes_a_ticket(db_session: AsyncSession) -> None:
    workspace, account = await _account(db_session)
    address = channel_accounts.address_for(account, "acme")
    row = await _store(db_session, _raw(address))

    state = await ingest.ingest_raw(db_session, row.id)

    assert state is RawMessageState.ingested
    conversation = await db_session.scalar(sa.select(Conversation))
    assert conversation is not None
    assert conversation.workspace_id == workspace.id
    assert conversation.subject == "Refund please"
    assert conversation.status is ConversationStatus.open
    assert conversation.unread is True
    assert conversation.number == 1

    message = await db_session.scalar(sa.select(Message))
    assert message.role is MessageRole.customer
    assert message.direction is MessageDirection.inbound
    assert message.external_id == "<a1@example.com>"


async def test_forwarded_mail_routes_by_delivered_to(db_session: AsyncSession) -> None:
    """Forwarding does not rewrite To:. A customer mailing support@acme.com
    produces a message whose To: still says support@acme.com, and the ingest
    address appears only in Delivered-To."""
    workspace, account = await _account(db_session)
    address = channel_accounts.address_for(account, "acme")
    row = await _store(db_session, _raw("support@acme.com", Delivered_To=address))

    assert await ingest.ingest_raw(db_session, row.id) is RawMessageState.ingested
    conversation = await db_session.scalar(sa.select(Conversation))
    assert conversation.workspace_id == workspace.id


async def test_mail_we_cannot_route_is_kept_not_dropped(
    db_session: AsyncSession,
) -> None:
    await _account(db_session)
    row = await _store(db_session, _raw("someone-else@elsewhere.com"))

    state = await ingest.ingest_raw(db_session, row.id)

    assert state is RawMessageState.unrouted
    assert (
        await db_session.scalar(sa.select(sa.func.count()).select_from(Conversation))
        == 0
    )
    await db_session.refresh(row)
    assert row.raw  # the bytes survive for replay


async def test_a_reply_threads_onto_the_same_conversation(
    db_session: AsyncSession,
) -> None:
    workspace, account = await _account(db_session)
    address = channel_accounts.address_for(account, "acme")
    first = await _store(
        db_session, _raw(address, message_id="<one@example.com>"), uid=1
    )
    await ingest.ingest_raw(db_session, first.id)

    second = await _store(
        db_session,
        _raw(
            address,
            subject="Re: Refund please",
            message_id="<two@example.com>",
            In_Reply_To="<one@example.com>",
        ),
        uid=2,
    )
    await ingest.ingest_raw(db_session, second.id)

    assert (
        await db_session.scalar(sa.select(sa.func.count()).select_from(Conversation))
        == 1
    )
    assert await db_session.scalar(sa.select(sa.func.count()).select_from(Message)) == 2


async def test_a_forged_reference_cannot_reach_another_workspace(
    db_session: AsyncSession,
) -> None:
    """References is attacker-supplied. Without the workspace predicate a
    crafted header appends a message to another tenant's conversation."""
    _victim, victim_account = await _account(db_session, slug="victim")
    victim_address = channel_accounts.address_for(victim_account, "victim")
    victim_row = await _store(
        db_session, _raw(victim_address, message_id="<secret@x>"), uid=1
    )
    await ingest.ingest_raw(db_session, victim_row.id)

    _attacker, attacker_account = await _account(db_session, slug="attacker")
    attacker_address = channel_accounts.address_for(attacker_account, "attacker")
    attacker_row = await _store(
        db_session,
        _raw(attacker_address, message_id="<evil@x>", In_Reply_To="<secret@x>"),
        uid=2,
    )
    await ingest.ingest_raw(db_session, attacker_row.id)

    assert (
        await db_session.scalar(sa.select(sa.func.count()).select_from(Conversation))
        == 2
    )


async def test_a_tagged_address_threads_only_for_that_contact(
    db_session: AsyncSession,
) -> None:
    """The +c tag uses the conversation number, which is guessable. Requiring
    the sender to be the conversation's own contact is what stops a stranger
    who knows the ingest address from posting into an existing thread."""
    _workspace, account = await _account(db_session)
    address = channel_accounts.address_for(account, "acme")
    first = await _store(db_session, _raw(address), uid=1)
    await ingest.ingest_raw(db_session, first.id)
    conversation = await db_session.scalar(sa.select(Conversation))

    tagged = channel_accounts.address_for(account, "acme", conversation.number)
    stranger = await _store(
        db_session,
        _raw(tagged, sender="mallory@example.com", message_id="<m@x>"),
        uid=2,
    )
    await ingest.ingest_raw(db_session, stranger.id)

    assert (
        await db_session.scalar(sa.select(sa.func.count()).select_from(Conversation))
        == 2
    )


async def test_the_same_subject_from_the_same_contact_threads(
    db_session: AsyncSession,
) -> None:
    _workspace, account = await _account(db_session)
    address = channel_accounts.address_for(account, "acme")
    first = await _store(db_session, _raw(address, message_id="<one@x>"), uid=1)
    await ingest.ingest_raw(db_session, first.id)

    second = await _store(
        db_session,
        _raw(address, subject="RE: Refund please", message_id="<two@x>"),
        uid=2,
    )
    await ingest.ingest_raw(db_session, second.id)

    assert (
        await db_session.scalar(sa.select(sa.func.count()).select_from(Conversation))
        == 1
    )


async def test_a_resolved_conversation_reopens_on_a_customer_reply(
    db_session: AsyncSession,
) -> None:
    _workspace, account = await _account(db_session)
    address = channel_accounts.address_for(account, "acme")
    first = await _store(db_session, _raw(address, message_id="<one@x>"), uid=1)
    await ingest.ingest_raw(db_session, first.id)
    conversation = await db_session.scalar(sa.select(Conversation))
    conversation.status = ConversationStatus.resolved
    await db_session.commit()

    second = await _store(
        db_session, _raw(address, message_id="<two@x>", In_Reply_To="<one@x>"), uid=2
    )
    await ingest.ingest_raw(db_session, second.id)

    await db_session.refresh(conversation)
    assert conversation.status is ConversationStatus.open


async def test_a_trashed_conversation_does_not_reopen(
    db_session: AsyncSession,
) -> None:
    _workspace, account = await _account(db_session)
    address = channel_accounts.address_for(account, "acme")
    first = await _store(db_session, _raw(address, message_id="<one@x>"), uid=1)
    await ingest.ingest_raw(db_session, first.id)
    conversation = await db_session.scalar(sa.select(Conversation))
    conversation.status = ConversationStatus.trash
    await db_session.commit()

    second = await _store(
        db_session, _raw(address, message_id="<two@x>", In_Reply_To="<one@x>"), uid=2
    )
    await ingest.ingest_raw(db_session, second.id)

    await db_session.refresh(conversation)
    assert conversation.status is ConversationStatus.trash


async def test_a_newsletter_creates_no_ticket(db_session: AsyncSession) -> None:
    _workspace, account = await _account(db_session)
    address = channel_accounts.address_for(account, "acme")
    row = await _store(db_session, _raw(address, List_Id="<news.example.com>"))

    await ingest.ingest_raw(db_session, row.id)

    assert (
        await db_session.scalar(sa.select(sa.func.count()).select_from(Conversation))
        == 0
    )


async def test_a_bounce_marks_the_contact_and_does_not_open_a_ticket(
    db_session: AsyncSession,
) -> None:
    _workspace, account = await _account(db_session)
    address = channel_accounts.address_for(account, "acme")
    first = await _store(db_session, _raw(address, message_id="<one@x>"), uid=1)
    await ingest.ingest_raw(db_session, first.id)

    bounce = await _store(
        db_session,
        _raw(
            address,
            sender="MAILER-DAEMON@mx.example.com",
            message_id="<b@x>",
            In_Reply_To="<one@x>",
        ),
        uid=2,
    )
    await ingest.ingest_raw(db_session, bounce.id)

    assert (
        await db_session.scalar(sa.select(sa.func.count()).select_from(Conversation))
        == 1
    )
    contact = await db_session.scalar(
        sa.select(Contact).where(Contact.email == "ada@example.com")
    )
    assert contact.bounced_at is not None
    roles = list(await db_session.scalars(sa.select(Message.role)))
    assert MessageRole.system in roles


async def test_ingesting_the_same_message_twice_appends_once(
    db_session: AsyncSession,
) -> None:
    """The task is at-least-once. A redelivery after a crash must be a
    no-op, not a duplicate ticket."""
    _workspace, account = await _account(db_session)
    address = channel_accounts.address_for(account, "acme")
    row = await _store(db_session, _raw(address))

    await ingest.ingest_raw(db_session, row.id)
    await ingest.ingest_raw(db_session, row.id)

    assert await db_session.scalar(sa.select(sa.func.count()).select_from(Message)) == 1


async def test_a_flood_from_one_contact_is_throttled(
    db_session: AsyncSession,
) -> None:
    _workspace, account = await _account(db_session)
    address = channel_accounts.address_for(account, "acme")

    for uid in range(1, ingest.CONTACT_HOURLY_CAP + 2):
        row = await _store(db_session, _raw(address, message_id=f"<m{uid}@x>"), uid=uid)
        state = await ingest.ingest_raw(db_session, row.id)

    assert state is RawMessageState.throttled


async def test_one_noisy_sender_does_not_silence_everyone_else(
    db_session: AsyncSession,
) -> None:
    """The cap is per contact. A workspace-wide cap would let one flood mute
    every other customer -- and the test above passes either way, so this is
    the one that actually pins the behaviour."""
    _workspace, account = await _account(db_session)
    address = channel_accounts.address_for(account, "acme")
    for uid in range(1, ingest.CONTACT_HOURLY_CAP + 2):
        row = await _store(db_session, _raw(address, message_id=f"<m{uid}@x>"), uid=uid)
        await ingest.ingest_raw(db_session, row.id)

    other = await _store(
        db_session,
        _raw(address, sender="rita@example.com", message_id="<other@x>"),
        uid=999,
    )

    assert await ingest.ingest_raw(db_session, other.id) is RawMessageState.ingested
