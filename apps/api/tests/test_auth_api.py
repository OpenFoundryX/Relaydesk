from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models import (
    Membership,
    MembershipStatus,
    Role,
    Session,
    User,
    Workspace,
)
from relaydesk.security.passwords import hash_password
from relaydesk.security.tokens import generate_token, hash_token


async def seed_member(session: AsyncSession) -> tuple[Workspace, User]:
    workspace = Workspace(name="Chronon", slug="chronon", monogram="CH")
    user = User(
        email="nilesh@relaydesk.dev",
        name="Nilesh Pant",
        monogram="NP",
        password_hash=hash_password("correct-horse"),
    )
    session.add_all([workspace, user])
    await session.flush()
    session.add(
        Membership(
            workspace_id=workspace.id,
            user_id=user.id,
            role=Role.admin,
            status=MembershipStatus.active,
        )
    )
    await session.commit()
    return workspace, user


async def test_login_returns_a_token(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_member(db_session)

    response = await client.post(
        "/api/auth/login",
        json={"email": "nilesh@relaydesk.dev", "password": "correct-horse"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token"]
    assert body["expiresAt"]


async def test_login_stores_only_the_token_hash(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_member(db_session)

    response = await client.post(
        "/api/auth/login",
        json={"email": "nilesh@relaydesk.dev", "password": "correct-horse"},
    )
    token = response.json()["token"]

    stored = await db_session.scalars(sa.select(Session))
    hashes = [row.token_hash for row in stored]
    assert hashes
    assert token not in hashes


async def test_login_with_a_bad_password_returns_the_error_envelope(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_member(db_session)

    response = await client.post(
        "/api/auth/login",
        json={"email": "nilesh@relaydesk.dev", "password": "nope"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "error": {"code": "unauthorized", "message": "Email or password is incorrect."}
    }


async def test_me_returns_user_workspace_and_membership(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_member(db_session)
    login = await client.post(
        "/api/auth/login",
        json={"email": "nilesh@relaydesk.dev", "password": "correct-horse"},
    )
    token = login.json()["token"]

    response = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["name"] == "Nilesh Pant"
    assert body["user"]["monogram"] == "NP"
    assert body["workspace"]["name"] == "Chronon"
    assert body["membership"]["role"] == "admin"


async def test_renaming_yourself_recomputes_the_monogram(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Without this, a rename left the monogram showing the old initials --
    team.monogram_for is what every other name-setting path (accept_invite,
    seeding) already derives it from."""
    await seed_member(db_session)
    login = await client.post(
        "/api/auth/login",
        json={"email": "nilesh@relaydesk.dev", "password": "correct-horse"},
    )
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.patch(
        "/api/auth/me", json={"name": "Grace Whitfield"}, headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["name"] == "Grace Whitfield"
    assert body["user"]["monogram"] == "GW"


async def test_renaming_yourself_past_the_column_width_is_a_422_not_a_500(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """User.name is String(120); without a bound on MePatch.name this
    reached the database and raised StringDataRightTruncation instead of a
    validation error."""
    await seed_member(db_session)
    login = await client.post(
        "/api/auth/login",
        json={"email": "nilesh@relaydesk.dev", "password": "correct-horse"},
    )
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.patch(
        "/api/auth/me", json={"name": "A" * 121}, headers=headers
    )

    assert response.status_code == 422


async def test_me_without_a_token_is_unauthorized(client: AsyncClient) -> None:
    response = await client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_logout_invalidates_the_token(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_member(db_session)
    login = await client.post(
        "/api/auth/login",
        json={"email": "nilesh@relaydesk.dev", "password": "correct-horse"},
    )
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    assert (await client.post("/api/auth/logout", headers=headers)).status_code == 204
    assert (await client.get("/api/auth/me", headers=headers)).status_code == 401


async def test_a_user_without_an_active_membership_cannot_log_in(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user = User(
        email="orphan@relaydesk.dev",
        name="Orphan",
        monogram="OR",
        password_hash=hash_password("correct-horse"),
    )
    db_session.add(user)
    await db_session.commit()

    response = await client.post(
        "/api/auth/login",
        json={"email": "orphan@relaydesk.dev", "password": "correct-horse"},
    )

    assert response.status_code == 401


async def test_an_expired_session_is_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    workspace, user = await seed_member(db_session)
    token = generate_token()
    now = datetime.now(UTC)
    db_session.add(
        Session(
            user_id=user.id,
            workspace_id=workspace.id,
            token_hash=hash_token(token),
            expires_at=now - timedelta(seconds=1),
            last_seen_at=now,
        )
    )
    await db_session.commit()

    response = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401


async def test_malformed_login_body_returns_the_error_envelope(
    client: AsyncClient,
) -> None:
    response = await client.post("/api/auth/login", json={"email": "not-an-email"})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "invalid"
    assert body["error"]["message"]


async def test_a_non_bearer_auth_scheme_is_unauthorized(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_member(db_session)

    response = await client.get(
        "/api/auth/me", headers={"Authorization": "Token abc"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_an_empty_bearer_token_is_unauthorized(client: AsyncClient) -> None:
    response = await client.get(
        "/api/auth/me", headers={"Authorization": "Bearer "}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_login_clamps_an_oversized_user_agent(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_member(db_session)

    response = await client.post(
        "/api/auth/login",
        json={"email": "nilesh@relaydesk.dev", "password": "correct-horse"},
        headers={"User-Agent": "x" * 500},
    )

    assert response.status_code == 200
    row = await db_session.scalar(sa.select(Session))
    assert row is not None
    assert len(row.user_agent) == 400
