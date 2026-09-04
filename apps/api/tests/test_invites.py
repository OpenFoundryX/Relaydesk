from datetime import UTC, datetime, timedelta

from relaydesk.models import Role
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
    assert "/invites/" in outbox[0]["text"]


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
        f"/api/invites/{raw_token}/accept",
        json={"name": "Sara", "password": "correct horse battery staple"},
    )
    assert first.status_code == 200

    second = await client.post(
        f"/api/invites/{raw_token}/accept",
        json={"name": "Sara", "password": "correct horse battery staple"},
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
        f"/api/invites/{raw_token}/accept",
        json={"name": "Sara", "password": "correct horse battery staple"},
    )

    assert response.status_code == 404


async def test_accepting_lands_in_the_inviting_workspace(
    db_session, client, outbox
) -> None:
    """Task 5 pins the session to a workspace; this proves acceptance mints
    it for the workspace that issued the invite."""
    workspace = await make_workspace(db_session, slug="acme")
    admin = await make_member(
        db_session, workspace, email="nilesh@example.com", role=Role.admin
    )
    _invite, raw_token = await team.create_invite(
        db_session, workspace.id, "sara@example.com", Role.agent, admin.id
    )
    await db_session.commit()

    accept = await client.post(
        f"/api/invites/{raw_token}/accept",
        json={"name": "Sara", "password": "correct horse battery staple"},
    )
    session_token = accept.json()["token"]

    me = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {session_token}"}
    )

    assert me.json()["workspace"]["id"] == str(workspace.id)
