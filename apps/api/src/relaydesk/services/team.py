import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Conflict, NotFound
from relaydesk.models import Invite, Membership, MembershipStatus, Role, User
from relaydesk.security.passwords import hash_password
from relaydesk.security.tokens import generate_token, hash_token

INVITE_TTL = timedelta(days=14)
ROLE_LABEL = {Role.admin: "Admin", Role.agent: "Agent"}
LAST_ADMIN_MESSAGE = "A workspace must keep at least one admin."


@dataclass(slots=True)
class TeamMember:
    id: str
    name: str
    email: str
    role: str
    status: str
    user_id: str | None


def monogram_for(name: str) -> str:
    parts = [part for part in name.split() if part]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


async def list_members(
    session: AsyncSession, workspace_id: uuid.UUID
) -> list[TeamMember]:
    """Active members plus outstanding invites, which the console shows together."""
    rows = await session.execute(
        sa.select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(
            Membership.workspace_id == workspace_id,
            Membership.status == MembershipStatus.active,
        )
        .order_by(User.name)
    )
    members = [
        TeamMember(
            id=str(membership.id),
            name=user.name,
            email=user.email,
            role=ROLE_LABEL[membership.role],
            status=membership.status.value,
            user_id=str(user.id),
        )
        for membership, user in rows
    ]

    pending = await session.scalars(
        sa.select(Invite).where(
            Invite.workspace_id == workspace_id, Invite.accepted_at.is_(None)
        )
    )
    members.extend(
        TeamMember(
            id=str(invite.id),
            name=invite.email.split("@")[0],
            email=invite.email,
            role=ROLE_LABEL[invite.role],
            status="invited",
            user_id=None,
        )
        for invite in pending
    )
    return members


# --- Invites: retained but not exposed over HTTP -------------------------
#
# `create_invite`, `read_invite`, `accept_invite`, and `revoke_invite` below
# are NOT reachable from the API in this release (see `relaydesk.api.team`
# and `relaydesk.api.router`). They are kept — and kept tested — because the
# guards that *are* correct here (claimed-account -> Conflict, the
# IntegrityError race handling in `accept_invite`) are the foundation the
# next slice builds on. Do not re-expose any of this over HTTP until
# acceptance requires proof that the accepter controls the invited address
# (e.g. an emailed confirmation link) — the root problem is that an invite
# currently binds an email address that nobody has proved they control, and
# acceptance both adopts an account and issues a session for it. Specific
# residual issues the next implementer inherits rather than rediscovers:
#
# * Acceptance issues a session that outlives the membership it was minted
#   for. Sessions are user-scoped, not membership-scoped, and
#   `services.auth.active_membership` re-derives the workspace from the
#   user's *current* memberships on every request. So a session survives
#   its originating membership being deleted, and silently re-points at
#   whatever workspace that user's account joins next.
# * `user_identities` (federated/Google credentials) survive account
#   adoption in `accept_invite`. Adopting an unclaimed row changes who
#   controls the account without touching any identity row linked to it, so
#   a federated credential can outlive the change of owner.
# * Two concurrent `accept_invite` calls for two *different* invites to the
#   same email collide on nothing — there is no unique constraint stopping
#   one user from ending up with two active memberships in two workspaces.
#   `active_membership`'s whole design (a bare `SELECT ... WHERE user_id =`
#   with no `ORDER BY`) assumes exactly one active membership per user; two
#   makes which workspace a login resolves to arbitrary.
# * An admin who accepts an invite for an address he does not own and then
#   *keeps* the membership (rather than releasing it, as in the squat/
#   release test below) permanently burns that email address: it is now
#   "claimed" forever, so the real owner can never accept an invite to any
#   workspace for it.
async def create_invite(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    email: str,
    role: Role,
    invited_by: uuid.UUID,
) -> tuple[Invite, str]:
    existing = await session.scalar(
        sa.select(Membership)
        .join(User, User.id == Membership.user_id)
        .where(Membership.workspace_id == workspace_id, User.email == email)
    )
    if existing is not None:
        raise Conflict("That address is already on the team.")

    pending = await session.scalar(
        sa.select(Invite).where(
            Invite.workspace_id == workspace_id,
            Invite.email == email,
            Invite.accepted_at.is_(None),
        )
    )
    if pending is not None:
        raise Conflict("That address has already been invited.")

    token = generate_token()
    invite = Invite(
        workspace_id=workspace_id,
        email=email,
        role=role,
        token_hash=hash_token(token),
        invited_by=invited_by,
        expires_at=datetime.now(UTC) + INVITE_TTL,
    )
    session.add(invite)
    await session.commit()
    return invite, token


async def _active_admin_count(session: AsyncSession, workspace_id: uuid.UUID) -> int:
    count = await session.scalar(
        sa.select(sa.func.count())
        .select_from(Membership)
        .where(
            Membership.workspace_id == workspace_id,
            Membership.status == MembershipStatus.active,
            Membership.role == Role.admin,
        )
    )
    return count or 0


