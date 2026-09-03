import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Unauthorized
from relaydesk.models import (
    Membership,
    MembershipStatus,
    Role,
    User,
    UserIdentity,
    Workspace,
)
from relaydesk.security.oauth_google import GoogleProfile
from relaydesk.services import auth


async def seed_member(session: AsyncSession, email: str) -> User:
    workspace = Workspace(name="Chronon", slug="chronon", monogram="CH")
    user = User(email=email, name="Nilesh Pant", monogram="NP")
    session.add_all([workspace, user])
    await session.flush()
    session.add(
        Membership(
            workspace_id=workspace.id,
            user_id=user.id,
            role=Role.admin,
            status=MembershipStatus.active,
        )
    )
    await session.commit()
    return user


async def test_google_login_links_an_existing_member(db_session: AsyncSession) -> None:
    user = await seed_member(db_session, "nilesh@relaydesk.dev")
    profile = GoogleProfile(
        sub="google-123",
        email="nilesh@relaydesk.dev",
        name="Nilesh Pant",
        email_verified=True,
    )

    result = await auth.login_with_google(db_session, profile)

    assert result.id == user.id
    identity = await db_session.scalar(
        UserIdentity.__table__.select().where(
            UserIdentity.provider_account_id == "google-123"
        )
    )
    assert identity is not None


async def test_google_login_is_idempotent(db_session: AsyncSession) -> None:
    await seed_member(db_session, "nilesh@relaydesk.dev")
    profile = GoogleProfile(
        sub="google-123",
        email="nilesh@relaydesk.dev",
        name="Nilesh Pant",
        email_verified=True,
    )

    first = await auth.login_with_google(db_session, profile)
    second = await auth.login_with_google(db_session, profile)

    assert first.id == second.id


async def test_unknown_email_is_rejected(db_session: AsyncSession) -> None:
    profile = GoogleProfile(
        sub="google-999",
        email="stranger@example.com",
        name="Stranger",
        email_verified=True,
    )

    with pytest.raises(Unauthorized):
        await auth.login_with_google(db_session, profile)


async def test_unverified_email_is_rejected(db_session: AsyncSession) -> None:
    await seed_member(db_session, "nilesh@relaydesk.dev")
    profile = GoogleProfile(
        sub="google-123",
        email="nilesh@relaydesk.dev",
        name="Nilesh",
        email_verified=False,
    )

    with pytest.raises(Unauthorized):
        await auth.login_with_google(db_session, profile)


async def test_member_without_active_membership_is_rejected(
    db_session: AsyncSession,
) -> None:
    user = User(email="orphan@relaydesk.dev", name="Orphan", monogram="OR")
    db_session.add(user)
    await db_session.commit()
    profile = GoogleProfile(
        sub="google-777",
        email="orphan@relaydesk.dev",
        name="Orphan",
        email_verified=True,
    )

    with pytest.raises(Unauthorized):
        await auth.login_with_google(db_session, profile)
