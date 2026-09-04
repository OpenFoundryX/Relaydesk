import sqlalchemy as sa
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
    # Acceptance issues a session, matching POST /auth/login's shape.
    assert accepted.json()["token"]
    assert accepted.json()["expiresAt"]

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
    # Acceptance now signs you in, so the response is a session token rather
    # than the user. Resolve it to check it belongs to the existing account.
    session_headers = {"Authorization": f"Bearer {accepted.json()['token']}"}
    me = await client.get("/api/auth/me", headers=session_headers)
    assert me.status_code == 200
    assert me.json()["user"]["id"] == str(existing.id)

    # The existing password still works: accept must not have overwritten it.
    login = await client.post(
        "/api/auth/login",
        json={"email": "sara@relaydesk.dev", "password": "saras-own-password"},
    )
    assert login.status_code == 200


async def invite_and_accept(
    client: AsyncClient, headers: dict, email: str = "sara@relaydesk.dev"
) -> str:
    """Invite `email` as an Agent and accept it, returning the membership id."""
    invite_url = (
        await client.post(
            "/api/team/invites",
            headers=headers,
            json={"email": email, "role": "Agent"},
        )
    ).json()["inviteUrl"]
    token = invite_url.rsplit("/", 1)[-1]
    await client.post(
        f"/api/invites/{token}/accept",
        json={"name": "Sara Duval", "password": "another-horse"},
    )
    team = (await client.get("/api/team", headers=headers)).json()
    member = next(entry for entry in team if entry["email"] == email)
    return member["id"]


