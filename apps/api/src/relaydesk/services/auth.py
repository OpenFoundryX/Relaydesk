from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.config import get_settings
from relaydesk.errors import Unauthorized
from relaydesk.models import User
from relaydesk.security.passwords import verify_password

BAD_CREDENTIALS = "Email or password is incorrect."


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    """Verify credentials, enforcing an attempt lockout.

    Every failure raises the same message, so the endpoint cannot be used to
    discover which addresses have accounts.
    """
    settings = get_settings()
    user = await session.scalar(sa.select(User).where(User.email == email))
    if user is None:
        raise Unauthorized(BAD_CREDENTIALS)

    now = datetime.now(UTC)
    if user.locked_until is not None:
        if user.locked_until > now:
            raise Unauthorized(BAD_CREDENTIALS)
        user.failed_login_count = 0
        user.locked_until = None

    if user.password_hash is None or not verify_password(password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= settings.login_max_attempts:
            user.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
        await session.commit()
        raise Unauthorized(BAD_CREDENTIALS)

    user.failed_login_count = 0
    user.locked_until = None
    await session.commit()
    return user
