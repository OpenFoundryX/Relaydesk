from datetime import UTC, datetime, timedelta

from relaydesk.models import Membership, MembershipStatus, Role, User
from relaydesk.security.passwords import hash_password
from relaydesk.services import team
from tests.factories import make_member, make_workspace, sign_in


async def test_creating_an_invite_returns_no_token(db_session, client, outbox) -> None:
    """The whole security property of this feature: the token reaches the
    invited address and nobody else. An inviteUrl in the response would hand
    it straight back to whoever made the request."""
    workspace = await make_workspace(db_session)
    admin = await make_member(
        db_session, workspace, email="nilesh@example.com", role=Role.admin
    )
    await db_session.commit()
    headers = await sign_in(client, db_session, admin.email)

    response = await client.post(
        "/api/team/invites",
        json={"email": "sara@example.com", "role": "Agent"},
        headers=headers,
    )

    assert response.status_code == 202
    assert "inviteUrl" not in response.text
    assert "token" not in response.text.lower()

    assert len(outbox) == 1
    assert outbox[0]["to"] == "sara@example.com"
    # A fragment, not a path segment: everything after "#" is never sent to
    # any server, so it never reaches an access log (see
    # notifications.notify_invite). "/invites/<token>" as a path was the
    # mistake this replaces.
    assert "/invites#" in outbox[0]["text"]
    assert "/invites/" not in outbox[0]["text"]


async def test_an_agent_cannot_invite(db_session, client, outbox) -> None:
    workspace = await make_workspace(db_session)
    agent = await make_member(
        db_session, workspace, email="sara@example.com", role=Role.agent
    )
    await db_session.commit()
    headers = await sign_in(client, db_session, agent.email)

    response = await client.post(
        "/api/team/invites",
        json={"email": "new@example.com", "role": "Agent"},
        headers=headers,
    )

    assert response.status_code == 403
    assert outbox == []


async def test_an_invite_can_only_be_accepted_once(db_session, client, outbox) -> None:
    """Acceptance deletes the invite row rather than marking it accepted, so
    a replayed token is indistinguishable from one that never existed — both
    are 404. There is nothing left in the table to tell them apart by, which
    is the point: a token that leaks from a mail archive after being used is
    inert, not merely rejected by a check."""
    workspace = await make_workspace(db_session)
    admin = await make_member(
        db_session, workspace, email="nilesh@example.com", role=Role.admin
    )
    _invite, raw_token = await team.create_invite(
        db_session, workspace.id, "sara@example.com", Role.agent, admin.id
    )
    await db_session.commit()

    first = await client.post(
        "/api/invites/accept",
        json={
            "token": raw_token,
            "name": "Sara",
            "password": "correct horse battery staple",
        },
    )
    assert first.status_code == 200

    second = await client.post(
        "/api/invites/accept",
        json={
            "token": raw_token,
            "name": "Sara",
            "password": "correct horse battery staple",
        },
    )
    assert second.status_code == 404


async def test_an_expired_invite_cannot_be_accepted(db_session, client) -> None:
    workspace = await make_workspace(db_session)
    admin = await make_member(
        db_session, workspace, email="nilesh@example.com", role=Role.admin
    )
    invite, raw_token = await team.create_invite(
        db_session, workspace.id, "sara@example.com", Role.agent, admin.id
    )
    invite.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()

    response = await client.post(
        "/api/invites/accept",
        json={
            "token": raw_token,
            "name": "Sara",
            "password": "correct horse battery staple",
        },
    )

    assert response.status_code == 404


async def test_previewing_an_invite_does_not_consume_it(db_session, client) -> None:
    workspace = await make_workspace(db_session, slug="acme")
    admin = await make_member(
        db_session, workspace, email="nilesh@example.com", role=Role.admin
    )
    _invite, raw_token = await team.create_invite(
        db_session, workspace.id, "sara@example.com", Role.agent, admin.id
    )
    await db_session.commit()

    preview = await client.post("/api/invites/preview", json={"token": raw_token})

    assert preview.status_code == 200
    assert preview.json() == {
        "workspaceName": "Acme",
        "email": "sara@example.com",
        "role": "Agent",
    }

    # Previewing must not be single-use: the real accept still works.
    accept = await client.post(
        "/api/invites/accept",
        json={
            "token": raw_token,
            "name": "Sara",
            "password": "correct horse battery staple",
        },
    )
    assert accept.status_code == 200


