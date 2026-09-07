import uuid

import pytest
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Conflict, NotFound
from relaydesk.models import Membership, MembershipStatus, Role, User, Workspace
from relaydesk.security.passwords import hash_password
from relaydesk.services import channel_accounts, team, workspaces


async def sign_in_full(
    client: AsyncClient, session: AsyncSession, role: Role = Role.admin
) -> tuple[dict, Workspace, User]:
    """Like `sign_in`, but also hands back the workspace/user rows.

    Invites are reachable over HTTP now, but `services.team.create_invite`
    still needs a workspace id and an inviter id rather than a bearer token,
    so the tests below that mint one go through the service directly and
    only assert on the HTTP-visible result.
    """
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
    headers = {"Authorization": f"Bearer {response.json()['token']}"}
    return headers, workspace, user


async def sign_in(
    client: AsyncClient, session: AsyncSession, role: Role = Role.admin
) -> dict:
    headers, _workspace, _user = await sign_in_full(client, session, role)
    return headers


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


async def test_an_invited_member_shows_as_invited(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Invite creation over HTTP mails the token (see tests/test_invites.py);
    this test only cares about the roster, so it goes through the service
    directly — `list_members` (and the team page it backs) still surfaces a
    pending invite alongside active members."""
    headers, workspace, admin = await sign_in_full(client, db_session)
    await team.create_invite(
        db_session, workspace.id, "sara@relaydesk.dev", Role.agent, admin.id
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
    """Accepting mints a session, not a login, so this drives
    `services.team` directly to get the account created and only checks the
    HTTP-visible result: the accepted account can log in on its own."""
    _headers, workspace, admin = await sign_in_full(client, db_session)
    _invite, token = await team.create_invite(
        db_session, workspace.id, "sara@relaydesk.dev", Role.agent, admin.id
    )

    user, _membership = await team.accept_invite(
        db_session, token, "Sara Duval", "another-horse"
    )
    assert user.email == "sara@relaydesk.dev"

    login = await client.post(
        "/api/auth/login",
        json={"email": "sara@relaydesk.dev", "password": "another-horse"},
    )
    assert login.status_code == 200


async def test_an_invite_cannot_be_accepted_twice(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """`accept_invite` deletes the invite row rather than flagging it, so a
    replayed token is indistinguishable from one that never existed: both
    raise NotFound (see `tests/test_invites.py` for the HTTP-level version
    of this pin)."""
    _headers, workspace, admin = await sign_in_full(client, db_session)
    _invite, token = await team.create_invite(
        db_session, workspace.id, "sara@relaydesk.dev", Role.agent, admin.id
    )

    await team.accept_invite(db_session, token, "Sara Duval", "another-horse")
    with pytest.raises(NotFound):
        await team.accept_invite(db_session, token, "Sara Duval", "another-horse")


async def test_setup_tasks_reflect_real_state(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await sign_in(client, db_session)

    body = (await client.get("/api/workspace/setup-tasks", headers=headers)).json()

    by_id = {task["id"]: task for task in body}
    assert by_id["team"]["done"] is False  # only one member so far
    # This fixture builds `Workspace(...)` directly rather than going through
    # `create_workspace`, so it has no channel account -- which is why the
    # task is undone here. A workspace made the real way is covered below.
    assert by_id["channel"]["done"] is False


async def test_a_real_workspace_has_its_channel_task_already_done(
    db_session: AsyncSession,
) -> None:
    """`channel` was hardcoded False, left over from before the email slice
    landed. `create_workspace` gives every workspace an active
    ChannelAccount, so the task sat unticked for a workspace that already had
    a working ingest address, with nothing anyone could do to complete it --
    which also meant the checklist never reached done and the "Finish setup"
    card never went away."""
    workspace = await workspaces.create_workspace(
        db_session, name="Acme", slug="acme-setup-task", monogram="AC"
    )
    await db_session.commit()

    tasks = {t.id: t for t in await workspaces.setup_tasks(db_session, workspace.id)}

    assert tasks["channel"].done is True


async def test_deactivating_every_channel_reopens_the_channel_task(
    db_session: AsyncSession,
) -> None:
    """The count is of *active* accounts, so the task tracks whether mail can
    actually be received rather than whether a row was ever created."""
    workspace = await workspaces.create_workspace(
        db_session, name="Acme", slug="acme-setup-task-2", monogram="AC"
    )
    await db_session.commit()
    for account in await channel_accounts.list_for(db_session, workspace.id):
        account.active = False
    await db_session.commit()

    tasks = {t.id: t for t in await workspaces.setup_tasks(db_session, workspace.id)}

    assert tasks["channel"].done is False


async def test_inviting_the_same_pending_address_twice_conflicts(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _headers, workspace, admin = await sign_in_full(client, db_session)
    await team.create_invite(
        db_session, workspace.id, "sara@relaydesk.dev", Role.agent, admin.id
    )

    with pytest.raises(Conflict):
        await team.create_invite(
            db_session, workspace.id, "sara@relaydesk.dev", Role.agent, admin.id
        )


async def test_accepting_an_invite_adopts_an_unclaimed_account(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A row with no active membership is unclaimed, so the accepter's
    password wins.

    Keeping the old credentials here would be the bug, not the fix: there
    is no password-reset flow anywhere in the repo, so a re-invited
    ex-member whose typed password was discarded could never sign in, and
    an address squatted by an earlier admin would stay under his password
    forever.
    """
    _headers, workspace, admin = await sign_in_full(client, db_session)
    existing = User(
        email="sara@relaydesk.dev",
        name="S Duval",
        monogram="SD",
        password_hash=hash_password("saras-old-password"),
    )
    db_session.add(existing)
    await db_session.commit()

    _invite, token = await team.create_invite(
        db_session, workspace.id, "sara@relaydesk.dev", Role.agent, admin.id
    )

    accepted_user, _membership = await team.accept_invite(
        db_session, token, "Sara Duval", "saras-new-password"
    )

    # Adopted the existing row rather than creating a second one.
    assert accepted_user.id == existing.id
    assert accepted_user.name == "Sara Duval"

    new_password = await client.post(
        "/api/auth/login",
        json={"email": "sara@relaydesk.dev", "password": "saras-new-password"},
    )
    old_password = await client.post(
        "/api/auth/login",
        json={"email": "sara@relaydesk.dev", "password": "saras-old-password"},
    )

    assert new_password.status_code == 200
    assert old_password.status_code == 401


async def invite_and_accept(
    client: AsyncClient,
    session: AsyncSession,
    headers: dict,
    workspace_id: uuid.UUID,
    invited_by: uuid.UUID,
    email: str = "sara@relaydesk.dev",
) -> str:
    """Invite `email` as an Agent and accept it, returning the membership id.

    Accepting over HTTP now mints a session for the invitee rather than
    handing the caller anything usable here, so this drives `services.team`
    directly instead.
    """
    _invite, token = await team.create_invite(
        session, workspace_id, email, Role.agent, invited_by
    )
    await team.accept_invite(session, token, "Sara Duval", "another-horse")
    roster = (await client.get("/api/team", headers=headers)).json()
    member = next(entry for entry in roster if entry["email"] == email)
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
    headers, workspace, admin = await sign_in_full(client, db_session)
    membership_id = await invite_and_accept(
        client, db_session, headers, workspace.id, admin.id
    )

    response = await client.patch(
        f"/api/team/members/{membership_id}",
        headers=headers,
        json={"role": "Admin"},
    )
    assert response.status_code == 204

    roster = (await client.get("/api/team", headers=headers)).json()
    sara = next(entry for entry in roster if entry["email"] == "sara@relaydesk.dev")
    assert sara["role"] == "Admin"


async def test_admin_can_remove_a_member(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers, workspace, admin = await sign_in_full(client, db_session)
    membership_id = await invite_and_accept(
        client, db_session, headers, workspace.id, admin.id
    )

    response = await client.delete(
        f"/api/team/members/{membership_id}", headers=headers
    )
    assert response.status_code == 204

    roster = (await client.get("/api/team", headers=headers)).json()
    assert all(entry["email"] != "sara@relaydesk.dev" for entry in roster)


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
    headers, workspace, admin = await sign_in_full(client, db_session)
    second_admin_id = await invite_and_accept(
        client,
        db_session,
        headers,
        workspace.id,
        admin.id,
        email="second-admin@relaydesk.dev",
    )
    await client.patch(
        f"/api/team/members/{second_admin_id}",
        headers=headers,
        json={"role": "Admin"},
    )

    roster = (await client.get("/api/team", headers=headers)).json()
    self_membership_id = next(
        entry["id"] for entry in roster if entry["email"] == "nilesh@relaydesk.dev"
    )

    response = await client.patch(
        f"/api/team/members/{self_membership_id}",
        headers=headers,
        json={"role": "Agent"},
    )

    assert response.status_code == 204


async def test_accepting_is_refused_for_a_claimed_account(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The original takeover, pinned.

    A Google-only user (``password_hash IS NULL``) who is an active member
    of another workspace is *claimed*: acceptance must be refused outright,
    so the admin holding the token can neither set a password on the
    account nor give it a second membership. ``services.auth
    .active_membership`` has no tiebreak, so a second active membership
    would also make which workspace a login resolves to arbitrary.

    Accepting over HTTP mints a session that this test has no use for, so
    this drives `services.team` directly; the guard being pinned lives in
    the service, not the route.
    """
    _headers, workspace, admin = await sign_in_full(client, db_session)

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

    _invite, token = await team.create_invite(
        db_session, workspace.id, "victim@elsewhere.dev", Role.agent, admin.id
    )

    with pytest.raises(Conflict) as excinfo:
        await team.accept_invite(db_session, token, "Vic Tim", "attacker-chosen")
    assert excinfo.value.code == "conflict"

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
    headers, workspace, admin = await sign_in_full(client, db_session)
    membership_id = await invite_and_accept(
        client, db_session, headers, workspace.id, admin.id
    )
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
    roster = (await client.get("/api/team", headers=headers)).json()
    sara = next(entry for entry in roster if entry["email"] == "sara@relaydesk.dev")
    assert sara["role"] == "Admin"


async def test_a_lowercase_invite_role_is_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """"agent" is not a valid `RoleLabel`: FastAPI rejects the malformed
    body before the handler — and its email send — ever runs."""
    headers = await sign_in(client, db_session)

    response = await client.post(
        "/api/team/invites",
        headers=headers,
        json={"email": "sara@relaydesk.dev", "role": "agent"},
    )

    assert response.status_code == 422


async def test_a_squatted_then_released_address_is_reclaimed_by_the_real_invitee(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The full squat-release-adopt chain, end to end.

    Over HTTP, the token this scenario depends on the squatter holding is
    mailed to the invited address and never returned to the inviter — so
    the attack is closed at that layer. This test pins the guard one layer
    down: `services.team.accept_invite` itself must still refuse to *link*
    to a pre-existing-but-unclaimed row, so a squatter who somehow does
    obtain a token (a compromised mailbox, a misconfigured mailer) can't
    turn it into a silent handover when the real owner later accepts.
    Deleting his own membership leaves the address pre-existing but
    unclaimed; if acceptance merely linked to that row rather than adopting
    it, the real person's typed password would be discarded and the
    squatter would keep their account in the inviting workspace.

    This is a regression pin kept intact from the previous slice: the
    invite creation/acceptance calls go through `services.team` directly,
    since accepting over HTTP now mints a session rather than anything this
    test needs. Everything the scenario depends on — deleting a membership,
    logging in — is still real HTTP against the running app.
    """
    squatter_headers, squatter_workspace, squatter_admin = await sign_in_full(
        client, db_session
    )

    # 1. Mint an invite for an address he does not control, and take it.
    _invite, squat_token = await team.create_invite(
        db_session,
        squatter_workspace.id,
        "target@outside.dev",
        Role.agent,
        squatter_admin.id,
    )
    squatter, _membership = await team.accept_invite(
        db_session, squat_token, "Not The Owner", "squatter-password"
    )
    assert squatter.email == "target@outside.dev"

    # 2. Release it, so the row survives with no active membership.
    roster = (await client.get("/api/team", headers=squatter_headers)).json()
    squatted_id = next(
        entry["id"] for entry in roster if entry["email"] == "target@outside.dev"
    )
    released = await client.delete(
        f"/api/team/members/{squatted_id}", headers=squatter_headers
    )
    assert released.status_code == 204

    # 3. A different workspace invites the same address, and the real
    #    person accepts with a password of their own choosing.
    acme = Workspace(name="Acme", slug="acme", monogram="AC")
    ada = User(
        email="ada@acme.dev",
        name="Ada Admin",
        monogram="AA",
        password_hash=hash_password("relaydesk"),
    )
    db_session.add_all([acme, ada])
    await db_session.flush()
    db_session.add(
        Membership(
            workspace_id=acme.id,
            user_id=ada.id,
            role=Role.admin,
            status=MembershipStatus.active,
        )
    )
    await db_session.commit()

    _acme_invite, acme_token = await team.create_invite(
        db_session, acme.id, "target@outside.dev", Role.agent, ada.id
    )
    real_owner, _membership = await team.accept_invite(
        db_session, acme_token, "Real Owner", "real-owner-password"
    )
    assert real_owner.id == squatter.id  # same row, reclaimed

    # 4. The real person holds the account; the squatter is locked out.
    real = await client.post(
        "/api/auth/login",
        json={"email": "target@outside.dev", "password": "real-owner-password"},
    )
    squatter_login = await client.post(
        "/api/auth/login",
        json={"email": "target@outside.dev", "password": "squatter-password"},
    )

    assert real.status_code == 200
    assert squatter_login.status_code == 401
