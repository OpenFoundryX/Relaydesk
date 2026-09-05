from datetime import UTC, datetime, timedelta
from email import message_from_bytes
from email.policy import default as default_policy

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models.message import (
    DeliveryState,
    Message,
    MessageDirection,
    MessageRole,
)
from relaydesk.services import channel_accounts, conversations, outbound
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