async def test_accepting_lands_in_the_inviting_workspace(
    db_session, client, outbox
) -> None:
    """Task 5 pins the session to a workspace; this proves acceptance mints
    it for the workspace that issued the invite — not just for the single
    workspace a naive fixture would leave as the only candidate.

    A decoy workspace/user holds an active membership stamped a full day in
    the past — deliberately older than anything else in this transaction,
    including the membership `accept_invite` is about to create (whose
    `created_at` comes from Postgres's ``now()``, which is fixed for the
    whole transaction and so reads as "now", not "in the past"). If the
    session's workspace were ever resolved by picking some membership
    without pinning to the exact row `accept_invite` just created — e.g. an
    unscoped "the oldest active membership in the table" instead of "the
    one this acceptance made" — this decoy is what would get picked
    instead, and the assertions below would catch it (see the revert-proof
    in the Task 6 fix-round report).
    """
    decoy_workspace = await make_workspace(db_session, slug="decoy")
    decoy_admin = User(
        email="decoy-admin@example.com",
        name="Decoy Admin",
        monogram="DA",
        password_hash=hash_password("relaydesk"),
    )
    db_session.add(decoy_admin)
    await db_session.flush()
    db_session.add(
        Membership(
            workspace_id=decoy_workspace.id,
            user_id=decoy_admin.id,
            role=Role.admin,
            status=MembershipStatus.active,
            created_at=datetime.now(UTC) - timedelta(days=1),
        )
    )
    await db_session.commit()

    workspace = await make_workspace(db_session, slug="acme")
    admin = await make_member(
        db_session, workspace, email="nilesh@example.com", role=Role.admin
    )
    _invite, raw_token = await team.create_invite(
        db_session, workspace.id, "sara@example.com", Role.agent, admin.id
    )
    await db_session.commit()

    accept = await client.post(
        "/api/invites/accept",
        json={
            "token": raw_token,
            "name": "Sara",
            "password": "correct horse battery staple",
        },
    )
    session_token = accept.json()["token"]

    me = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {session_token}"}
    )

    assert me.json()["workspace"]["id"] == str(workspace.id)
    assert me.json()["workspace"]["id"] != str(decoy_workspace.id)


async def test_admin_revokes_an_invite(db_session, client) -> None:
    workspace = await make_workspace(db_session)
    admin = await make_member(
        db_session, workspace, email="nilesh@example.com", role=Role.admin
    )
    invite, _token = await team.create_invite(
        db_session, workspace.id, "sara@example.com", Role.agent, admin.id
    )
    await db_session.commit()
    headers = await sign_in(client, db_session, admin.email)

    response = await client.delete(
        f"/api/team/invites/{invite.id}", headers=headers
    )

    assert response.status_code == 204


async def test_an_agent_cannot_revoke_an_invite(db_session, client) -> None:
    workspace = await make_workspace(db_session)
    admin = await make_member(
        db_session, workspace, email="nilesh@example.com", role=Role.admin
    )
    agent = await make_member(
        db_session, workspace, email="sara@example.com", role=Role.agent
    )
    invite, _token = await team.create_invite(
        db_session, workspace.id, "new@example.com", Role.agent, admin.id
    )
    await db_session.commit()
    headers = await sign_in(client, db_session, agent.email)

    response = await client.delete(
        f"/api/team/invites/{invite.id}", headers=headers
    )

    assert response.status_code == 403


async def test_revoking_another_workspaces_invite_404s(db_session, client) -> None:
    other_workspace = await make_workspace(db_session, slug="other-co")
    other_admin = await make_member(
        db_session, other_workspace, email="other-admin@example.com", role=Role.admin
    )
    other_invite, _token = await team.create_invite(
        db_session, other_workspace.id, "victim@example.com", Role.agent, other_admin.id
    )
    await db_session.commit()

    workspace = await make_workspace(db_session, slug="acme")
    admin = await make_member(
        db_session, workspace, email="nilesh@example.com", role=Role.admin
    )
    await db_session.commit()
    headers = await sign_in(client, db_session, admin.email)

    response = await client.delete(
        f"/api/team/invites/{other_invite.id}", headers=headers
    )

    assert response.status_code == 404
