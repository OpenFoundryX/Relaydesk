from datetime import UTC, datetime
from email.message import EmailMessage

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.cli import (
    ADMIN_PASSWORD_ENV,
    bootstrap,
    resolve_admin_password,
    seed,
    unrouted,
)
from relaydesk.models import (
    ActivityEvent,
    ActivityKind,
    Conversation,
    Label,
    Membership,
    Message,
    RawMessage,
    SavedView,
    User,
    Workspace,
)
from relaydesk.models.channel_account import ChannelAccount
from relaydesk.services import channel_accounts, ingest
from tests.factories import make_workspace


async def test_seed_creates_a_demo_workspace(db_session: AsyncSession) -> None:
    await seed(db_session)

    workspace = await db_session.scalar(
        sa.select(Workspace).where(Workspace.slug == "chronon")
    )
    conversations = (await db_session.scalars(sa.select(Conversation))).all()
    labels = (await db_session.scalars(sa.select(Label))).all()
    views = (await db_session.scalars(sa.select(SavedView))).all()

    assert workspace is not None
    assert len(conversations) == 11
    assert len(labels) == 4
    assert len(views) == 3
    assert workspace.conversation_seq == 11


async def test_seed_messages_carry_the_address_they_were_sent_to(
    db_session: AsyncSession,
) -> None:
    """append_message takes an explicit `to_address`; the refactor onto it
    must not silently drop the recipient the old inline construction set."""
    await seed(db_session)

    messages = (await db_session.scalars(sa.select(Message))).all()

    assert len(messages) == 11
    assert all(message.to_address == "support@chronon.co" for message in messages)


async def test_seed_is_idempotent(db_session: AsyncSession) -> None:
    await seed(db_session)
    await seed(db_session)

    workspaces = (await db_session.scalars(sa.select(Workspace))).all()
    conversations = (await db_session.scalars(sa.select(Conversation))).all()

    assert len(workspaces) == 1
    assert len(conversations) == 11


async def test_bootstrap_creates_a_workspace_and_admin(
    db_session: AsyncSession,
) -> None:
    await bootstrap(
        db_session,
        workspace_name="Acme Support",
        admin_email="owner@acme.com",
        admin_name="Ada Owner",
        admin_password="a-real-password",
    )

    user = await db_session.scalar(
        sa.select(User).where(User.email == "owner@acme.com")
    )
    membership = await db_session.scalar(sa.select(Membership))
    conversations = (await db_session.scalars(sa.select(Conversation))).all()

    assert user is not None and user.password_hash is not None
    assert membership is not None and membership.role.value == "admin"
    assert conversations == []


async def test_bootstrap_refuses_to_run_twice(db_session: AsyncSession) -> None:
    kwargs = dict(
        workspace_name="Acme Support",
        admin_email="owner@acme.com",
        admin_name="Ada Owner",
        admin_password="a-real-password",
    )
    await bootstrap(db_session, **kwargs)

    from relaydesk.errors import Conflict

    try:
        await bootstrap(db_session, **kwargs)
    except Conflict:
        return
    raise AssertionError("expected bootstrap to refuse a second workspace")


async def test_seed_writes_an_opening_activity_event_per_conversation(
    db_session: AsyncSession,
) -> None:
    """The History tab reads empty on a fresh seed without these."""
    await seed(db_session)

    conversations = (await db_session.scalars(sa.select(Conversation))).all()
    events = (await db_session.scalars(sa.select(ActivityEvent))).all()
    admin = await db_session.scalar(
        sa.select(User).where(User.email == "nilesh@relaydesk.dev")
    )

    assert len(events) == len(conversations)
    assert {event.conversation_id for event in events} == {
        conversation.id for conversation in conversations
    }
    assert all(event.kind is ActivityKind.created for event in events)
    assert all(event.actor_user_id == admin.id for event in events)

    by_conversation = {event.conversation_id: event for event in events}
    for conversation in conversations:
        assert by_conversation[conversation.id].at == conversation.last_message_at


async def test_seed_gives_the_workspace_a_channel_account(
    db_session: AsyncSession,
) -> None:
    """Regression net for "no workspace exists without a channel account".

    A workspace with no channel account can never receive mail (Task 11's
    lookup would find nothing for it), silently and with no error. This
    fails the moment ``seed`` stops going through
    ``services.workspaces.create_workspace``.
    """
    await seed(db_session)

    workspace = await db_session.scalar(
        sa.select(Workspace).where(Workspace.slug == "chronon")
    )
    account = await db_session.scalar(
        sa.select(ChannelAccount).where(ChannelAccount.workspace_id == workspace.id)
    )

    assert account is not None


async def test_bootstrap_gives_the_workspace_a_channel_account(
    db_session: AsyncSession,
) -> None:
    """Same net as above, for ``bootstrap`` — the other creation path."""
    await bootstrap(
        db_session,
        workspace_name="Acme Support",
        admin_email="owner@acme.com",
        admin_name="Ada Owner",
        admin_password="a-real-password",
    )

    workspace = await db_session.scalar(sa.select(Workspace))
    account = await db_session.scalar(
        sa.select(ChannelAccount).where(ChannelAccount.workspace_id == workspace.id)
    )

    assert account is not None


def test_the_admin_password_comes_from_the_environment_first(monkeypatch) -> None:
    monkeypatch.setenv(ADMIN_PASSWORD_ENV, "from-the-env")

    assert resolve_admin_password("from-argv") == "from-the-env"


def test_the_admin_password_falls_back_to_the_flag(monkeypatch) -> None:
    monkeypatch.delenv(ADMIN_PASSWORD_ENV, raising=False)

    assert resolve_admin_password("from-argv") == "from-argv"
    assert resolve_admin_password(None) is None


def _raw(to: str, subject: str = "Hello") -> bytes:
    message = EmailMessage()
    message["From"] = "ada@example.com"
    message["To"] = to
    message["Subject"] = subject
    message["Date"] = "Tue, 2 Sep 2026 10:00:00 +0000"
    message["Message-ID"] = "<a1@example.com>"
    message.set_content("Hi there.")
    return message.as_bytes()


async def test_unrouted_lists_mail_that_failed_to_route_and_omits_the_rest(
    db_session: AsyncSession,
) -> None:
    """The bytes for undeliverable mail must stay visible to an operator --
    ``state = 'unrouted'`` is a value nothing else ever reads."""
    workspace = await make_workspace(db_session, slug="acme")
    account = await channel_accounts.create(db_session, workspace.id, "Support")
    await db_session.flush()
    address = channel_accounts.address_for(account, "acme")

    routed = RawMessage(
        mailbox="INBOX",
        uidvalidity=1,
        uid=1,
        raw=_raw(address, subject="Routed ok"),
        received_at=datetime.now(UTC),
    )
    unroutable = RawMessage(
        mailbox="INBOX",
        uidvalidity=1,
        uid=2,
        raw=_raw("someone-else@elsewhere.com", subject="Nowhere to go"),
        received_at=datetime.now(UTC),
    )
    db_session.add_all([routed, unroutable])
    await db_session.flush()

    await ingest.ingest_raw(db_session, routed.id)
    await ingest.ingest_raw(db_session, unroutable.id)

    rows = await unrouted(db_session)

    ids = {row.id for row in rows}
    assert unroutable.id in ids
    assert routed.id not in ids
