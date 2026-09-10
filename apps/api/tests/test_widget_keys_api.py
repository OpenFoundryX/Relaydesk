from relaydesk.models import Role
from tests.factories import make_member, make_workspace, sign_in


# The house pattern -- these mirror tests/test_api_keys_api.py.
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


async def test_admin_creates_and_lists(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)

    created = await client.post(
        "/api/widget-keys",
        json={"name": "Marketing site", "allowedOrigins": ["https://acme.com/"]},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["key"].startswith("rdw_")
    assert body["allowedOrigins"] == ["https://acme.com"]

    listed = await client.get("/api/widget-keys", headers=headers)
    assert listed.status_code == 200
    # The key comes back in full every time -- it is public, and the admin
    # needs it to re-paste the snippet. Contrast ApiKey, whose secret is
    # shown once and never again.
    assert listed.json()[0]["key"] == body["key"]


async def test_create_really_commits(client, db_session, commit_spy) -> None:
    """`create_route` must commit, not just flush -- see widget_keys.py.

    `commit_spy` is the only thing in this file that can tell the two
    apart: `client` hands the route this exact `db_session`, so a bare
    flush is already visible to every other assertion here, committed or
    not.
    """
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)
    commit_spy.clear()  # admin_headers' own sign-in commits too.

    response = await client.post(
        "/api/widget-keys", json={"name": "Site"}, headers=headers
    )

    assert response.status_code == 201, response.text
    assert len(commit_spy) >= 1


async def test_agent_is_refused(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await agent_headers(client, db_session, workspace)

    response = await client.post(
        "/api/widget-keys", json={"name": "Site"}, headers=headers
    )
    assert response.status_code == 403, response.text


async def test_bad_origin_is_rejected(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)

    response = await client.post(
        "/api/widget-keys",
        json={"name": "Site", "allowedOrigins": ["*.acme.com"]},
        headers=headers,
    )
    assert response.status_code == 422, response.text


async def test_delete_removes_the_embed(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)

    created = await client.post(
        "/api/widget-keys", json={"name": "Site"}, headers=headers
    )
    key_id = created.json()["id"]

    deleted = await client.delete(f"/api/widget-keys/{key_id}", headers=headers)
    assert deleted.status_code == 204, deleted.text

    remaining = await client.get("/api/widget-keys", headers=headers)
    assert remaining.json() == []
