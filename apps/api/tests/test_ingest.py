from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models.activity import ActivityEvent, ActivityKind
from relaydesk.models.contact import Contact
from relaydesk.models.conversation import Conversation, ConversationStatus
from relaydesk.models.message import Message, MessageDirection, MessageRole
from relaydesk.models.raw_message import RawMessage, RawMessageState
from relaydesk.services import channel_accounts, contacts, conversations, ingest
from tests.factories import make_workspace


async def _account(session, slug="acme"):
    workspace = await make_workspace(session, slug=slug)
    account = await channel_accounts.create(session, workspace.id, "Support")
    await session.flush()
    return workspace, account


def _raw(
    to: str,
    subject="Refund please",
    sender="ada@example.com",
    date="Tue, 2 Sep 2026 10:00:00 +0000",
    **headers,
) -> bytes:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = to
    message["Subject"] = subject
    message["Date"] = date
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
    assert message.to_address == address

    contact = await db_session.scalar(
        sa.select(Contact).where(Contact.email == "ada@example.com")
    )
    event = await db_session.scalar(sa.select(ActivityEvent))
    assert event.kind is ActivityKind.created
    assert event.actor_user_id is None
    assert event.actor_name == contact.name


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


async def test_strategy_three_finds_the_contacts_own_thread_past_fifty_others(
    db_session: AsyncSession,
) -> None:
    """.limit(50) must be applied after filtering by contact, not before --
    otherwise a workspace with more than 50 conversations touched in the
    window pushes the sender's own thread out of the window and the reply
    opens a duplicate ticket instead of threading."""
    _workspace, account = await _account(db_session)
    address = channel_accounts.address_for(account, "acme")

    # "first" gets the earliest timestamp; each of the 60 others is strictly
    # more recent, so under ORDER BY last_message_at DESC LIMIT 50 applied
    # before the contact filter, "first" falls outside the window entirely.
    first = await _store(
        db_session,
        _raw(address, message_id="<one@x>", date="Tue, 2 Sep 2026 00:00:00 +0000"),
        uid=1,
    )
    await ingest.ingest_raw(db_session, first.id)

    for i in range(60):
        other = await _store(
            db_session,
            _raw(
                address,
                sender=f"other{i}@example.com",
                subject=f"Something else {i}",
                message_id=f"<other{i}@x>",
                date="Tue, 2 Sep 2026 12:00:00 +0000",
            ),
            uid=100 + i,
        )
        await ingest.ingest_raw(db_session, other.id)

    reply = await _store(
        db_session,
        _raw(
            address,
            subject="RE: Refund please",
            message_id="<two@x>",
            date="Wed, 3 Sep 2026 00:00:00 +0000",
        ),
        uid=999,
    )
    await ingest.ingest_raw(db_session, reply.id)

    assert (
        await db_session.scalar(sa.select(sa.func.count()).select_from(Conversation))
        == 61
    )