async def update_member_role(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    membership_id: uuid.UUID,
    role: Role,
) -> None:
    membership = await session.scalar(
        sa.select(Membership).where(
            Membership.id == membership_id, Membership.workspace_id == workspace_id
        )
    )
    if membership is None:
        raise NotFound("Member not found.")
    if membership.role is Role.admin and role is not Role.admin:
        admin_count = await _active_admin_count(session, workspace_id)
        if admin_count <= 1:
            raise Conflict(LAST_ADMIN_MESSAGE)
    membership.role = role
    await session.commit()


async def remove_member(
    session: AsyncSession, workspace_id: uuid.UUID, membership_id: uuid.UUID
) -> None:
    membership = await session.scalar(
        sa.select(Membership).where(
            Membership.id == membership_id, Membership.workspace_id == workspace_id
        )
    )
    if membership is None:
        raise NotFound("Member not found.")
    if membership.role is Role.admin:
        admin_count = await _active_admin_count(session, workspace_id)
        if admin_count <= 1:
            raise Conflict(LAST_ADMIN_MESSAGE)
    await session.delete(membership)
    await session.commit()


async def revoke_invite(
    session: AsyncSession, workspace_id: uuid.UUID, invite_id: uuid.UUID
) -> None:
    invite = await session.scalar(
        sa.select(Invite).where(
            Invite.id == invite_id, Invite.workspace_id == workspace_id
        )
    )
    if invite is None:
        raise NotFound("Invite not found.")
    await session.delete(invite)
    await session.commit()


async def read_invite(session: AsyncSession, token: str) -> Invite:
    invite = await session.scalar(
        sa.select(Invite).where(Invite.token_hash == hash_token(token))
    )
    if invite is None or invite.expires_at <= datetime.now(UTC):
        raise NotFound("This invite is not valid.")
    if invite.accepted_at is not None:
        raise Conflict("This invite has already been accepted.")
    return invite


ALREADY_A_MEMBER = (
    "This address already belongs to a Relaydesk workspace. "
    "Sign in with that account instead."
)


async def accept_invite(
    session: AsyncSession, token: str, name: str, password: str
) -> User:
    """Turn an invite into an active membership.

    This is reachable unauthenticated and whoever holds the token chooses
    the ``password`` in the payload, so the question is whose account the
    address is. The line is **claimed vs unclaimed**, not new vs
    pre-existing:

    * **Unclaimed** — no row at all, or a row with no active membership.
      Nobody is currently using the address to sign in to Relaydesk, so
      whoever accepts a valid invite for it is the person it now belongs
      to. Adopt the row: overwrite ``name`` and ``password_hash`` from the
      accepter's input. A pre-existing row here is a released ex-member, or
      an address an earlier admin minted-and-abandoned; in both cases the
      real invitee's typed password has to win, because there is no
      password-reset flow to recover from it losing.
    * **Claimed** — the user holds an active membership. Refuse with
      ``Conflict``. This is what protects a real account (the Google-only
      member of another workspace), and it is also what enforces the
      one-active-membership-per-user assumption ``services.auth`` is
      written against: ``active_membership`` resolves a user's workspace
      with no tiebreak, so a second active membership would make login pick
      one arbitrarily.

    Distinguishing on *pre-existing* instead would leave the address
    squattable: mint an invite for an address with no account, accept it
    yourself to create the row with your own password, then delete your own
    membership. The row is pre-existing but unclaimed, and the real person's
    later acceptance would be given a membership while their typed password
    was silently discarded — handing their account to the squatter.
    """
    invite = await read_invite(session, token)

    # Two concurrent accepts of one token both clear the guards below — they
    # read the invite as unaccepted before either commits — and then collide
    # on users.email (new account) or on memberships' (workspace_id,
    # user_id). Either way the loser gets a conflict rather than an
    # unhandled IntegrityError surfacing as a bare 500. The collision can be
    # raised by the flush as well as the commit, so both sit inside the try.
    try:
        user = await session.scalar(sa.select(User).where(User.email == invite.email))
        if user is None:
            user = User(
                email=invite.email,
                name=name,
                monogram=monogram_for(name),
                password_hash=hash_password(password),
            )
            session.add(user)
            await session.flush()
        else:
            claimed = await session.scalar(
                sa.select(Membership).where(
                    Membership.user_id == user.id,
                    Membership.status == MembershipStatus.active,
                )
            )
            if claimed is not None:
                raise Conflict(ALREADY_A_MEMBER)
            # Unclaimed: adopt the row rather than link to it. The monogram
            # is derived from the name, so it moves with it.
            user.name = name
            user.monogram = monogram_for(name)
            user.password_hash = hash_password(password)

        session.add(
            Membership(
                workspace_id=invite.workspace_id,
                user_id=user.id,
                role=invite.role,
                status=MembershipStatus.active,
            )
        )
        invite.accepted_at = datetime.now(UTC)
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise Conflict("This invite has already been accepted.") from error
    return user
