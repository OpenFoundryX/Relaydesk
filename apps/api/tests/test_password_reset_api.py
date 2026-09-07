import sqlalchemy as sa

from relaydesk.models import RateLimitHit
from relaydesk.security.passwords import verify_password
from tests.factories import make_member, make_workspace, sign_in


async def test_every_address_gets_the_same_answer(db_session, client, outbox) -> None:
    """The whole enumeration defense: a real address, an unknown one and a
    Google-only one must be indistinguishable from outside."""
    workspace = await make_workspace(db_session)
    await make_member(db_session, workspace, email="nilesh@example.com")
    google_only = await make_member(
        db_session, workspace, email="sara@example.com", name="Sara Vidal"
    )
    google_only.password_hash = None
    await db_session.commit()

    answers = []
    for address in ("nilesh@example.com", "nobody@example.com", "sara@example.com"):
        response = await client.post(
            "/api/auth/password-reset", json={"email": address}
        )
        answers.append((response.status_code, response.text))

    assert answers[0] == answers[1] == answers[2]
    assert answers[0][0] == 202
    # Only the real password account was mailed.
    assert len(outbox) == 1
    assert outbox[0]["to"] == "nilesh@example.com"


async def test_the_response_never_carries_the_token(db_session, client, outbox) -> None:
    workspace = await make_workspace(db_session)
    await make_member(db_session, workspace, email="nilesh@example.com")
    await db_session.commit()

    response = await client.post(
        "/api/auth/password-reset", json={"email": "nilesh@example.com"}
    )

    assert response.status_code == 202
    assert response.text.strip() == ""
    token = outbox[0]["text"].split("/reset-password#")[1].split()[0]
    assert token not in response.text


async def test_a_rate_limited_request_still_answers_202(
    db_session, client, outbox
) -> None:
    """A 429 is itself a signal, and one an attacker can provoke against a
    chosen address."""
    workspace = await make_workspace(db_session)
    await make_member(db_session, workspace, email="nilesh@example.com")
    await db_session.commit()

    statuses = []
    for _ in range(5):
        response = await client.post(
            "/api/auth/password-reset", json={"email": "nilesh@example.com"}
        )
        statuses.append(response.status_code)

    assert statuses == [202, 202, 202, 202, 202]
    assert len(outbox) == 3


async def test_the_limiter_keys_on_the_forwarded_client_not_the_peer(
    db_session, client, outbox, monkeypatch
) -> None:
    """Behind the web container every request arrives from one peer. Keyed
    on the peer, the whole deployment would share a single five-per-hour
    bucket. This is the regression test for using api.deps.client_ip here."""
    from relaydesk.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "trusted_proxy_ips", "127.0.0.1")

    workspace = await make_workspace(db_session)
    for index in range(2):
        await make_member(db_session, workspace, email=f"user{index}@example.com")
    await db_session.commit()

    await client.post(
        "/api/auth/password-reset",
        json={"email": "user0@example.com"},
        headers={"X-Forwarded-For": "203.0.113.9"},
    )
    await client.post(
        "/api/auth/password-reset",
        json={"email": "user1@example.com"},
        headers={"X-Forwarded-For": "198.51.100.4"},
    )

    keys = (
        await db_session.scalars(
            sa.select(RateLimitHit.key).where(
                RateLimitHit.bucket == "password_reset_ip"
            )
        )
    ).all()
    assert set(keys) == {"203.0.113.9", "198.51.100.4"}


async def test_confirming_through_the_api_changes_the_password(
    db_session, client, outbox
) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace, email="nilesh@example.com")
    await db_session.commit()

    await client.post("/api/auth/password-reset", json={"email": "nilesh@example.com"})
    token = outbox[0]["text"].split("/reset-password#")[1].split()[0]

    response = await client.post(
        "/api/auth/password-reset/confirm",
        json={"token": token, "password": "a-brand-new-password"},
    )

    assert response.status_code == 204
    await db_session.refresh(user)
    assert verify_password("a-brand-new-password", user.password_hash)

    headers = await sign_in(
        client, db_session, "nilesh@example.com", "a-brand-new-password"
    )
    assert "Authorization" in headers


async def test_a_short_password_is_refused(db_session, client, outbox) -> None:
    workspace = await make_workspace(db_session)
    await make_member(db_session, workspace, email="nilesh@example.com")
    await db_session.commit()
    await client.post("/api/auth/password-reset", json={"email": "nilesh@example.com"})
    token = outbox[0]["text"].split("/reset-password#")[1].split()[0]

    response = await client.post(
        "/api/auth/password-reset/confirm",
        json={"token": token, "password": "short"},
    )

    assert response.status_code == 422


async def test_an_unknown_token_is_a_404(db_session, client) -> None:
    response = await client.post(
        "/api/auth/password-reset/confirm",
        json={"token": "not-a-real-token", "password": "a-brand-new-password"},
    )

    assert response.status_code == 404
