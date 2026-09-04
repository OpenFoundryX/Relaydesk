import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.cli import bootstrap, seed
from relaydesk.models import Conversation, Label, Membership, SavedView, User, Workspace


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
