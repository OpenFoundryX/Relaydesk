import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Unauthorized
from relaydesk.models.membership import Membership
from relaydesk.models.user import User
from relaydesk.services import auth
from tests.factories import make_member, make_workspace


async def _membership(session: AsyncSession, workspace, user: User) -> Membership:
    """make_member returns the User; these tests also need the Membership row."""
    return await session.scalar(
        sa.select(Membership).where(
            Membership.user_id == user.id,
            Membership.workspace_id == workspace.id,
        )
    )


async def test_a_session_names_the_workspace_it_was_minted_for(
    db_session: AsyncSession,
) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace, email="ada@example.com")
    membership = await _membership(db_session, workspace, user)

    _token, row = await auth.create_session(db_session, user, membership)

    assert row.workspace_id == workspace.id


async def test_a_session_dies_with_its_membership(db_session: AsyncSession) -> None:
    """Previously the session survived and silently re-pointed at whatever
    workspace the user joined next — a removed agent's old token becoming a
    live token in someone else's workspace.

    ``remove_member`` (``services/team.py``) hard-deletes the membership
    row rather than flipping a status flag, so this mirrors that: delete
    the row, not mutate its status.
    """
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace, email="ada@example.com")
    membership = await _membership(db_session, workspace, user)
    token, _row = await auth.create_session(db_session, user, membership)

    await db_session.delete(membership)
    await db_session.commit()

    resolved, row = await auth.resolve_session(db_session, token)
    with pytest.raises(Unauthorized):
        await auth.active_membership(db_session, resolved, row.workspace_id)


async def test_a_second_membership_does_not_move_an_existing_session(
    db_session: AsyncSession,
) -> None:
    """Two active memberships used to make the resolved workspace arbitrary.
    Invites are what put that within reach of an ordinary user."""
    first = await make_workspace(db_session, slug="first")
    second = await make_workspace(db_session, slug="second")
    user = await make_member(db_session, first, email="ada@example.com")
    membership = await _membership(db_session, first, user)
    token, _row = await auth.create_session(db_session, user, membership)

    await make_member(db_session, second, email="ada@example.com", user=user)

    resolved, row = await auth.resolve_session(db_session, token)
    found = await auth.active_membership(db_session, resolved, row.workspace_id)

    assert found.workspace_id == first.id


async def test_login_picks_the_oldest_membership_deterministically(
    db_session: AsyncSession,
) -> None:
    first = await make_workspace(db_session, slug="first")
    second = await make_workspace(db_session, slug="second")
    user = await make_member(db_session, first, email="ada@example.com")
    await make_member(db_session, second, email="ada@example.com", user=user)

    chosen = await auth.default_membership(db_session, user)

    assert chosen.workspace_id == first.id
