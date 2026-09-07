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
from relaydesk.errors import NotFound
from relaydesk.models.membership import Membership, MembershipStatus
from relaydesk.models.password_reset import PasswordReset
from relaydesk.models.session import Session
from relaydesk.models.user import User
from relaydesk.security.passwords import hash_password
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


INVALID_LINK = "This reset link is not valid."


async def confirm(session: AsyncSession, token: str, password: str) -> None:
    """Spend a reset token.

    A missing row and an expired one raise the same message, per decision
    D3: a consumed row is deleted, so there is nothing left to distinguish
    a replay from a token that never existed, and no reason to confirm to a
    caller that a given token used to be valid.
    """
    row = await session.scalar(
        sa.select(PasswordReset).where(PasswordReset.token_hash == hash_token(token))
    )
    if row is None or row.expires_at <= datetime.now(UTC):
        raise NotFound(INVALID_LINK)

    user = await session.get(User, row.user_id)
    if user is None:
        raise NotFound(INVALID_LINK)

    user.password_hash = hash_password(password)

    # Forgetting a password and guessing at one are the same activity from
    # `authenticate`'s point of view, so the user most likely to arrive
    # here is disproportionately likely to have tripped the five-attempt
    # lockout on the way. Leaving it set produces the worst outcome
    # available: a correct, just-chosen password refused with the same
    # BAD_CREDENTIALS message for the next fifteen minutes.
    user.failed_login_count = 0
    user.locked_until = None

    await session.delete(row)

    # Decision D5. This logs the user out of devices they are using
    # happily, which is a real cost on a flow reached through simple
    # forgetfulness. It is paid because the server cannot tell that case
    # from a compromise, and the two are asymmetric: forgetfulness costs a
    # few sign-ins with a password the user just chose, whereas not
    # revoking lets an attacker's session survive the exact action taken to
    # evict them -- for up to `session_ttl_days`, which defaults to 30.
    await session.execute(sa.delete(Session).where(Session.user_id == user.id))

    await session.commit()
