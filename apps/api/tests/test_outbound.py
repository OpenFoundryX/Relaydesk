import logging
from datetime import UTC, datetime, timedelta
from email import message_from_bytes
from email.policy import default as default_policy

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models.message import (
    DeliveryState,
    Message,
    MessageDirection,
    MessageRole,
)
from relaydesk.models.workspace import Workspace
from relaydesk.services import channel_accounts, conversations, mailer, outbound, queue
from relaydesk.worker.tasks.mail import send_conversation_message
from tests.factories import make_conversation, make_member, make_workspace


async def _reply(session, subject="Refund please"):
    workspace = await make_workspace(session, slug="acme")
    await channel_accounts.create(session, workspace.id, "Support")
    member = await make_member(session, workspace, email="nilesh@example.com")
    conversation = await make_conversation(session, workspace, subject=subject)
    await conversations.append_message(
        session,
        conversation,
        role=MessageRole.customer,
        direction=MessageDirection.inbound,
        author_name="Ada",
        body="Where is my refund?",
        sent_at=datetime.now(UTC),
        external_id="<customer@example.com>",
    )
    # add_reply (services/conversations.py:419) takes no `resolve` flag — the
    # router applies that separately — and returns the Conversation, so the
    # message is read back here.
    await conversations.add_reply(
        session, workspace.id, conversation.id, "On its way.", member
    )
    message = await session.scalar(
        sa.select(Message)
        .where(
            Message.conversation_id == conversation.id,
            Message.direction == MessageDirection.outbound,
        )
        .order_by(Message.sent_at.desc())
        .limit(1)
    )
    return workspace, conversation, message


async def test_a_reply_is_queued_with_a_message_id(db_session: AsyncSession) -> None:
    """SMTP returns a queue id, not a Message-ID — the sender mints it. Without
    one stored, a customer's reply has nothing to thread onto."""
    _workspace, _conversation, message = await _reply(db_session)

    assert message.direction is MessageDirection.outbound
    assert message.delivery_state is DeliveryState.queued
    assert message.external_id is not None
    assert message.external_id.startswith("<") and message.external_id.endswith(">")


async def test_the_built_reply_threads_in_the_customers_client(
    db_session: AsyncSession,
) -> None:
    _workspace, conversation, message = await _reply(db_session)

    built = await outbound.build_reply(db_session, message)
    parsed = message_from_bytes(built.as_bytes(), policy=default_policy)

    assert parsed["In-Reply-To"] == "<customer@example.com>"
    assert "<customer@example.com>" in parsed["References"]
    assert parsed["Message-ID"] == message.external_id
    assert parsed["Subject"] == "Re: Refund please"
    assert f"+c{conversation.number}@" in parsed["Reply-To"]
    # Agent replies are written by a person and must not be marked automatic.
    assert parsed["Auto-Submitted"] is None


async def test_a_reply_to_an_already_prefixed_subject_is_not_double_prefixed(
    db_session: AsyncSession,
) -> None:
    _workspace, _conversation, message = await _reply(db_session, subject="Re: Refund")

    built = await outbound.build_reply(db_session, message)

    assert built["Subject"] == "Re: Refund"


async def test_delivery_marks_the_message_sent(
    db_session: AsyncSession, smtp_server
) -> None:
    _workspace, _conversation, message = await _reply(db_session)

    state = await outbound.deliver(db_session, message.id)

    assert state is DeliveryState.sent
    await db_session.refresh(message)
    assert message.delivery_state is DeliveryState.sent
    assert len(smtp_server.messages) == 1


async def test_delivering_twice_sends_once(
    db_session: AsyncSession, smtp_server
) -> None:
    """The task is at-least-once, so a redelivery must not mail the customer
    a second copy."""
    _workspace, _conversation, message = await _reply(db_session)

    await outbound.deliver(db_session, message.id)
    await outbound.deliver(db_session, message.id)

    assert len(smtp_server.messages) == 1


async def test_the_reconciler_finds_a_reply_that_was_never_published(
    db_session: AsyncSession,
) -> None:
    """Publishing to RabbitMQ is not part of the database transaction, so a
    reply can commit as queued and never reach the broker. Without this, the
    agent sees a sent reply the customer never gets."""
    _workspace, _conversation, message = await _reply(db_session)
    message.created_at = datetime.now(UTC) - timedelta(minutes=5)
    await db_session.commit()

    stalled = await outbound.requeue_stalled(db_session, timedelta(minutes=2))

    assert message.id in stalled


