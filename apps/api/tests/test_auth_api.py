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
