from datetime import UTC, datetime, timedelta

import sqlalchemy as sa

from relaydesk.models import PasswordReset, User
from relaydesk.security.tokens import hash_token
from relaydesk.services import password_reset
from tests.factories import make_member, make_workspace

IP = "203.0.113.9"


async def _member(db_session, **kwargs) -> User:
    workspace = await make_workspace(db_session)
    return await make_member(db_session, workspace, **kwargs)


async def test_a_request_mails_a_token_that_matches_the_stored_hash(
    db_session, outbox
) -> None:
    user = await _member(db_session, email="nilesh@example.com")
    await db_session.commit()

    await password_reset.request(db_session, "nilesh@example.com", IP)

    assert len(outbox) == 1
    assert outbox[0]["to"] == "nilesh@example.com"
    assert "/reset-password#" in outbox[0]["text"]

    token = outbox[0]["text"].split("/reset-password#")[1].split()[0]
    row = await db_session.scalar(
        sa.select(PasswordReset).where(PasswordReset.token_hash == hash_token(token))
    )
    assert row is not None
    assert row.user_id == user.id
    # The plaintext never lands in the row.
    assert token not in row.token_hash


async def test_an_unknown_address_sends_nothing(db_session, outbox) -> None:
    await _member(db_session, email="nilesh@example.com")
    await db_session.commit()

    await password_reset.request(db_session, "nobody@example.com", IP)

    assert outbox == []
    assert await db_session.scalar(
        sa.select(sa.func.count()).select_from(PasswordReset)
    ) == 0


async def test_a_google_only_account_gets_no_mail(db_session, outbox) -> None:
    """Decision D1. Such an account has never had a password and its root of
    trust is Google; a reset would mint one from mailbox control alone. The
    caller cannot tell -- the route answers 202 either way (Task 5)."""
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace, email="sara@example.com")
    user.password_hash = None
    await db_session.commit()

    await password_reset.request(db_session, "sara@example.com", IP)

    assert outbox == []


async def test_a_user_with_no_active_membership_gets_no_mail(
    db_session, outbox
) -> None:
    """auth.default_membership refuses them, so a working link would lead
    somewhere they still cannot go."""
    user = User(
        email="orphan@example.com",
        name="Orphan",
        monogram="OR",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$notarealhash",
    )
    db_session.add(user)
    await db_session.commit()

    await password_reset.request(db_session, "orphan@example.com", IP)

    assert outbox == []


async def test_a_second_request_invalidates_the_first_token(
    db_session, outbox
) -> None:
    """Decision D4. Four clicks must not leave four live links in four
    separate emails."""
    await _member(db_session, email="nilesh@example.com")
    await db_session.commit()

    await password_reset.request(db_session, "nilesh@example.com", IP)
    await password_reset.request(db_session, "nilesh@example.com", IP)

    assert len(outbox) == 2
    rows = (await db_session.scalars(sa.select(PasswordReset))).all()
    assert len(rows) == 1

    second = outbox[1]["text"].split("/reset-password#")[1].split()[0]
    assert rows[0].token_hash == hash_token(second)


async def test_the_row_expires_within_the_configured_ttl(db_session, outbox) -> None:
    await _member(db_session, email="nilesh@example.com")
    await db_session.commit()

    await password_reset.request(db_session, "nilesh@example.com", IP)

    row = await db_session.scalar(sa.select(PasswordReset))
    assert row is not None
    assert row.expires_at <= datetime.now(UTC) + timedelta(minutes=61)
    assert row.expires_at > datetime.now(UTC) + timedelta(minutes=55)


async def test_the_address_cap_stops_the_fourth_request(db_session, outbox) -> None:
    await _member(db_session, email="nilesh@example.com")
    await db_session.commit()

    for _ in range(4):
        await password_reset.request(db_session, "nilesh@example.com", IP)

    assert len(outbox) == 3


async def test_the_ip_cap_covers_several_addresses(db_session, outbox) -> None:
    """The address cap alone would let one host walk a list of addresses,
    three mails each."""
    workspace = await make_workspace(db_session)
    for index in range(6):
        await make_member(db_session, workspace, email=f"user{index}@example.com")
    await db_session.commit()

    for index in range(6):
        await password_reset.request(db_session, f"user{index}@example.com", IP)

    assert len(outbox) == 5


async def test_two_ip_buckets_do_not_share_an_allowance(db_session, outbox) -> None:
    """The regression test for keying on the wrong client_ip helper: behind
    the web container every caller shares one peer address, so a limiter
    keyed on the peer gives the whole deployment five resets an hour."""
    workspace = await make_workspace(db_session)
    for index in range(12):
        await make_member(db_session, workspace, email=f"user{index}@example.com")
    await db_session.commit()

    for index in range(6):
        await password_reset.request(db_session, f"user{index}@example.com", IP)
    for index in range(6, 12):
        await password_reset.request(
            db_session, f"user{index}@example.com", "198.51.100.4"
        )

    assert len(outbox) == 10
