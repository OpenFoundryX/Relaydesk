import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Conflict, NotFound
from relaydesk.models import Invite, Membership, MembershipStatus, Role, User
from relaydesk.security.passwords import hash_password
from relaydesk.security.tokens import generate_token, hash_token

INVITE_TTL = timedelta(days=14)
ROLE_LABEL = {Role.admin: "Admin", Role.agent: "Agent"}


@dataclass(slots=True)
class TeamMember:
    id: str
    name: str
    email: str
    role: str
    status: str


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
        )
        for invite in pending
    )
    return members


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


async def accept_invite(
    session: AsyncSession, token: str, name: str, password: str
) -> User:
    invite = await read_invite(session, token)

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
    elif user.password_hash is None:
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
    return user
