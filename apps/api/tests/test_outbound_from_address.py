"""The From address on an outbound reply.

Replying from the raw ingest address (``acme-<token>+c7@…``) is correct for
routing but reads as machine-generated to a recipient, and to Gmail. These
cover sending from a configured address instead while keeping the tagged
address in ``Reply-To``, which is what actually carries a customer's reply
back onto the right conversation.
"""

from datetime import UTC, datetime
from email.utils import parseaddr

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.config import get_settings
from relaydesk.models.message import Message, MessageDirection, MessageRole
from relaydesk.services import channel_accounts, conversations, outbound
from relaydesk.services.actors import Actor
from tests.factories import make_conversation, make_member, make_workspace


async def _outbound_message(session: AsyncSession, slug: str) -> Message:
    workspace = await make_workspace(session, slug=slug)
    account = await channel_accounts.create(session, workspace.id, "Support")
    member = await make_member(session, workspace, email="nilesh@example.com")
    conversation = await make_conversation(session, workspace, subject="Refund please")
    await conversations.append_message(
        session,
        conversation,
        role=MessageRole.customer,
        direction=MessageDirection.inbound,
        author_name="Ada",
        body="Where is my refund?",
        sent_at=datetime.now(UTC),
        external_id="<customer@example.com>",
        channel_account_id=account.id,
    )
    await conversations.add_reply(
        session, workspace.id, conversation.id, "On its way.", Actor.for_user(member)
    )
    return await session.scalar(
        sa.select(Message).where(
            Message.conversation_id == conversation.id,
            Message.direction == MessageDirection.outbound,
        )
    )


async def test_a_configured_from_address_replaces_the_ingest_address(
    db_session: AsyncSession, monkeypatch
) -> None:
    """The recipient sees a real mailbox, not a tagged routing address."""
    monkeypatch.setattr(get_settings(), "outbound_from_address", "info@relaydesk.dev")
    message = await _outbound_message(db_session, "acme-from-configured")

    built = await outbound.build_reply(db_session, message)

    name, address = parseaddr(built["From"])
    assert address == "info@relaydesk.dev"
    # The workspace still identifies itself; only the mailbox changed.
    assert name == "Acme-From-Configured"


async def test_the_tagged_address_stays_in_reply_to(
    db_session: AsyncSession, monkeypatch
) -> None:
    """The whole feature rests on this. The ``+c`` tag in Reply-To is what
    routes the customer's reply back onto this conversation; moving the From
    off the ingest address must not move that with it."""
    monkeypatch.setattr(get_settings(), "outbound_from_address", "info@relaydesk.dev")
    message = await _outbound_message(db_session, "acme-reply-to-kept")

    built = await outbound.build_reply(db_session, message)

    assert "+c" in built["Reply-To"]
    assert built["Reply-To"].endswith(f"@{get_settings().inbound_domain}")
    assert built["Reply-To"] != built["From"]


async def test_an_unset_from_address_keeps_replying_from_the_ingest_address(
    db_session: AsyncSession
) -> None:
    """The default is empty, so a self-hoster who upgrades sees no change."""
    assert get_settings().outbound_from_address == ""
    message = await _outbound_message(db_session, "acme-from-default")

    built = await outbound.build_reply(db_session, message)

    name, address = parseaddr(built["From"])
    assert address == built["Reply-To"]
    assert name == "Acme-From-Default"