async def test_the_reconciler_ignores_a_fresh_reply(
    db_session: AsyncSession,
) -> None:
    _workspace, _conversation, message = await _reply(db_session)

    stalled = await outbound.requeue_stalled(db_session, timedelta(minutes=2))

    assert stalled == []


async def test_a_broker_failure_during_add_reply_does_not_propagate(
    db_session: AsyncSession, monkeypatch, caplog
) -> None:
    """By the time add_reply calls queue.enqueue_reply, the message row is
    already committed. A broker hiccup here must not turn a successful reply
    into a 500 for the agent -- the row stays `queued` for the reconciler."""
    workspace = await make_workspace(db_session, slug="acme-broker")
    member = await make_member(db_session, workspace, email="nilesh@example.com")
    conversation = await make_conversation(db_session, workspace)

    def raise_broker_error(*args: object, **kwargs: object) -> None:
        raise RuntimeError("broker unreachable")

    monkeypatch.setattr(send_conversation_message, "delay", raise_broker_error)
    # See test_queue.py's identical comment: migrations disable every logger
    # created before they run, including this module's.
    monkeypatch.setattr(queue.logger, "disabled", False)

    with caplog.at_level(logging.WARNING):
        await conversations.add_reply(
            db_session, workspace.id, conversation.id, "On its way.", member
        )

    assert "relaydesk.send_conversation_message" in caplog.text

    message = await db_session.scalar(
        sa.select(Message)
        .where(
            Message.conversation_id == conversation.id,
            Message.direction == MessageDirection.outbound,
        )
        .order_by(Message.sent_at.desc())
        .limit(1)
    )
    assert message is not None
    assert message.delivery_state is DeliveryState.queued


async def test_a_reply_without_a_channel_account_omits_the_c_tag_and_logs(
    db_session: AsyncSession, monkeypatch, caplog
) -> None:
    """channel_accounts.deactivate can leave a workspace with no active
    account. The fallback address still sends, but silently drops the +c tag
    the customer's reply needs to route back -- so this pins the fallback's
    actual shape and makes sure it is loud, not silent."""
    monkeypatch.setattr(outbound.logger, "disabled", False)
    workspace = await make_workspace(db_session, slug="acme-no-account")
    member = await make_member(db_session, workspace, email="nilesh@example.com")
    conversation = await make_conversation(
        db_session, workspace, subject="Refund please"
    )
    await conversations.append_message(
        db_session,
        conversation,
        role=MessageRole.customer,
        direction=MessageDirection.inbound,
        author_name="Ada",
        body="Where is my refund?",
        sent_at=datetime.now(UTC),
        external_id="<customer@example.com>",
    )
    await conversations.add_reply(
        db_session, workspace.id, conversation.id, "On its way.", member
    )
    message = await db_session.scalar(
        sa.select(Message).where(
            Message.conversation_id == conversation.id,
            Message.direction == MessageDirection.outbound,
        )
    )

    with caplog.at_level(logging.WARNING):
        built = await outbound.build_reply(db_session, message)

    # Pinned to the literal value, not just "no +c tag": a regression that
    # produced some other broken address would still satisfy a negative
    # check on "+c" alone.
    assert built["Reply-To"] == mailer.from_address()
    assert str(workspace.id) in caplog.text
    assert str(conversation.id) in caplog.text
    assert "no active channel account" in caplog.text


async def test_a_reply_uses_the_address_the_customer_actually_wrote_to(
    db_session: AsyncSession,
) -> None:
    """_context used to always pick the workspace's oldest active
    ChannelAccount, ignoring Message.channel_account_id -- which ingest.py
    already records per inbound message. A workspace with two connected
    addresses would answer mail sent to one from the other, so the customer
    sees a different correspondent than the one they wrote to."""
    workspace = await make_workspace(db_session, slug="acme-two-addresses")
    older_account = await channel_accounts.create(db_session, workspace.id, "Sales")
    newer_account = await channel_accounts.create(db_session, workspace.id, "Support")
    member = await make_member(db_session, workspace, email="nilesh@example.com")
    conversation = await make_conversation(
        db_session, workspace, subject="Refund please"
    )
    await conversations.append_message(
        db_session,
        conversation,
        role=MessageRole.customer,
        direction=MessageDirection.inbound,
        author_name="Ada",
        body="Where is my refund?",
        sent_at=datetime.now(UTC),
        external_id="<customer@example.com>",
        channel_account_id=newer_account.id,
    )

    await conversations.add_reply(
        db_session, workspace.id, conversation.id, "On its way.", member
    )
    message = await db_session.scalar(
        sa.select(Message).where(
            Message.conversation_id == conversation.id,
            Message.direction == MessageDirection.outbound,
        )
    )

    built = await outbound.build_reply(db_session, message)

    expected = channel_accounts.address_for(
        newer_account, workspace.slug, conversation.number
    )
    wrong = channel_accounts.address_for(
        older_account, workspace.slug, conversation.number
    )
    assert expected in built["Reply-To"]
    assert wrong not in built["Reply-To"]


