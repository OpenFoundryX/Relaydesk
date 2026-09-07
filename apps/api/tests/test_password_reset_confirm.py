from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa

from relaydesk.errors import NotFound, Unauthorized
from relaydesk.models import Membership, PasswordReset, Role
from relaydesk.models import Session as SessionRow
from relaydesk.security.passwords import verify_password
from relaydesk.services import auth, password_reset, team
from tests.factories import make_member, make_workspace

IP = "203.0.113.9"


async def _issue(db_session, outbox, email="nilesh@example.com") -> str:
    await password_reset.request(db_session, email, IP)
    return outbox[-1]["text"].split("/reset-password#")[1].split()[0]


async def test_confirming_sets_the_new_password(db_session, outbox) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace, email="nilesh@example.com")
    await db_session.commit()
    token = await _issue(db_session, outbox)

    await password_reset.confirm(db_session, token, "a-brand-new-password")

    await db_session.refresh(user)
    assert verify_password("a-brand-new-password", user.password_hash)


async def test_confirming_consumes_the_token(db_session, outbox) -> None:
    """Decision D3: the row is deleted, so a replay is indistinguishable
    from a token that never existed."""
    workspace = await make_workspace(db_session)
    await make_member(db_session, workspace, email="nilesh@example.com")
    await db_session.commit()
    token = await _issue(db_session, outbox)

    await password_reset.confirm(db_session, token, "a-brand-new-password")

    assert await db_session.scalar(
        sa.select(sa.func.count()).select_from(PasswordReset)
    ) == 0

    with pytest.raises(NotFound) as replayed:
        await password_reset.confirm(db_session, token, "another-password")

    with pytest.raises(NotFound) as never_existed:
        await password_reset.confirm(db_session, "not-a-real-token", "another-password")

    assert str(replayed.value) == str(never_existed.value)


async def test_an_expired_token_is_refused(db_session, outbox) -> None:
    workspace = await make_workspace(db_session)
    await make_member(db_session, workspace, email="nilesh@example.com")
    await db_session.commit()
    token = await _issue(db_session, outbox)

    row = await db_session.scalar(sa.select(PasswordReset))
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.commit()

    with pytest.raises(NotFound) as expired:
        await password_reset.confirm(db_session, token, "a-brand-new-password")

    # Pinned to the exact message, not just any NotFound: a distinct
    # EXPIRED_LINK message on this branch would still satisfy the replay
    # test above (that one compares two never-existed rows), so the
    # missing/expired identity has to be checked here directly.
    assert str(expired.value) == password_reset.INVALID_LINK


async def test_confirming_clears_the_login_lockout(db_session, outbox) -> None:
    """A user who forgot their password and one guessing at it look the same
    to authenticate(), so the user most likely to need a reset is
    disproportionately likely to have tripped the lockout getting here.
    Leaving it set means a correct new password is still refused, with the
    same message, for fifteen minutes."""
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace, email="nilesh@example.com")
    user.failed_login_count = 5
    user.locked_until = datetime.now(UTC) + timedelta(minutes=15)
    await db_session.commit()
    token = await _issue(db_session, outbox)

    await password_reset.confirm(db_session, token, "a-brand-new-password")

    await db_session.refresh(user)
    assert user.failed_login_count == 0
    assert user.locked_until is None

    signed_in = await auth.authenticate(
        db_session, "nilesh@example.com", "a-brand-new-password"
    )
    assert signed_in.id == user.id


async def test_confirming_revokes_every_session(db_session, outbox) -> None:
    """Decision D5. If the reset answered a compromise, not revoking means
    the attacker's session survives the exact action taken to evict them --
    for up to session_ttl_days, which defaults to 30."""
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace, email="nilesh@example.com")
    await db_session.commit()

    membership = await auth.default_membership(db_session, user)
    first, _ = await auth.create_session(db_session, user, membership)
    second, _ = await auth.create_session(db_session, user, membership)
    assert await db_session.scalar(
        sa.select(sa.func.count()).select_from(SessionRow)
    ) == 2

    token = await _issue(db_session, outbox)
    await password_reset.confirm(db_session, token, "a-brand-new-password")

    assert await db_session.scalar(
        sa.select(sa.func.count()).select_from(SessionRow)
    ) == 0
    for stale in (first, second):
        with pytest.raises(Unauthorized):
            await auth.resolve_session(db_session, stale)


async def test_one_users_reset_does_not_touch_another(db_session, outbox) -> None:
    workspace = await make_workspace(db_session)
    await make_member(db_session, workspace, email="nilesh@example.com")
    sara = await make_member(
        db_session, workspace, email="sara@example.com", name="Sara Vidal"
    )
    await db_session.commit()

    sara_membership = await auth.active_membership(db_session, sara, workspace.id)
    await auth.create_session(db_session, sara, sara_membership)
    sara_hash = sara.password_hash

    # An unscoped `sa.delete(PasswordReset)` on confirm would still pass
    # every other test in this file, since none of them mints a second
    # user's token. Minting one here is what would catch it.
    await _issue(db_session, outbox, email="sara@example.com")

    token = await _issue(db_session, outbox)
    await password_reset.confirm(db_session, token, "a-brand-new-password")

    await db_session.refresh(sara)
    assert sara.password_hash == sara_hash
    remaining = await db_session.scalar(
        sa.select(sa.func.count())
        .select_from(SessionRow)
        .where(SessionRow.user_id == sara.id)
    )
    assert remaining == 1
    sara_resets = await db_session.scalar(
        sa.select(sa.func.count())
        .select_from(PasswordReset)
        .where(PasswordReset.user_id == sara.id)
    )
    assert sara_resets == 1


async def test_accepting_an_invite_revokes_a_live_reset_on_the_adopted_row(
    db_session, outbox
) -> None:
    """Finding 1: an unclaimed row can carry a reset token that is still
    live -- it was minted while the row's previous occupant held a
    membership, and `request()` never re-checks that once the token
    exists. If accepting an invite adopted the row without revoking that
    token, the previous occupant could spend it after the fact and take
    the row right back from whoever just accepted the invite for it. This
    is ordinary address reuse (an employee leaves, their address is
    reassigned), not an exotic attack."""
    workspace = await make_workspace(db_session)
    admin = await make_member(
        db_session, workspace, email="admin@example.com", role=Role.admin
    )
    nilesh = await make_member(db_session, workspace, email="nilesh@example.com")
    await db_session.commit()

    token = await _issue(db_session, outbox)

    # Release nilesh's membership, leaving the row unclaimed -- the same
    # state `accept_invite` treats as adoptable.
    await db_session.execute(
        sa.delete(Membership).where(Membership.user_id == nilesh.id)
    )
    await db_session.commit()

    _invite, invite_token = await team.create_invite(
        db_session, workspace.id, "nilesh@example.com", Role.agent, admin.id
    )
    accepted, _membership = await team.accept_invite(
        db_session, invite_token, "New Nilesh", "accepter-chosen-password"
    )
    assert accepted.id == nilesh.id

    with pytest.raises(NotFound):
        await password_reset.confirm(db_session, token, "attacker-chosen-password")

    await db_session.refresh(accepted)
    assert verify_password("accepter-chosen-password", accepted.password_hash)
