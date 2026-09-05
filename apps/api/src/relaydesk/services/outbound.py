"""Turning a stored reply into mail that threads."""

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.utils import make_msgid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.config import get_settings
from relaydesk.models.channel_account import ChannelAccount
from relaydesk.models.conversation import Conversation
from relaydesk.models.message import DeliveryState, Message, MessageDirection
from relaydesk.models.workspace import Workspace
from relaydesk.services import channel_accounts, mailer

logger = logging.getLogger(__name__)

# Delivery is at-least-once by design: SMTP has no idempotency key, and
# marking `sent` before the send would trade a rare duplicate for a rare
# silent non-delivery, which is worse for a support product. These bound
# (without eliminating) the specific case of an ordinary transient failure
# -- a dropped connection, a statement timeout -- landing in the narrow
# window *after* the mail has already left the building but before the
# commit that records it. A handful of immediate retries turns that into a
# non-event; only a true outage still falls through to Celery's own retry,
# which is where the residual duplicate risk lives.
_COMMIT_RETRIES = 3
_COMMIT_RETRY_DELAY_SECONDS = 0.05


def new_message_id() -> str:
    """SMTP does not return a Message-ID; it returns a queue id local to that
    server. The sender generates the header, and we must store what we sent
    or a customer's reply has nothing to thread onto."""
    return make_msgid(domain=get_settings().inbound_domain)


def reply_subject(subject: str) -> str:
    return subject if subject.lower().startswith("re:") else f"Re: {subject}"


async def _context(
    session: AsyncSession, message: Message
) -> tuple[Conversation, Workspace, ChannelAccount | None]:
    conversation = await session.get(Conversation, message.conversation_id)
    workspace = await session.get(Workspace, message.workspace_id)
    account = await session.scalar(
        sa.select(ChannelAccount)
        .where(
            ChannelAccount.workspace_id == message.workspace_id,
            ChannelAccount.active.is_(True),
        )
        .order_by(ChannelAccount.created_at)
        .limit(1)
    )
    return conversation, workspace, account


async def build_reply(session: AsyncSession, message: Message) -> EmailMessage:
    conversation, workspace, account = await _context(session, message)

    last_inbound = await session.scalar(
        sa.select(Message)
        .where(
            Message.conversation_id == conversation.id,
            Message.direction == MessageDirection.inbound,
            Message.external_id.is_not(None),
        )
        .order_by(Message.sent_at.desc())
        .limit(1)
    )

    sender = mailer.from_address()
    reply_to = sender
    if account is not None:
        address = channel_accounts.address_for(
            account, workspace.slug, conversation.number
        )
        sender = f'"{workspace.name}" <{address}>'
        reply_to = address
    else:
        # channel_accounts.deactivate can leave a workspace with no active
        # account. The send still succeeds, but the +c tag that lets the
        # customer's reply route back onto this conversation is silently
        # gone -- loud in the log even though nothing here fails.
        logger.warning(
            "workspace %s has no active channel account; reply to "
            "conversation %s will not carry a routable +c tag",
            workspace.id,
            conversation.id,
        )

    headers: dict[str, str] = {"Reply-To": reply_to}
    if last_inbound is not None and last_inbound.external_id:
        headers["In-Reply-To"] = last_inbound.external_id
        headers["References"] = last_inbound.external_id

    built = mailer.build(
        to=conversation.contact.email,
        subject=reply_subject(conversation.subject),
        text_body=message.body,
        headers=headers,
        sender=sender,
    )
    # Replace the auto-generated Message-ID with the one already stored, so
    # the header the customer replies to is the one we can match on.
    del built["Message-ID"]
    built["Message-ID"] = message.external_id or new_message_id()
    return built


async def deliver(session: AsyncSession, message_id: uuid.UUID) -> DeliveryState:
    message = await session.get(Message, message_id)
    if message is None:
        return DeliveryState.failed
    if message.delivery_state is not DeliveryState.queued:
        # Already handled; a redelivered task must not mail a second copy.
        return message.delivery_state

    built = await build_reply(session, message)
    await mailer.send_message(built)

    # The mail is already gone. From here, an ordinary transient failure --
    # not a hard crash -- would otherwise fall straight through to Celery's
    # autoretry, which resends: the guard above only protects a *second*
    # invocation, not this one finishing what it started. Retrying the
    # commit in place turns a brief database blip into a non-event instead
    # of a duplicate email.
    last_error: BaseException | None = None
    for attempt in range(_COMMIT_RETRIES):
        message.delivery_state = DeliveryState.sent
        message.delivery_error = None
        try:
            await session.commit()
            return DeliveryState.sent
        except Exception as error:
            last_error = error
            if attempt < _COMMIT_RETRIES - 1:
                logger.warning(
                    "commit failed after sending message %s (attempt %d/%d);"
                    " retrying",
                    message_id,
                    attempt + 1,
                    _COMMIT_RETRIES,
                    exc_info=True,
                )
                await asyncio.sleep(_COMMIT_RETRY_DELAY_SECONDS)
    assert last_error is not None
    raise last_error


async def mark_failed(session: AsyncSession, message_id: uuid.UUID, error: str) -> None:
    message = await session.get(Message, message_id)
    if message is None:
        return
    message.delivery_state = DeliveryState.failed
    message.delivery_error = error[:2000]
    await session.commit()


async def requeue_stalled(
    session: AsyncSession, older_than: timedelta
) -> list[uuid.UUID]:
    """Replies committed as queued that never reached the broker.

    Publishing is not part of the database transaction, so the API can commit
    a reply and then fail to publish it. Without this the agent sees a sent
    reply that the customer never receives.
    """
    cutoff = datetime.now(UTC) - older_than
    result = await session.scalars(
        sa.select(Message.id).where(
            Message.delivery_state == DeliveryState.queued,
            Message.created_at < cutoff,
        )
    )
    return list(result)
