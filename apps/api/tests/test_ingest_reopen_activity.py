from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.utils import format_datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models import ActivityEvent, ActivityKind, ConversationStatus
from relaydesk.models.conversation import Conversation
from relaydesk.models.raw_message import RawMessage
from relaydesk.services import channel_accounts, conversations, ingest
from tests.factories import make_conversation, make_member, make_workspace


async def deliver_inbound_reply(
    session: AsyncSession, workspace, conversation: Conversation
) -> None:
    """Feed a reply through the real ingest pipeline, tagged onto
    ``conversation`` the way a customer's reply-to-support address actually
    arrives (see test_ingest.py's tagged-address test) -- not a shortcut
    into ingest that would leave the routing/threading path unexercised.
    """
    account = await channel_accounts.create(session, workspace.id, "Support")
    address = channel_accounts.address_for(
        account, workspace.slug, conversation.number
    )
    message = EmailMessage()
    message["From"] = "priya@northwind.io"  # make_conversation's default contact
    message["To"] = address
    message["Subject"] = f"Re: {conversation.subject}"
    message["Date"] = format_datetime(datetime.now(UTC) - timedelta(minutes=1))
    message["Message-ID"] = "<reply@example.com>"
    message.set_content("Still broken, please take another look.")
    row = RawMessage(
        mailbox="INBOX",
        uidvalidity=1,
        uid=1,
        raw=message.as_bytes(),
        received_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()
    await ingest.ingest_raw(session, row.id)


async def test_an_inbound_reply_to_a_resolved_ticket_records_the_reopen(
    db_session: AsyncSession,
) -> None:
    """Without this event the backlog series cannot see the reopen: the
    ticket silently re-enters the backlog and every earlier point is short
    by one. The conversation's own timeline was missing it too."""
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    conversation = await make_conversation(db_session, workspace)
    await conversations.set_status(
        db_session,
        workspace.id,
        conversation.id,
        ConversationStatus.resolved,
        conversations.Actor(name=user.name, user_id=user.id),
    )

    await deliver_inbound_reply(db_session, workspace, conversation)

    events = list(
        await db_session.scalars(
            sa.select(ActivityEvent)
            .where(
                ActivityEvent.conversation_id == conversation.id,
                ActivityEvent.kind == ActivityKind.status,
            )
            .order_by(ActivityEvent.at)
        )
    )
    assert [event.status for event in events] == ["resolved", "open"]
