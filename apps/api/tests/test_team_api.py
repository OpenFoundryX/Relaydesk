from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models import Membership, MembershipStatus, Role, User, Workspace
from relaydesk.security.passwords import hash_password


async def sign_in(
    client: AsyncClient, session: AsyncSession, role: Role = Role.admin
) -> dict:
    workspace = Workspace(name="Chronon", slug="chronon", monogram="CH")
    user = User(
        email="nilesh@relaydesk.dev",
        name="Nilesh Pant",
        monogram="NP",
        password_hash=hash_password("relaydesk"),
    )
    session.add_all([workspace, user])
    await session.flush()
    session.add(
        Membership(
            workspace_id=workspace.id,
            user_id=user.id,
            role=role,
            status=MembershipStatus.active,
        )
    )
    await session.commit()

    response = await client.post(
        "/api/auth/login",
        json={"email": "nilesh@relaydesk.dev", "password": "relaydesk"},
    )
    return {"Authorization": f"Bearer {response.json()['token']}"}


async def test_team_lists_the_signed_in_member(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await sign_in(client, db_session)

    response = await client.get("/api/team", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "Nilesh Pant"
    assert body[0]["role"] == "Admin"
    assert body[0]["status"] == "active"


async def test_admin_can_create_an_invite(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await sign_in(client, db_session)

    response = await client.post(
        "/api/team/invites",
        headers=headers,
        json={"email": "sara@relaydesk.dev", "role": "Agent"},
    )

    assert response.status_code == 201
    assert "/invite/" in response.json()["inviteUrl"]


async def test_an_invited_member_shows_as_invited(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await sign_in(client, db_session)
    await client.post(
        "/api/team/invites",
        headers=headers,
        json={"email": "sara@relaydesk.dev", "role": "Agent"},
    )

    body = (await client.get("/api/team", headers=headers)).json()

    invited = [entry for entry in body if entry["email"] == "sara@relaydesk.dev"]
    assert invited and invited[0]["status"] == "invited"


async def test_an_agent_cannot_create_an_invite(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await sign_in(client, db_session, role=Role.agent)

    response = await client.post(
        "/api/team/invites",
        headers=headers,
        json={"email": "sara@relaydesk.dev", "role": "Agent"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


async def test_accepting_an_invite_creates_a_working_login(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await sign_in(client, db_session)
    invite_url = (
        await client.post(
            "/api/team/invites",
            headers=headers,
            json={"email": "sara@relaydesk.dev", "role": "Agent"},
        )
    ).json()["inviteUrl"]
    token = invite_url.rsplit("/", 1)[-1]

    accepted = await client.post(
        f"/api/invites/{token}/accept",
        json={"name": "Sara Duval", "password": "another-horse"},
    )
    assert accepted.status_code == 200

    login = await client.post(
        "/api/auth/login",
        json={"email": "sara@relaydesk.dev", "password": "another-horse"},
    )
    assert login.status_code == 200


async def test_an_invite_cannot_be_accepted_twice(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await sign_in(client, db_session)
    invite_url = (
        await client.post(
            "/api/team/invites",
            headers=headers,
            json={"email": "sara@relaydesk.dev", "role": "Agent"},
        )
    ).json()["inviteUrl"]
    token = invite_url.rsplit("/", 1)[-1]
    payload = {"name": "Sara Duval", "password": "another-horse"}

    assert (
        await client.post(f"/api/invites/{token}/accept", json=payload)
    ).status_code == 200
    second = await client.post(f"/api/invites/{token}/accept", json=payload)

    assert second.status_code == 409


async def test_setup_tasks_reflect_real_state(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await sign_in(client, db_session)

    body = (await client.get("/api/workspace/setup-tasks", headers=headers)).json()

    by_id = {task["id"]: task for task in body}
    assert by_id["team"]["done"] is False  # only one member so far
    assert by_id["channel"]["done"] is False  # no channels until slice 2


async def test_inviting_the_same_pending_address_twice_conflicts(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await sign_in(client, db_session)
    await client.post(
        "/api/team/invites",
        headers=headers,
        json={"email": "sara@relaydesk.dev", "role": "Agent"},
    )

    second = await client.post(
        "/api/team/invites",
        headers=headers,
        json={"email": "sara@relaydesk.dev", "role": "Agent"},
    )

    assert second.status_code == 409
    body = (await client.get("/api/team", headers=headers)).json()
    matches = [entry for entry in body if entry["email"] == "sara@relaydesk.dev"]
    assert len(matches) == 1


async def test_accepting_an_invite_for_an_existing_user_links_it(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await sign_in(client, db_session)
    existing = User(
        email="sara@relaydesk.dev",
        name="Sara Duval",
        monogram="SD",
        password_hash=hash_password("saras-own-password"),
    )
    db_session.add(existing)
    await db_session.commit()

    invite_url = (
        await client.post(
            "/api/team/invites",
            headers=headers,
            json={"email": "sara@relaydesk.dev", "role": "Agent"},
        )
    ).json()["inviteUrl"]
    token = invite_url.rsplit("/", 1)[-1]

    accepted = await client.post(
        f"/api/invites/{token}/accept",
        json={"name": "Sara Duval", "password": "a-different-password"},
    )

    assert accepted.status_code == 200
    assert accepted.json()["id"] == str(existing.id)

    # The existing password still works: accept must not have overwritten it.
    login = await client.post(
        "/api/auth/login",
        json={"email": "sara@relaydesk.dev", "password": "saras-own-password"},
    )
    assert login.status_code == 200
