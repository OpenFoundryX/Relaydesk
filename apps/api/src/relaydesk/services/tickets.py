import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.config import get_settings
from relaydesk.email_parse.normalize import ParsedAttachment
from relaydesk.errors import Invalid, TooManyRequests
from relaydesk.models.activity import ActivityKind
from relaydesk.models.conversation import Channel, Conversation, Priority
from relaydesk.models.message import MessageDirection, MessageRole
from relaydesk.services import attachments as attachment_store
from relaydesk.services import contacts, conversations, ingest
from relaydesk.services.actors import Actor


def validate(message: str, attachments: Sequence[ParsedAttachment]) -> str:
    """Every input-validation refusal a submission can earn, and the body.

    Split out of `submit` so the portal router can run it *before* its own
    abuse controls. A control that fires ahead of validation answers 201 or
    429 where validation would have answered 422, and that difference is an
    oracle: a bot that posts one deliberately invalid payload twice, once
    with a candidate field filled and once without, reads the honeypot's
    identity straight off the two status codes. Running validation first
    means every caller has been refused for the same reasons in the same
    order before any control has spoken (spec section 7).

    These messages stay specific on purpose -- a blank message, an oversize
    one, too many files, a rejected type, a total upload over budget are
    genuine mistakes a real submitter benefits from being told about, not
    abuse signals to hide. The refusals that *are* abuse signals (the IP
    cap, the per-email cap, the honeypot) are the ones held to a single
    indistinguishable answer.
    """
    settings = get_settings()

    body = message.strip()
    if not body:
        raise Invalid("A message is required.")
    if len(body) > settings.ticket_message_max_chars:
        raise Invalid("That message is too long.")
    if len(attachments) > settings.ticket_attachment_max_count:
        raise Invalid("Too many attachments.")
    for item in attachments:
        if item.content_type.lower() not in attachment_store.INLINE_SAFE_TYPES:
            raise Invalid("That file type is not accepted.")

    # `attachment_max_bytes` is a budget shared across the whole submission,
    # not a per-file allowance: that is how `attachments.store` spends it,
    # and store *skips* whatever no longer fits. Checking the same total
    # here is what stops the two from disagreeing -- five 6 MiB files would
    # otherwise each clear a per-file check, and then store would silently
    # keep four of them and drop the fifth while the submitter was told the
    # ticket was received.
    total = sum(len(item.content) for item in attachments)
    if total > settings.attachment_max_bytes:
        raise Invalid("Those files are too large.")

    return body


async def over_email_cap(
    session: AsyncSession, workspace_id: uuid.UUID, email: str
) -> bool:
    """Whether this address has already opened too many tickets this hour.

    Reported rather than raised so the caller decides the wording. The
    portal router raises exactly the exception the IP cap raises, with
    exactly the same message: a caller who can tell the two caps apart --
    by status code or by wording -- learns which control fired and how to
    route around it. The address is free text and never attested, so this
    cap is evaded by varying it; it is a courtesy bound on one honest
    submitter, not a defence.
    """
    return await ingest._over_cap(session, workspace_id, email)


async def submit(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    email: str,
    name: str,
    subject: str,
    message: str,
    attachments: Sequence[ParsedAttachment],
) -> Conversation:
    """Turn an anonymous portal submission into an ordinary inbox ticket.

    Composes the same services email ingest uses, so a portal ticket and an
    emailed one are the same rows -- the only difference is the channel,
    which records that the sender's address was never attested (spec D1/D2).

    Re-runs `validate` and `over_email_cap` even though the portal router
    has already called both: they are cheap, and a future second caller of
    this function must not be able to write a ticket that skipped them.
    """
    body = validate(message, attachments)

    if await over_email_cap(session, workspace_id, email):
        raise TooManyRequests("We could not accept that just now.")

    display_name = name.strip() or email
    contact = await contacts.upsert(session, workspace_id, email, display_name)

    now = datetime.now(UTC)
    conversation = await conversations.create_conversation(
        session,
        workspace_id,
        contact,
        subject.strip() or f"Message from {display_name}",
        Channel.portal,
        now,
    )
    # ``create_conversation`` sets ``contact_id`` but never touches the
    # ``contact`` relationship, and that relationship's ``lazy="selectin"``
    # strategy only fires for objects returned by a query -- not for one
    # this call just constructed and flushed. Without this, the very next
    # line to read ``conversation.contact`` on the object this function
    # returns would try a synchronous lazy load outside of any awaited
    # call and blow up with ``MissingGreenlet``. We already hold the exact
    # ``Contact`` instance, so assign it directly instead of paying for a
    # refresh.
    conversation.contact = contact
    appended = await conversations.append_message(
        session,
        conversation,
        role=MessageRole.customer,
        direction=MessageDirection.inbound,
        author_name=display_name,
        body=body,
        sent_at=now,
    )
    if attachments:
        await attachment_store.store(session, appended, attachments)

    await session.flush()
    return conversation


