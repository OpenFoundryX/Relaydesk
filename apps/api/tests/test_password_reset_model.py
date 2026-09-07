from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from relaydesk.config import get_settings
from relaydesk.models import PasswordReset, User
from relaydesk.security.tokens import generate_token, hash_token
from tests.factories import make_member, make_workspace


async def test_a_reset_row_round_trips(db_session) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace, email="nilesh@example.com")
    token = generate_token()

    row = PasswordReset(
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(row)
    await db_session.flush()

    found = await db_session.scalar(
        sa.select(PasswordReset).where(PasswordReset.token_hash == hash_token(token))
    )
    assert found is not None
    assert found.user_id == user.id
    # The plaintext is not what was stored -- only its digest.
    assert found.token_hash != token


async def test_two_rows_cannot_share_a_token_hash(db_session) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace, email="nilesh@example.com")
    digest = hash_token(generate_token())

    db_session.add(
        PasswordReset(
            user_id=user.id,
            token_hash=digest,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    await db_session.flush()

    db_session.add(
        PasswordReset(
            user_id=user.id,
            token_hash=digest,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_deleting_the_user_takes_the_reset_with_it(db_session) -> None:
    """A live capability must never outlive the account it unlocks."""
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace, email="nilesh@example.com")
    db_session.add(
        PasswordReset(
            user_id=user.id,
            token_hash=hash_token(generate_token()),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    await db_session.flush()

    await db_session.execute(sa.delete(User).where(User.id == user.id))
    await db_session.flush()

    remaining = await db_session.scalar(
        sa.select(sa.func.count()).select_from(PasswordReset)
    )
    assert remaining == 0


def test_the_reset_settings_have_defaults() -> None:
    settings = get_settings()
    assert settings.password_reset_ttl_minutes == 60
    assert settings.password_reset_ip_hourly_cap == 5
    assert settings.password_reset_email_hourly_cap == 3