async def test_an_agent_cannot_change_a_members_role(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await sign_in(client, db_session, role=Role.agent)
    team = (await client.get("/api/team", headers=headers)).json()
    membership_id = team[0]["id"]

    response = await client.patch(
        f"/api/team/members/{membership_id}",
        headers=headers,
        json={"role": "Admin"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


async def test_an_agent_cannot_remove_a_member(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await sign_in(client, db_session, role=Role.agent)
    team = (await client.get("/api/team", headers=headers)).json()
    membership_id = team[0]["id"]

    response = await client.delete(
        f"/api/team/members/{membership_id}", headers=headers
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


async def test_admin_can_change_a_members_role(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await sign_in(client, db_session)
    membership_id = await invite_and_accept(client, headers)

    response = await client.patch(
        f"/api/team/members/{membership_id}",
        headers=headers,
        json={"role": "Admin"},
    )
    assert response.status_code == 204

    team = (await client.get("/api/team", headers=headers)).json()
    sara = next(entry for entry in team if entry["email"] == "sara@relaydesk.dev")
    assert sara["role"] == "Admin"


async def test_admin_can_remove_a_member(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await sign_in(client, db_session)
    membership_id = await invite_and_accept(client, headers)

    response = await client.delete(
        f"/api/team/members/{membership_id}", headers=headers
    )
    assert response.status_code == 204

    team = (await client.get("/api/team", headers=headers)).json()
    assert all(entry["email"] != "sara@relaydesk.dev" for entry in team)


async def test_member_routes_404_for_a_membership_in_another_workspace(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await sign_in(client, db_session)

    other_workspace = Workspace(name="Other Co", slug="other-co", monogram="OC")
    other_user = User(
        email="stranger@elsewhere.dev",
        name="A Stranger",
        monogram="AS",
        password_hash=hash_password("does-not-matter"),
    )
    db_session.add_all([other_workspace, other_user])
    await db_session.flush()
    other_membership = Membership(
        workspace_id=other_workspace.id,
        user_id=other_user.id,
        role=Role.admin,
        status=MembershipStatus.active,
    )
    db_session.add(other_membership)
    await db_session.commit()

    patch_response = await client.patch(
        f"/api/team/members/{other_membership.id}",
        headers=headers,
        json={"role": "Agent"},
    )
    delete_response = await client.delete(
        f"/api/team/members/{other_membership.id}", headers=headers
    )

    assert patch_response.status_code == 404
    assert delete_response.status_code == 404


async def test_demoting_the_last_admin_conflicts(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await sign_in(client, db_session)
    team = (await client.get("/api/team", headers=headers)).json()
    self_membership_id = team[0]["id"]

    response = await client.patch(
        f"/api/team/members/{self_membership_id}",
        headers=headers,
        json={"role": "Agent"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


async def test_removing_the_last_admin_conflicts(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await sign_in(client, db_session)
    team = (await client.get("/api/team", headers=headers)).json()
    self_membership_id = team[0]["id"]

    response = await client.delete(
        f"/api/team/members/{self_membership_id}", headers=headers
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


async def test_demoting_one_of_several_admins_succeeds(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Sanity check that the last-admin guard doesn't over-trigger."""
    headers = await sign_in(client, db_session)
    second_admin_id = await invite_and_accept(
        client, headers, email="second-admin@relaydesk.dev"
    )
    await client.patch(
        f"/api/team/members/{second_admin_id}",
        headers=headers,
        json={"role": "Admin"},
    )

    team = (await client.get("/api/team", headers=headers)).json()
    self_membership_id = next(
        entry["id"] for entry in team if entry["email"] == "nilesh@relaydesk.dev"
    )

    response = await client.patch(
        f"/api/team/members/{self_membership_id}",
        headers=headers,
        json={"role": "Agent"},
    )

    assert response.status_code == 204


async def test_accepting_does_not_set_a_password_on_a_passwordless_user(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The account-takeover chain, closed at its first link.

    A Google-only user has ``password_hash IS NULL``. Whoever holds the
    invite token picks the password in the accept payload, and with no
    mailer that is the admin who minted it — so writing that password onto
    a pre-existing account would hand them a working login as somebody
    else.
    """
    headers = await sign_in(client, db_session)
    google_only = User(
        email="sara@relaydesk.dev",
        name="Sara Duval",
        monogram="SD",
        password_hash=None,
    )
    db_session.add(google_only)
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
        json={"name": "Sara Duval", "password": "attacker-chosen"},
    )
    assert accepted.status_code == 200

    await db_session.refresh(google_only)
    assert google_only.password_hash is None

    login = await client.post(
        "/api/auth/login",
        json={"email": "sara@relaydesk.dev", "password": "attacker-chosen"},
    )
    assert login.status_code == 401


async def test_accepting_is_refused_when_the_user_already_has_a_membership(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The second link: a member of another workspace cannot be pulled in.

    ``services.auth.active_membership`` has no tiebreak, so a second active
    membership would make which workspace a login resolves to arbitrary.
    """
    headers = await sign_in(client, db_session)

    other_workspace = Workspace(name="Other Co", slug="other-co", monogram="OC")
    victim = User(
        email="victim@elsewhere.dev",
        name="Vic Tim",
        monogram="VT",
        password_hash=None,
    )
    db_session.add_all([other_workspace, victim])
    await db_session.flush()
    db_session.add(
        Membership(
            workspace_id=other_workspace.id,
            user_id=victim.id,
            role=Role.admin,
            status=MembershipStatus.active,
        )
    )
    await db_session.commit()

    invite_url = (
        await client.post(
            "/api/team/invites",
            headers=headers,
            json={"email": "victim@elsewhere.dev", "role": "Agent"},
        )
    ).json()["inviteUrl"]
    token = invite_url.rsplit("/", 1)[-1]

    accepted = await client.post(
        f"/api/invites/{token}/accept",
        json={"name": "Vic Tim", "password": "attacker-chosen"},
    )

    assert accepted.status_code == 409
    assert accepted.json()["error"]["code"] == "conflict"

    memberships = (
        await db_session.scalars(
            sa.select(Membership).where(Membership.user_id == victim.id)
        )
    ).all()
    assert len(memberships) == 1
    await db_session.refresh(victim)
    assert victim.password_hash is None


async def test_a_lowercase_role_is_rejected_rather_than_demoting(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """"admin" is the casing /auth/me returns, so it must not silently
    fall through to Agent."""
    headers = await sign_in(client, db_session)
    membership_id = await invite_and_accept(client, headers)
    await client.patch(
        f"/api/team/members/{membership_id}",
        headers=headers,
        json={"role": "Admin"},
    )

    response = await client.patch(
        f"/api/team/members/{membership_id}",
        headers=headers,
        json={"role": "admin"},
    )

    assert response.status_code == 422
    team = (await client.get("/api/team", headers=headers)).json()
    sara = next(entry for entry in team if entry["email"] == "sara@relaydesk.dev")
    assert sara["role"] == "Admin"


async def test_a_lowercase_invite_role_is_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await sign_in(client, db_session)

    response = await client.post(
        "/api/team/invites",
        headers=headers,
        json={"email": "sara@relaydesk.dev", "role": "agent"},
    )

    assert response.status_code == 422
