import uuid
from datetime import UTC, datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models.channel_account import ChannelAccount, ChannelAccountKind
from relaydesk.models.message import (
    DeliveryState,
    Message,
    MessageDirection,
    MessageRole,
)
from tests.factories import make_conversation, make_workspace


async def _account(session: AsyncSession, workspace_id: uuid.UUID) -> ChannelAccount:
    account = ChannelAccount(
        workspace_id=workspace_id,
        kind=ChannelAccountKind.email,
        ingest_token=uuid.uuid4().hex[:12],
        display_name="Support",
        active=True,
    )
    session.add(account)
    await session.flush()
    return account


def _message(conversation, account_id, external_id) -> Message:
    return Message(
        workspace_id=conversation.workspace_id,
        conversation_id=conversation.id,
        role=MessageRole.customer,
        direction=MessageDirection.inbound,
        author_name="Ada",
        body="hello",
        sent_at=datetime.now(UTC),
        channel_account_id=account_id,
        external_id=external_id,
    )


async def test_the_same_external_id_cannot_be_ingested_twice(
    db_session: AsyncSession,
) -> None:
    """RabbitMQ is at-least-once, so a redelivered ingest task must append
    nothing the second time. This index is what makes that true."""
    workspace = await make_workspace(db_session)
    account = await _account(db_session, workspace.id)
    conversation = await make_conversation(db_session, workspace)

    db_session.add(_message(conversation, account.id, "<abc@example.com>"))
    await db_session.flush()

    db_session.add(_message(conversation, account.id, "<abc@example.com>"))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_many_messages_may_have_no_external_id(
    db_session: AsyncSession,
) -> None:
    """The index must be partial. Postgres treats NULLs as distinct, so a
    plain unique index would appear to work here while silently permitting
    the duplicates it exists to prevent."""
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)

    db_session.add(_message(conversation, None, None))
    db_session.add(_message(conversation, None, None))
    await db_session.flush()


async def test_system_is_an_accepted_message_role(db_session: AsyncSession) -> None:
    """Bounce notices belong to a thread but were authored by neither a
    customer nor an agent. Slice 1's migration created ck_messages_role as a
    named CHECK, so widening the enum needs the constraint recreated."""
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)

    message = _message(conversation, None, None)
    message.role = MessageRole.system
    db_session.add(message)
    await db_session.flush()


async def test_delivery_state_defaults_to_none(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)

    message = _message(conversation, None, None)
    db_session.add(message)
    await db_session.flush()

    assert message.delivery_state == DeliveryState.none


async def test_existing_users_default_to_wanting_assignment_email(
    db_session: AsyncSession,
) -> None:
    """A Python-side default does not touch rows the migration already
    created, so this column needs a server default."""
    workspace = await make_workspace(db_session)
    from tests.factories import make_member

    user = await make_member(db_session, workspace, email="ada@example.com")
    value = await db_session.scalar(
        sa.text("SELECT notify_on_assignment FROM users WHERE id = :id").bindparams(
            id=user.id
        )
    )
    assert value is True
