import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Conflict, NotFound
from relaydesk.models import (
    Invite,
    Membership,
    MembershipStatus,
    PasswordReset,
    Role,
    User,
)
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
        sa.select(Invite).where(Invite.workspace_id == workspace_id)
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


# --- Invites: reachable over HTTP -----------------------------------------
#
# Three successive security reviews each found a live cross-tenant account
# takeover here: an invite bound an email address nobody had proved they
# controlled, and accepting one both adopted a (possibly pre-existing)
# account and issued a session for it. Four residual risks were recorded
# when this was disabled. Two are closed elsewhere; two are closed by this
# task, and by the same mechanism:
#
# * A session outliving the membership it was minted for, and two
#   concurrent accepts of *different* invites to the same email resolving
#   to an arbitrary workspace on login — both closed in `services.auth`.
#   `create_session` now stamps `workspace_id` from the membership it was
#   minted for, so a session can't outlive it and silently re-point at
#   whatever workspace the account joins next; `default_membership` now
#   picks deterministically (`ORDER BY created_at, id`) instead of
#   arbitrarily.
# * `user_identities` surviving account adoption, and an admin who invites
#   an address he does not control keeping the resulting membership and
#   permanently burning that address — both closed here, by delivery rather
#   than a new check. `relaydesk.api.team` never puts the invite token or an
#   invite URL in a response body: `create_team_invite` mails it via
#   `notifications.notify_invite` and answers the caller with a bare 202.
#   Only whoever controls the invited mailbox can ever obtain the token, so
#   only that person can accept — an admin can no longer self-accept an
#   invite for an address he doesn't own (closing the squat), and whoever
#   *does* adopt an account has, by construction, just proved control of
#   its address (closing the identity-adoption risk).
#
# `accept_invite` also deletes the invite row in the same transaction that
# creates the membership, instead of setting `accepted_at`: a token that
# leaks from a mail archive after being used is inert because there is
# nothing left for it to match, not merely rejected by a check. (A first
# pass at this had the public routes take the token as a path segment,
# `GET/POST /invites/{token}...`; that logs the live token to uvicorn's
# access log on every preview or accept, which is the same leak relocated
# rather than closed. Both public routes take the token in the request body
# instead, and the emailed link carries it as a URL fragment, which is never
# sent to any server — see `relaydesk.api.team` and
# `notifications.notify_invite`.)
#
# Do not add an invite URL, or the raw token, to any response body, log
# line, error message, or URL path/query segment — that is the exact leak
# this replaced.
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
    """Look up a still-usable invite by its plaintext token.

    A once-accepted invite's row is gone (`accept_invite` deletes it), so a
    replayed token looks exactly like one that never existed: both raise
    NotFound. There is nothing left to tell them apart by, and no reason to
    confirm to a caller that a given token used to be valid.
    """
    invite = await session.scalar(
        sa.select(Invite).where(Invite.token_hash == hash_token(token))
    )
    if invite is None or invite.expires_at <= datetime.now(UTC):
        raise NotFound("This invite is not valid.")
    return invite


ALREADY_A_MEMBER = (
    "This address already belongs to a Relaydesk workspace. "
    "Sign in with that account instead."
)


async def accept_invite(
    session: AsyncSession, token: str, name: str, password: str
) -> tuple[User, Membership]:
    """Turn an invite into an active membership.

    Returns the membership too, not just the user: the caller mints a
    session for it directly (``auth.create_session(session, user,
    membership, ...)``) rather than re-deriving "the workspace this login
    resolves to" via ``auth.default_membership``. That query is scoped to
    the user and would, today, happen to return the same row — but only
    because this function refuses to run at all for a user who already
    holds an active membership elsewhere. Handing back the exact row this
    call created makes the session's workspace direct, not an inference
    that depends on a guarantee living in a different function.

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
      real invitee's typed password has to win: nobody else is relying on
      the row, and the alternative silently discards what they typed.
    * **Claimed** — the user holds an active membership. Refuse with
      ``Conflict``. This is what protects a real account (the Google-only
      member of another workspace), and it is also what enforces the
      one-active-membership-per-user assumption ``services.auth`` is
      written against: ``active_membership`` resolves a user's workspace
      with no tiebreak, so a second active membership would make login pick
      one arbitrarily.

    Slice 5 added a password-reset flow (see
    ``docs/superpowers/specs/2026-09-07-password-reset-design.md``). An
    earlier version of this docstring justified the adoption above partly
    on there being no way to recover from the wrong password winning. That
    is no longer true, and it was never the load-bearing reason — the
    squatting defense below is. The adoption rule itself is unchanged, but
    adoption now also revokes any outstanding reset token on the row: a
    token can only have been minted while the row still had an active
    membership, so it belongs to whoever held that membership, not to
    whoever adopts the row after it lapses.

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
            # A row is only unclaimed here because it has no active
            # membership, and `password_reset.request` refuses to mint a
            # token for a user with none. So any reset row still on this
            # user was minted while the *previous* occupant held the
            # membership, and must not survive into the new occupant's
            # account -- otherwise the previous occupant could later spend
            # it to take over the row this accepter just adopted.
            await session.execute(
                sa.delete(PasswordReset).where(PasswordReset.user_id == user.id)
            )

        membership = Membership(
            workspace_id=invite.workspace_id,
            user_id=user.id,
            role=invite.role,
            status=MembershipStatus.active,
        )
        session.add(membership)
        # Single-use by deletion, not by flag: once the row is gone there is
        # nothing left for a replayed token to match against (see
        # `read_invite`).
        await session.delete(invite)
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise Conflict("This invite has already been accepted.") from error
    return user, membership
