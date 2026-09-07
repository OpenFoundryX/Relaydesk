"""Forgot-password: issue a capability, and spend it.

Every path through ``request`` returns ``None``, including the ones that do
nothing. The caller cannot tell an unknown address from a real one, a
Google-only account from a password account, or a refused rate limit from
an accepted request -- the route answers 202 for all of them.

That uniformity is the primary enumeration defense, and it is not
complete: the path that sends mail does two writes and a broker publish
that the silent paths do not, which is measurable in principle. It is not
equalized with dummy work. The ``_DUMMY_PASSWORD_HASH`` trick in
``services.auth`` works there because the asymmetry is one argon2 call,
cheap and exact to pay unconditionally; here it would mean writing rows
nobody reads on a path an attacker triggers, which is a worse thing to own
than the channel it closes. The rate limits below are the mitigation:
distinguishing two addresses through a noisy timing difference needs
repeated samples per address, and three per hour per address denies them.
See section 6.2 of the design.
"""

from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.config import get_settings
from relaydesk.models.membership import Membership, MembershipStatus
from relaydesk.models.password_reset import PasswordReset
from relaydesk.models.user import User
from relaydesk.security.tokens import generate_token, hash_token
from relaydesk.services import notifications, ratelimit

WINDOW = timedelta(hours=1)


async def request(session: AsyncSession, email: str, ip_bucket: str) -> None:
    settings = get_settings()
    address = email.strip().lower()

    # Both limits are charged before anything is written. `ratelimit.check`
    # commits, so it has to come before any write this function might
    # otherwise want to roll back -- the ordering `api.public` documents at
    # its own call site.
    #
    # The IP bucket is charged first and returns on refusal without
    # touching the address bucket. Charging both would let a caller who has
    # already exhausted their own IP allowance keep burning down the
    # allowance of any address they name, which turns a rate limit into a
    # denial-of-service against a chosen user.
    within_ip = await ratelimit.check(
        session,
        "password_reset_ip",
        ip_bucket,
        limit=settings.password_reset_ip_hourly_cap,
        window=WINDOW,
    )
    if not within_ip:
        return

    within_address = await ratelimit.check(
        session,
        "password_reset_email",
        address,
        limit=settings.password_reset_email_hourly_cap,
        window=WINDOW,
    )
    if not within_address:
        return

    user = await session.scalar(sa.select(User).where(User.email == address))
    if user is None:
        return

    # Decision D1: an account that has never had a password is a Google
    # account, and its root of trust is Google. Minting a password from
    # mailbox control alone would convert it into a password account
    # without its owner doing anything.
    if user.password_hash is None:
        return

    # `auth.default_membership` refuses a user with no active membership,
    # so a working link would lead somewhere they still cannot go.
    membership = await session.scalar(
        sa.select(Membership).where(
            Membership.user_id == user.id,
            Membership.status == MembershipStatus.active,
        )
    )
    if membership is None:
        return

    # Decision D4: one live token per user. Without this, a user who clicks
    # the button four times has four valid links sitting in four separate
    # emails, and each extra copy is another chance for one to leak.
    await session.execute(
        sa.delete(PasswordReset).where(PasswordReset.user_id == user.id)
    )
    token = generate_token()
    session.add(
        PasswordReset(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=datetime.now(UTC)
            + timedelta(minutes=settings.password_reset_ttl_minutes),
        )
    )
    await session.commit()

    notifications.notify_password_reset(user.email, user.name, token)