async def test_a_reply_falls_back_to_the_oldest_active_account_with_no_inbound(
    db_session: AsyncSession,
) -> None:
    """An agent-initiated thread has no inbound message to key off of, so
    the fallback to the workspace's oldest active account must still work."""
    workspace = await make_workspace(db_session, slug="acme-agent-initiated")
    account = await channel_accounts.create(db_session, workspace.id, "Support")
    member = await make_member(db_session, workspace, email="nilesh@example.com")
    conversation = await make_conversation(
        db_session, workspace, subject="Following up"
    )

    await conversations.add_reply(
        db_session, workspace.id, conversation.id, "Just checking in.", member
    )
    message = await db_session.scalar(
        sa.select(Message).where(
            Message.conversation_id == conversation.id,
            Message.direction == MessageDirection.outbound,
        )
    )

    built = await outbound.build_reply(db_session, message)

    expected = channel_accounts.address_for(
        account, workspace.slug, conversation.number
    )
    assert expected in built["Reply-To"]


async def test_a_transient_commit_failure_retries_in_place(
    db_session: AsyncSession, smtp_server
) -> None:
    """A dropped connection or a statement timeout right after the mail
    leaves the building must not fall straight through to Celery's autoretry
    -- that would resend for something as mundane as a database blip.

    This forces a genuine DBAPI-level failure (a unique violation) instead
    of mocking `commit`, so it also proves the required rollback-before-
    retry actually recovers a live session: verified directly (see the
    round-2 fix report) that a bare retry without an intervening rollback
    raises PendingRollbackError rather than ever reaching Postgres again."""
    _workspace, _conversation, message = await _reply(db_session)

    # A second, doomed-to-conflict row shares this session with `message`.
    # deliver()'s first commit flushes both together and fails on the
    # duplicate slug; the rollback it performs discards this pending row
    # (it was never persisted) while the retry loop re-applies `message`'s
    # own change, so the second commit reaches Postgres with only that
    # change pending, and succeeds. Autoflush is disabled for the call so
    # the conflict surfaces only at the intended `commit()`, not at one of
    # deliver()'s own earlier reads (session.get, the channel-account
    # lookup, ...), each of which would otherwise autoflush it prematurely
    # and fail outside the retry loop entirely.
    db_session.add(Workspace(name="Dupe", slug=_workspace.slug, monogram="DP"))
    db_session.autoflush = False
    try:
        state = await outbound.deliver(db_session, message.id)
    finally:
        db_session.autoflush = True

    assert state is DeliveryState.sent
    await db_session.refresh(message)
    assert message.delivery_state is DeliveryState.sent
    assert len(smtp_server.messages) == 1


async def test_commit_failure_exhausting_retries_still_sent_only_once(
    db_session: AsyncSession, smtp_server, monkeypatch
) -> None:
    """When every retry fails, the caller must see the error (so Celery's
    own retry takes over) -- but the mail was only ever sent the once.

    A persistently-failing DBAPI error is impractical to arrange
    deterministically (the prior test's duplicate-row trick only fails
    once, by design -- the rollback it triggers removes the conflict).
    `commit` is mocked here instead; `rollback` is a spy wrapping the real
    method, confirming it genuinely runs on every failed attempt rather
    than merely appearing in the source."""
    _workspace, _conversation, message = await _reply(db_session)

    async def always_fail() -> None:
        raise RuntimeError("connection reset")

    real_rollback = db_session.rollback
    rollback_calls = {"n": 0}

    async def counting_rollback() -> None:
        rollback_calls["n"] += 1
        await real_rollback()

    monkeypatch.setattr(db_session, "commit", always_fail)
    monkeypatch.setattr(db_session, "rollback", counting_rollback)

    with pytest.raises(RuntimeError):
        await outbound.deliver(db_session, message.id)

    assert len(smtp_server.messages) == 1
    assert rollback_calls["n"] == outbound._COMMIT_RETRIES