async def create_from_api(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    email: str,
    name: str,
    subject: str,
    message: str,
    priority: Priority,
    external_id: str | None,
    metadata: dict,
    actor: Actor,
) -> tuple[Conversation, bool]:
    """Open a ticket on behalf of an API caller.

    Returns ``(conversation, created)``. ``created`` is ``False`` when
    ``external_id`` matched a conversation this workspace already has, which
    is what makes an interrupted import safe to re-run: the caller retries
    the whole batch and gets its original tickets back rather than a second
    copy of each.

    Composes the same services email ingest and the portal form use, so an
    API ticket is the same rows as an emailed one. The differences are the
    channel, the caller's own identifier, and the activity event: unlike
    inbound mail, this creation has a principal, and recording it is what
    makes "show me everything this key did" answerable later.
    """
    body = message.strip()
    if not body:
        raise Invalid("A message is required.")
    if len(body) > get_settings().ticket_message_max_chars:
        raise Invalid("That message is too long.")

    if external_id:
        existing = await session.scalar(
            sa.select(Conversation).where(
                Conversation.workspace_id == workspace_id,
                Conversation.external_id == external_id,
            )
        )
        if existing is not None:
            return existing, False

    display_name = name.strip() or email
    contact = await contacts.upsert(session, workspace_id, email, display_name)

    now = datetime.now(UTC)
    conversation = await conversations.create_conversation(
        session,
        workspace_id,
        contact,
        subject.strip() or f"Message from {display_name}",
        Channel.api,
        now,
    )
    # See the note in ``submit``: ``create_conversation`` sets ``contact_id``
    # but not the relationship, and a selectin strategy does not fire for an
    # object this call just constructed.
    conversation.contact = contact
    conversation.priority = priority
    conversation.meta = metadata

    await conversations.append_message(
        session,
        conversation,
        role=MessageRole.customer,
        direction=MessageDirection.inbound,
        author_name=display_name,
        body=body,
        sent_at=now,
    )
    conversations.record(
        session,
        conversation,
        actor,
        ActivityKind.created,
        "opened this through the API",
        "",
    )

    # Assigned only now, and not up with ``priority``/``meta`` above:
    # ``append_message`` calls its own ``session.flush()`` internally, and a
    # dirty ``external_id`` would ride along on *that* flush -- outside the
    # savepoint below -- so a concurrent duplicate would raise
    # ``IntegrityError`` straight through this function instead of being
    # caught. Setting it right before the guarded flush keeps the only
    # write that can violate the unique index inside the savepoint that
    # catches it.
    conversation.external_id = external_id

    try:
        # A savepoint, not a bare flush. Two concurrent creates carrying the
        # same external_id both miss the lookup above and both insert; the
        # partial unique index refuses the loser. Same shape as the race
        # ``contacts.upsert`` handles.
        async with session.begin_nested():
            await session.flush()
    except IntegrityError:
        # Unlike ``contacts.upsert``, nothing earlier in *this* session needs
        # to survive: every row touched above (contact, conversation,
        # message, activity event) belongs to the losing attempt and must
        # not persist once a duplicate ``external_id`` is discovered. A
        # failed flush leaves the whole session -- not just the savepoint --
        # unusable until an explicit rollback, per SQLAlchemy; since we want
        # everything this call did undone anyway, a full rollback is both
        # required and correct here.
        await session.rollback()
        if not external_id:
            raise
        existing = await session.scalar(
            sa.select(Conversation).where(
                Conversation.workspace_id == workspace_id,
                Conversation.external_id == external_id,
            )
        )
        if existing is None:
            raise
        return existing, False

    await session.commit()
    # ``updated_at`` and ``assignee_id`` on top of the usual refresh list:
    # the flush above issues an UPDATE (priority/external_id/meta on a row
    # that ``create_conversation`` already INSERTed), and that UPDATE's
    # ``onupdate=func.now()`` on ``updated_at`` -- and the never-explicitly
    # -set ``assignee_id`` -- come back from Postgres unresolved rather than
    # via RETURNING, so both are left expired. ``conversation_out`` reads
    # both directly (not through a relationship), so without naming them
    # here the very next line to touch either raises ``MissingGreenlet``.
    await session.refresh(
        conversation, ["labels", "assignee", "updated_at", "assignee_id"]
    )
    return conversation, True
