from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.config import get_settings
from relaydesk.errors import Unauthorized
from relaydesk.models import Membership, MembershipStatus, Session, User
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


async def active_membership(session: AsyncSession, user: User) -> Membership:
    """Return the user's one active membership.

    Deliberately scoped by user only, not by workspace: this slice assumes a
    single active membership per user (the console has no workspace switcher
    yet). If a user ever holds more than one active membership, ``scalar()``
    picks whichever row comes back first — don't build multi-workspace
    behaviour on top of this without revisiting it.
    """
    membership = await session.scalar(
        sa.select(Membership).where(
            Membership.user_id == user.id,
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
    user_agent: str | None = None,
    ip: str | None = None,
) -> tuple[str, Session]:
    """Return the plaintext token and the stored row. Only the hash persists."""
    settings = get_settings()
    now = datetime.now(UTC)
    token = generate_token()
    row = Session(
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=now + timedelta(days=settings.session_ttl_days),
        last_seen_at=now,
        user_agent=user_agent[:USER_AGENT_MAX_LENGTH] if user_agent else user_agent,
        ip=ip,
    )
    session.add(row)
    await session.commit()
    return token, row


async def resolve_session(session: AsyncSession, token: str) -> User:
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
    return user


async def revoke_session(session: AsyncSession, token: str) -> None:
    await session.execute(
        sa.delete(Session).where(Session.token_hash == hash_token(token))
    )
    await session.commit()
