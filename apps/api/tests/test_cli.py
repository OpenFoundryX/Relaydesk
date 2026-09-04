import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.cli import ADMIN_PASSWORD_ENV, bootstrap, resolve_admin_password, seed
from relaydesk.models import (
    ActivityEvent,
    ActivityKind,
    Conversation,
    Label,
    Membership,
    SavedView,
    User,
    Workspace,
)


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


def test_the_admin_password_comes_from_the_environment_first(monkeypatch) -> None:
    monkeypatch.setenv(ADMIN_PASSWORD_ENV, "from-the-env")

    assert resolve_admin_password("from-argv") == "from-the-env"


def test_the_admin_password_falls_back_to_the_flag(monkeypatch) -> None:
    monkeypatch.delenv(ADMIN_PASSWORD_ENV, raising=False)

    assert resolve_admin_password("from-argv") == "from-argv"
    assert resolve_admin_password(None) is None