async def test_a_bounce_records_the_address_it_bounced_to(
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

    system_message = await db_session.scalar(
        sa.select(Message).where(Message.role == MessageRole.system)
    )
    assert system_message.to_address == address


async def test_a_contact_insert_race_does_not_lose_the_pipelines_earlier_mutations(
    db_session: AsyncSession, monkeypatch
) -> None:
    """If contacts.upsert's own SELECT misses a contact that another message
    from the same brand-new address inserted a moment earlier, the INSERT
    hits the unique constraint. Recovering from that must not roll back the
    `row.workspace_id`/`row.channel_account_id`/`row.external_id` mutations
    ingest_raw already made in this same transaction -- a bare
    ``session.rollback()`` would discard them and detach `row`, silently
    losing the pipeline's progress and leaving the message stuck at
    `fetched` for redelivery."""
    workspace, account = await _account(db_session)
    address = channel_accounts.address_for(account, "acme")
    row = await _store(db_session, _raw(address))

    # Someone else's message from this same new address already landed.
    existing = Contact(workspace_id=workspace.id, email="ada@example.com", name="Ada")
    db_session.add(existing)
    await db_session.flush()

    # ...but simulate contacts.upsert's own lookup missing it once, as a
    # race would: the first call returns None, forcing the insert branch
    # into the real unique-constraint conflict; later calls behave normally.
    real_find = contacts._find
    calls = {"n": 0}

    async def blind_once(session, workspace_id, email):
        calls["n"] += 1
        if calls["n"] == 1:
            return None
        return await real_find(session, workspace_id, email)

    monkeypatch.setattr(contacts, "_find", blind_once)

    state = await ingest.ingest_raw(db_session, row.id)

    assert state is RawMessageState.ingested
    await db_session.refresh(row)
    assert row.state is RawMessageState.ingested
    assert row.workspace_id == workspace.id
    assert row.channel_account_id == account.id
    assert row.external_id == "<a1@example.com>"


async def test_a_long_display_name_is_truncated_not_fatal(
    db_session: AsyncSession,
) -> None:
    """A From: display name over Contact.name's 160 characters is not
    adversarial -- automated senders and other ticketing systems produce
    them routinely. Before normalize._header_fields bounded from_name,
    contacts.upsert's insert raised StringDataRightTruncation deep inside
    append_message's commit, aborting the whole ingest transaction. This
    pins that the ticket is created anyway, with the contact's name simply
    truncated to fit."""
    _workspace, account = await _account(db_session)
    address = channel_accounts.address_for(account, "acme")
    long_name = "A" * 300
    raw = (
        f'From: "{long_name}" <ada@example.com>\r\n'
        f"To: {address}\r\n"
        f"Subject: Refund please\r\n"
        f"Date: Tue, 2 Sep 2026 10:00:00 +0000\r\n"
        f"Message-ID: <long-name@example.com>\r\n"
        f"\r\n"
        f"Please refund my order.\r\n"
    ).encode()
    row = await _store(db_session, raw)

    state = await ingest.ingest_raw(db_session, row.id)

    assert state is RawMessageState.ingested
    assert (
        await db_session.scalar(sa.select(sa.func.count()).select_from(Conversation))
        == 1
    )
    contact = await db_session.scalar(
        sa.select(Contact).where(Contact.email == "ada@example.com")
    )
    assert contact is not None
    assert contact.name == long_name[:160]


async def test_an_unrecoverable_failure_lands_in_failed_not_stuck_at_fetched(
    db_session: AsyncSession, monkeypatch
) -> None:
    """Before ingest_raw had a terminal state, an exception here aborted the
    transaction and left row.state at `fetched` forever: ingest_message
    exhausts its five retries hitting the same error every time, and
    reconcile_inbound re-enqueues the row every five minutes after that --
    forever. A terminal `failed` state with the error recorded is what
    stops the loop and gives the operator something to look at instead of
    silent, permanent message loss."""
    _workspace, account = await _account(db_session)
    address = channel_accounts.address_for(account, "acme")
    row = await _store(db_session, _raw(address))
    # Committed, matching how imap.store_new leaves a real raw message:
    # already durable in its own transaction by the time ingestion runs.
    # Otherwise the rollback that recovers from the poisoned transaction
    # below would undo this row's own insert along with everything else.
    await db_session.commit()

    async def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated unrecoverable failure")

    monkeypatch.setattr(conversations, "create_conversation", boom)

    state = await ingest.ingest_raw(db_session, row.id)

    assert state is RawMessageState.failed
    await db_session.refresh(row)
    assert row.state is RawMessageState.failed
    assert row.error is not None
    assert "simulated unrecoverable failure" in row.error

    # Terminal, not stuck: a redelivered task must not retry the same
    # failing operation forever -- it short-circuits on the recorded state.
    assert await ingest.ingest_raw(db_session, row.id) is RawMessageState.failed


async def test_a_date_header_far_in_the_past_does_not_sink_the_conversation(
    db_session: AsyncSession,
) -> None:
    """The sender's Date: header is attacker-controlled, but
    Conversation.last_message_at -- the keyset-paginated inbox's sort key --
    was set straight from it. An unclamped Date this old would sort a brand
    new ticket below every 50-row page forever."""
    _workspace, account = await _account(db_session)
    address = channel_accounts.address_for(account, "acme")
    row = await _store(
        db_session, _raw(address, date="Tue, 2 Sep 1990 10:00:00 +0000")
    )

    await ingest.ingest_raw(db_session, row.id)

    conversation = await db_session.scalar(sa.select(Conversation))
    assert conversation.last_message_at.year >= 2000


async def test_a_date_header_far_in_the_future_does_not_pin_the_conversation(
    db_session: AsyncSession,
) -> None:
    """An unclamped Date far in the future would pin the conversation to
    the top of the inbox permanently: append_message's max() means no
    later, honest message could ever move it back down."""
    _workspace, account = await _account(db_session)
    address = channel_accounts.address_for(account, "acme")
    row = await _store(
        db_session, _raw(address, date="Fri, 2 Sep 2099 10:00:00 +0000")
    )

    await ingest.ingest_raw(db_session, row.id)

    conversation = await db_session.scalar(sa.select(Conversation))
    assert conversation.last_message_at.year < 2099
    assert conversation.last_message_at <= row.received_at + ingest._MAX_FUTURE_SKEW


async def test_an_ordinary_date_header_passes_through_unclamped(
    db_session: AsyncSession,
) -> None:
    """A normal, recent Date must render exactly as sent -- the clamp only
    ever engages far outside any plausible mail delivery window."""
    _workspace, account = await _account(db_session)
    address = channel_accounts.address_for(account, "acme")
    row = await _store(db_session, _raw(address))

    await ingest.ingest_raw(db_session, row.id)

    message = await db_session.scalar(sa.select(Message))
    assert message.sent_at == datetime(2026, 9, 2, 10, 0, tzinfo=UTC)


async def test_requeue_unprocessed_finds_a_stalled_raw_message(
    db_session: AsyncSession,
) -> None:
    """imap_poll writes the row and publishes ingest_message separately, so
    a broker outage can leave a raw message sitting in `fetched` with no
    task ever picked up to ingest it."""
    row = await _store(db_session, _raw("acme-abc@inbound.localhost"))
    row.created_at = datetime.now(UTC) - timedelta(minutes=5)
    await db_session.commit()

    stuck = await ingest.requeue_unprocessed(db_session, timedelta(minutes=2))

    assert row.id in stuck


async def test_requeue_unprocessed_ignores_a_fresh_raw_message(
    db_session: AsyncSession,
) -> None:
    await _store(db_session, _raw("acme-abc@inbound.localhost"))
    await db_session.commit()

    stuck = await ingest.requeue_unprocessed(db_session, timedelta(minutes=2))

    assert stuck == []


async def test_requeue_unprocessed_ignores_an_already_ingested_message(
    db_session: AsyncSession,
) -> None:
    row = await _store(db_session, _raw("acme-abc@inbound.localhost"))
    row.state = RawMessageState.ingested
    row.created_at = datetime.now(UTC) - timedelta(minutes=5)
    await db_session.commit()

    stuck = await ingest.requeue_unprocessed(db_session, timedelta(minutes=2))

    assert stuck == []
