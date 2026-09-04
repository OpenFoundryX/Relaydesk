import uuid
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.config import get_settings
from relaydesk.errors import Unauthorized
from relaydesk.models import Membership, MembershipStatus, Session, User, UserIdentity
from relaydesk.security.oauth_google import GoogleProfile
from relaydesk.security.passwords import hash_password, verify_password
from relaydesk.security.tokens import generate_token, hash_token

BAD_CREDENTIALS = "Email or password is incorrect."
LAST_SEEN_INTERVAL = timedelta(hours=1)

# Precomputed once at import time so every failure path — unknown email or a
# user with no password set — pays the same argon2 cost as a real password
# check. Without this, an unknown email returns before ever hitting argon2,
# which is a timing side channel that defeats the point of a uniform error
# message.
_DUMMY_PASSWORD_HASH = hash_password("relaydesk-timing-safety-dummy")


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    """Verify credentials, enforcing an attempt lockout.

    Every failure raises the same message, so the endpoint cannot be used to
    discover which addresses have accounts.
    """
    settings = get_settings()
    user = await session.scalar(sa.select(User).where(User.email == email))
    if user is None:
        verify_password(password, _DUMMY_PASSWORD_HASH)
        raise Unauthorized(BAD_CREDENTIALS)

    now = datetime.now(UTC)
    if user.locked_until is not None:
        if user.locked_until > now:
            verify_password(password, _DUMMY_PASSWORD_HASH)
            raise Unauthorized(BAD_CREDENTIALS)
        user.failed_login_count = 0
        user.locked_until = None

    if user.password_hash is None:
        verify_password(password, _DUMMY_PASSWORD_HASH)
        password_ok = False
    else:
        password_ok = verify_password(password, user.password_hash)

    if not password_ok:
        user.failed_login_count += 1
        if user.failed_login_count >= settings.login_max_attempts:
            user.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
        await session.commit()
        raise Unauthorized(BAD_CREDENTIALS)

    user.failed_login_count = 0
    user.locked_until = None
    await session.commit()
    return user


async def default_membership(session: AsyncSession, user: User) -> Membership:
    """The membership a fresh login resolves to.

    Ordered so the answer is stable. There is no workspace switcher yet, so a
    user with two memberships always lands in the one they joined first
    rather than in whichever row the planner happened to return.
    """
    membership = await session.scalar(
        sa.select(Membership)
        .where(
            Membership.user_id == user.id,
            Membership.status == MembershipStatus.active,
        )
        .order_by(Membership.created_at, Membership.id)
        .limit(1)
    )
    if membership is None:
        raise Unauthorized(BAD_CREDENTIALS)
    return membership


async def active_membership(
    session: AsyncSession, user: User, workspace_id: uuid.UUID
) -> Membership:
    """The user's active membership in one specific workspace.

    Scoped by workspace because the session names one. A session must never
    follow its user into a workspace it was not minted for.
    """
    membership = await session.scalar(
        sa.select(Membership).where(
            Membership.user_id == user.id,
            Membership.workspace_id == workspace_id,
            Membership.status == MembershipStatus.active,
        )
    )
    if membership is None:
        raise Unauthorized(BAD_CREDENTIALS)
    return membership


# sessions.user_agent is a String(400); Postgres raises rather than
# truncates on overflow, so an oversized header would otherwise escape as an
# unhandled 500 instead of a normal login.
USER_AGENT_MAX_LENGTH = 400


async def create_session(
    session: AsyncSession,
    user: User,
    membership: Membership,
    user_agent: str | None = None,
    ip: str | None = None,
) -> tuple[str, Session]:
    """Return the plaintext token and the stored row. Only the hash persists."""
    settings = get_settings()
    now = datetime.now(UTC)
    token = generate_token()
    row = Session(
        user_id=user.id,
        workspace_id=membership.workspace_id,
        token_hash=hash_token(token),
        expires_at=now + timedelta(days=settings.session_ttl_days),
        last_seen_at=now,
        user_agent=user_agent[:USER_AGENT_MAX_LENGTH] if user_agent else user_agent,
        ip=ip,
    )
    session.add(row)
    await session.commit()
    return token, row


async def resolve_session(session: AsyncSession, token: str) -> tuple[User, Session]:
    now = datetime.now(UTC)
    row = await session.scalar(
        sa.select(Session).where(Session.token_hash == hash_token(token))
    )
    if row is None or row.expires_at <= now:
        raise Unauthorized("Session is invalid or has expired.")

    if now - row.last_seen_at > LAST_SEEN_INTERVAL:
        row.last_seen_at = now
        await session.commit()

    user = await session.get(User, row.user_id)
    if user is None:
        raise Unauthorized("Session is invalid or has expired.")
    return user, row


async def revoke_session(session: AsyncSession, token: str) -> None:
    await session.execute(
        sa.delete(Session).where(Session.token_hash == hash_token(token))
    )
    await session.commit()


async def login_with_google(session: AsyncSession, profile: GoogleProfile) -> User:
    """Log in an existing member through Google.

    There is no self-serve signup, so an address without an active
    membership is refused rather than provisioned.
    """
    if not profile.email_verified or not profile.email:
        raise Unauthorized("Google did not confirm this email address.")

    user = await session.scalar(sa.select(User).where(User.email == profile.email))
    if user is None:
        raise Unauthorized("No Relaydesk account matches this Google address.")

    await default_membership(session, user)

    identity = await session.scalar(
        sa.select(UserIdentity).where(
            UserIdentity.provider == "google",
            UserIdentity.provider_account_id == profile.sub,
        )
    )
    if identity is not None:
        if identity.user_id != user.id:
            # The (provider, provider_account_id) unique constraint means
            # this Google account is already linked to a different local
            # user than the one this email just resolved to.
            raise Unauthorized("This Google account is linked to a different user.")
        return user

    # ON CONFLICT DO NOTHING makes this tolerant of two concurrent
    # first-time logins for the same Google account: both would see
    # `identity is None` above, and without this the loser's plain INSERT
    # would hit the unique constraint as an unhandled IntegrityError -> 500.
    await session.execute(
        pg_insert(UserIdentity)
        .values(user_id=user.id, provider="google", provider_account_id=profile.sub)
        .on_conflict_do_nothing(index_elements=["provider", "provider_account_id"])
    )
    await session.commit()
    return user
