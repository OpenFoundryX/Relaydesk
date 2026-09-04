"""The concurrent-accept race on a single invite token.

This one test cannot use the ``db_session`` fixture: that fixture wraps
everything in one connection and one outer transaction, so two "concurrent"
callers would share a transaction and never collide. Real concurrency needs
two independent connections, which means real commits — hence the explicit
teardown at the end.

It also has to *force* the interleaving. Left to chance, one caller commits
before the other reads, and the loser is turned away by ``read_invite``'s
"already accepted" check — which passes the assertions below while never
reaching the constraint the handler exists for. The barrier holds both
callers just past their invite read, so both are guaranteed to be mid-write
at the same time.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Conflict
from relaydesk.models import (
    Invite,
    Membership,
    MembershipStatus,
    Role,
    User,
    Workspace,
)
from relaydesk.security.passwords import hash_password
from relaydesk.security.tokens import generate_token, hash_token
from relaydesk.services import team

SLUG = "race-co"


async def test_two_concurrent_accepts_conflict_rather_than_500(
    engine, monkeypatch
) -> None:
    token = generate_token()

    async with AsyncSession(engine, expire_on_commit=False) as setup:
        workspace = Workspace(name="Race Co", slug=SLUG, monogram="RC")
        admin = User(
            email="admin@race-co.dev",
            name="Ada Admin",
            monogram="AA",
            password_hash=hash_password("relaydesk"),
        )
        setup.add_all([workspace, admin])
        await setup.flush()
        setup.add(
            Membership(
                workspace_id=workspace.id,
                user_id=admin.id,
                role=Role.admin,
                status=MembershipStatus.active,
            )
        )
        setup.add(
            Invite(
                workspace_id=workspace.id,
                email="racer@race-co.dev",
                role=Role.agent,
                token_hash=hash_token(token),
                invited_by=admin.id,
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
        )
        await setup.commit()
        workspace_id = workspace.id

    # Both callers read the invite as unaccepted, then proceed together.
    # `asyncio.Barrier` has no timeout of its own and the project has no
    # pytest-timeout dependency, so if one caller raised before reaching
    # `wait()` the other would block the whole suite forever — hence the
    # `wait_for` around the gather below.
    read_invite = team.read_invite
    barrier = asyncio.Barrier(2)

    async def gated_read_invite(session: AsyncSession, value: str) -> Invite:
        invite = await read_invite(session, value)
        await barrier.wait()
        return invite

    monkeypatch.setattr(team, "read_invite", gated_read_invite)

    async def attempt() -> Exception | None:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            try:
                await team.accept_invite(
                    session, token, "Ray Sir", "a-good-password"
                )
            except Exception as error:  # Reported to the caller, not swallowed.
                return error
        return None

    try:
        outcomes = await asyncio.wait_for(
            asyncio.gather(attempt(), attempt()), timeout=30
        )

        succeeded = [result for result in outcomes if result is None]
        failed = [result for result in outcomes if result is not None]
        assert len(succeeded) == 1, outcomes
        assert len(failed) == 1, outcomes
        # A Conflict, not an IntegrityError escaping as a bare 500 — and it
        # must come from the constraint, not from read_invite's own check,
        # or this test would pass with the handler deleted.
        assert isinstance(failed[0], Conflict)
        assert isinstance(failed[0].__cause__, IntegrityError)

        async with AsyncSession(engine) as check:
            memberships = await check.scalar(
                sa.select(sa.func.count())
                .select_from(Membership)
                .where(Membership.workspace_id == workspace_id)
            )
            users = await check.scalar(
                sa.select(sa.func.count())
                .select_from(User)
                .where(User.email == "racer@race-co.dev")
            )
        assert memberships == 2  # the admin, plus exactly one accepted invite
        assert users == 1
    finally:
        async with AsyncSession(engine) as cleanup:
            await cleanup.execute(
                sa.delete(Workspace).where(Workspace.slug == SLUG)
            )
            await cleanup.execute(
                sa.delete(User).where(
                    User.email.in_(["admin@race-co.dev", "racer@race-co.dev"])
                )
            )
            await cleanup.commit()
