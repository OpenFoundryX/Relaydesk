from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Unauthorized
from relaydesk.models import User
from relaydesk.security.passwords import hash_password
from relaydesk.services import auth


async def make_user(
    session: AsyncSession, password: str | None = "correct-horse"
) -> User:
    user = User(
        email="agent@relaydesk.dev",
        name="Sara Duval",
        monogram="SD",
        password_hash=hash_password(password) if password else None,
    )
    session.add(user)
    await session.commit()
    return user


async def test_authenticate_returns_user_for_correct_password(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)

    result = await auth.authenticate(
        db_session, "agent@relaydesk.dev", "correct-horse"
    )

    assert result.id == user.id
    assert result.failed_login_count == 0


async def test_authenticate_is_case_insensitive_on_email(
    db_session: AsyncSession,
) -> None:
    await make_user(db_session)

    result = await auth.authenticate(
        db_session, "AGENT@Relaydesk.dev", "correct-horse"
    )

    assert result.email == "agent@relaydesk.dev"


async def test_wrong_password_raises_and_increments_the_counter(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)

    with pytest.raises(Unauthorized):
        await auth.authenticate(db_session, "agent@relaydesk.dev", "wrong")

    await db_session.refresh(user)
    assert user.failed_login_count == 1


async def test_unknown_email_raises_the_same_error(db_session: AsyncSession) -> None:
    with pytest.raises(Unauthorized):
        await auth.authenticate(db_session, "nobody@relaydesk.dev", "whatever")


async def test_password_only_account_without_hash_cannot_log_in(
    db_session: AsyncSession,
) -> None:
    await make_user(db_session, password=None)

    with pytest.raises(Unauthorized):
        await auth.authenticate(db_session, "agent@relaydesk.dev", "anything")


async def test_lockout_after_max_attempts(db_session: AsyncSession) -> None:
    user = await make_user(db_session)

    for _ in range(5):
        with pytest.raises(Unauthorized):
            await auth.authenticate(db_session, "agent@relaydesk.dev", "wrong")

    await db_session.refresh(user)
    assert user.locked_until is not None

    # Even the correct password is refused while the lockout stands.
    with pytest.raises(Unauthorized):
        await auth.authenticate(db_session, "agent@relaydesk.dev", "correct-horse")


async def test_expired_lockout_allows_login_and_resets_counter(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    user.failed_login_count = 5
    user.locked_until = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()

    result = await auth.authenticate(
        db_session, "agent@relaydesk.dev", "correct-horse"
    )

    assert result.failed_login_count == 0
    assert result.locked_until is None
