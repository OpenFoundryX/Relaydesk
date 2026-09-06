import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.email_parse.normalize import ParsedAttachment
from relaydesk.errors import Invalid
from relaydesk.models.conversation import Channel, Conversation
from relaydesk.models.message import Message, MessageDirection, MessageRole
from relaydesk.services import tickets
from tests.factories import make_workspace


def _file(name: str = "shot.png", content_type: str = "image/png") -> ParsedAttachment:
    return ParsedAttachment(
        filename=name,
        content_type=content_type,
        content=b"\x89PNG\r\n\x1a\n" + b"0" * 32,
        inline=False,
        content_id=None,
    )


async def test_a_submission_opens_a_conversation(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)

    conversation = await tickets.submit(
        db_session,
        workspace.id,
        email="ada@example.dev",
        name="Ada",
        subject="Refund please",
        message="My order never arrived.",
        attachments=[],
    )

    assert conversation.channel is Channel.portal
    assert conversation.subject == "Refund please"
    assert conversation.contact.email == "ada@example.dev"


async def test_the_first_message_is_an_inbound_customer_message(
    db_session: AsyncSession,
) -> None:
    workspace = await make_workspace(db_session)

    await tickets.submit(
        db_session,
        workspace.id,
        email="ada@example.dev",
        name="Ada",
        subject="Refund please",
        message="My order never arrived.",
        attachments=[],
    )

    message = await db_session.scalar(sa.select(Message))
    assert message.role is MessageRole.customer
    assert message.direction is MessageDirection.inbound
    assert message.body == "My order never arrived."


async def test_a_missing_subject_falls_back_rather_than_failing(
    db_session: AsyncSession,
) -> None:
    """The form does not require a subject. An inbox row with a blank title
    is worse than one titled from the sender."""
    workspace = await make_workspace(db_session)

    conversation = await tickets.submit(
        db_session,
        workspace.id,
        email="ada@example.dev",
        name="Ada",
        subject="",
        message="My order never arrived.",
        attachments=[],
    )

    assert conversation.subject == "Message from Ada"


async def test_an_empty_message_is_refused(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)

    with pytest.raises(Invalid):
        await tickets.submit(
            db_session,
            workspace.id,
            email="ada@example.dev",
            name="Ada",
            subject="Refund please",
            message="   ",
            attachments=[],
        )


async def test_an_oversize_message_is_refused(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)

    with pytest.raises(Invalid):
        await tickets.submit(
            db_session,
            workspace.id,
            email="ada@example.dev",
            name="Ada",
            subject="Refund please",
            message="x" * 10_001,
            attachments=[],
        )


async def test_too_many_attachments_are_refused(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)

    with pytest.raises(Invalid):
        await tickets.submit(
            db_session,
            workspace.id,
            email="ada@example.dev",
            name="Ada",
            subject="Refund please",
            message="See these.",
            attachments=[_file(f"{index}.png") for index in range(6)],
        )


async def test_a_disallowed_content_type_is_refused(db_session: AsyncSession) -> None:
    """SVG executes script when rendered inline. The allowlist is shared with
    email attachments so there is exactly one list to keep right."""
    workspace = await make_workspace(db_session)

    with pytest.raises(Invalid):
        await tickets.submit(
            db_session,
            workspace.id,
            email="ada@example.dev",
            name="Ada",
            subject="Refund please",
            message="See this.",
            attachments=[_file("x.svg", "image/svg+xml")],
        )


async def test_an_attachment_is_stored(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)

    conversation = await tickets.submit(
        db_session,
        workspace.id,
        email="ada@example.dev",
        name="Ada",
        subject="Refund please",
        message="See this.",
        attachments=[_file()],
    )

    message = await db_session.scalar(
        sa.select(Message).where(Message.conversation_id == conversation.id)
    )
    assert len(message.attachments) == 1
    assert message.attachments[0].filename == "shot.png"


async def test_a_submission_never_threads_into_an_existing_conversation(
    db_session: AsyncSession,
) -> None:
    """Spec D4. Threading an unattested submission into a stranger's thread
    would hand them its contents."""
    workspace = await make_workspace(db_session)
    for _ in range(2):
        await tickets.submit(
            db_session,
            workspace.id,
            email="ada@example.dev",
            name="Ada",
            subject="Refund please",
            message="Still waiting.",
            attachments=[],
        )

    count = await db_session.scalar(
        sa.select(sa.func.count()).select_from(Conversation)
    )
    assert count == 2


async def test_a_sender_over_the_hourly_cap_is_refused(
    db_session: AsyncSession,
) -> None:
    """Reuses the same per-contact cap email ingest enforces."""
    workspace = await make_workspace(db_session)
    for _ in range(20):
        await tickets.submit(
            db_session,
            workspace.id,
            email="flood@example.dev",
            name="Flood",
            subject="Hi",
            message="Hi",
            attachments=[],
        )

    with pytest.raises(Invalid):
        await tickets.submit(
            db_session,
            workspace.id,
            email="flood@example.dev",
            name="Flood",
            subject="Hi",
            message="Hi",
            attachments=[],
        )
