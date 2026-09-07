from relaydesk.models import ApiKeyScope, Role
from tests.factories import make_member, make_workspace, sign_in


async def admin_headers(client, db_session, workspace):
    await make_member(db_session, workspace, email="admin@relaydesk.dev")
    await db_session.commit()
    return await sign_in(client, db_session, "admin@relaydesk.dev")


async def agent_headers(client, db_session, workspace):
    await make_member(
        db_session, workspace, email="agent@relaydesk.dev", role=Role.agent
    )
    await db_session.commit()
    return await sign_in(client, db_session, "agent@relaydesk.dev")


async def test_an_admin_creates_a_key_and_sees_the_secret_once(
    client, db_session
) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)

    created = await client.post(
        "/api/api-keys",
        json={
            "name": "Production ingest",
            "scopes": ["conversations:read", "conversations:write"],
        },
        headers=headers,
    )

    assert created.status_code == 201, created.text
    body = created.json()
    assert body["token"].startswith("rd_")
    assert body["key"]["name"] == "Production ingest"
    assert body["key"]["prefix"] == body["token"][:7]
    assert body["key"]["scopes"] == ["conversations:read", "conversations:write"]

    listed = await client.get("/api/api-keys", headers=headers)
    assert [item["name"] for item in listed.json()] == ["Production ingest"]
    # The secret is never offered again, in any field.
    assert body["token"] not in listed.text


async def test_an_agent_cannot_manage_keys(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await agent_headers(client, db_session, workspace)

    listed = await client.get("/api/api-keys", headers=headers)
    created = await client.post(
        "/api/api-keys",
        json={"name": "Sneaky", "scopes": ["conversations:read"]},
        headers=headers,
    )

    assert listed.status_code == 403
    assert created.status_code == 403


async def test_an_unknown_scope_is_refused(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)

    response = await client.post(
        "/api/api-keys",
        json={"name": "Bad", "scopes": ["workspace:destroy"]},
        headers=headers,
    )

    assert response.status_code == 422


async def test_a_revoked_key_disappears_from_the_list(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)
    created = await client.post(
        "/api/api-keys",
        json={"name": "Temporary", "scopes": ["conversations:read"]},
        headers=headers,
    )
    key_id = created.json()["key"]["id"]

    deleted = await client.delete(f"/api/api-keys/{key_id}", headers=headers)

    assert deleted.status_code == 204
    assert (await client.get("/api/api-keys", headers=headers)).json() == []


async def test_a_revoked_key_stops_working_immediately(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)
    created = await client.post(
        "/api/api-keys",
        json={"name": "Temporary", "scopes": ["conversations:read"]},
        headers=headers,
    )
    token = created.json()["token"]
    assert (
        await client.get(
            "/v1/conversations", headers={"Authorization": f"Bearer {token}"}
        )
    ).status_code == 200

    await client.delete(f"/api/api-keys/{created.json()['key']['id']}", headers=headers)

    after = await client.get(
        "/v1/conversations", headers={"Authorization": f"Bearer {token}"}
    )
    assert after.status_code == 401


async def test_an_admin_cannot_revoke_another_workspaces_key(
    client, db_session
) -> None:
    ours = await make_workspace(db_session, slug="ours")
    theirs = await make_workspace(db_session, slug="theirs")
    from relaydesk.services import api_keys

    _, foreign = await api_keys.mint(
        db_session,
        theirs.id,
        name="Theirs",
        scopes=[ApiKeyScope.conversations_read],
        created_by_user_id=None,
    )
    headers = await admin_headers(client, db_session, ours)

    response = await client.delete(f"/api/api-keys/{foreign.id}", headers=headers)

    assert response.status_code == 404
