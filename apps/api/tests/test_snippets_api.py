from relaydesk.models import Role
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


async def test_an_admin_creates_a_snippet_and_lists_it(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)

    created = await client.post(
        "/api/snippets",
        json={
            "title": "Follow up",
            "content": "Hi {{customer.first_name}} — any luck?",
        },
        headers=headers,
    )

    assert created.status_code == 201, created.text
    body = created.json()
    assert body["title"] == "Follow up"
    assert body["content"] == "Hi {{customer.first_name}} — any luck?"

    listed = await client.get("/api/snippets", headers=headers)
    assert [item["title"] for item in listed.json()] == ["Follow up"]


async def test_an_agent_can_read_snippets_but_not_change_them(
    client, db_session
) -> None:
    """The composer's `/` menu is an agent's tool, so reading is open to the
    whole workspace. Authoring is an admin's job, which is why Settings ->
    Templates is behind `requireAdmin` in the console."""
    workspace = await make_workspace(db_session)
    admin = await admin_headers(client, db_session, workspace)
    await client.post(
        "/api/snippets",
        json={"title": "Greeting", "content": "Hi!"},
        headers=admin,
    )
    headers = await agent_headers(client, db_session, workspace)

    listed = await client.get("/api/snippets", headers=headers)
    created = await client.post(
        "/api/snippets", json={"title": "Sneaky", "content": "Nope"}, headers=headers
    )

    assert listed.status_code == 200
    assert [item["title"] for item in listed.json()] == ["Greeting"]
    assert created.status_code == 403


async def test_an_agent_cannot_edit_or_delete_a_snippet(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    admin = await admin_headers(client, db_session, workspace)
    created = await client.post(
        "/api/snippets", json={"title": "Greeting", "content": "Hi!"}, headers=admin
    )
    snippet_id = created.json()["id"]
    headers = await agent_headers(client, db_session, workspace)

    patched = await client.patch(
        f"/api/snippets/{snippet_id}", json={"content": "Nope"}, headers=headers
    )
    deleted = await client.delete(f"/api/snippets/{snippet_id}", headers=headers)

    assert patched.status_code == 403
    assert deleted.status_code == 403


async def test_snippets_require_a_session(client, db_session) -> None:
    await make_workspace(db_session)

    response = await client.get("/api/snippets")

    assert response.status_code == 401


async def test_a_duplicate_title_is_a_409(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)
    await client.post(
        "/api/snippets", json={"title": "Greeting", "content": "Hi!"}, headers=headers
    )

    response = await client.post(
        "/api/snippets",
        json={"title": "greeting", "content": "Hello!"},
        headers=headers,
    )

    assert response.status_code == 409


async def test_a_blank_title_is_a_422(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)

    response = await client.post(
        "/api/snippets", json={"title": "   ", "content": "Hi!"}, headers=headers
    )

    assert response.status_code == 422


async def test_a_snippet_is_edited_in_place(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)
    created = await client.post(
        "/api/snippets", json={"title": "Greeting", "content": "Hi!"}, headers=headers
    )
    snippet_id = created.json()["id"]

    patched = await client.patch(
        f"/api/snippets/{snippet_id}",
        json={"title": "Greeting", "content": "Hello there!"},
        headers=headers,
    )

    assert patched.status_code == 200, patched.text
    assert patched.json()["content"] == "Hello there!"
    listed = await client.get("/api/snippets", headers=headers)
    assert len(listed.json()) == 1


async def test_a_deleted_snippet_is_gone(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)
    created = await client.post(
        "/api/snippets", json={"title": "Greeting", "content": "Hi!"}, headers=headers
    )

    deleted = await client.delete(
        f"/api/snippets/{created.json()['id']}", headers=headers
    )

    assert deleted.status_code == 204
    listed = await client.get("/api/snippets", headers=headers)
    assert listed.json() == []


async def test_another_workspaces_snippet_is_a_404(client, db_session) -> None:
    one = await make_workspace(db_session, slug="chronon")
    two = await make_workspace(db_session, slug="northwind")
    intruder = await admin_headers(client, db_session, one)
    await make_member(db_session, two, email="owner@northwind.io")
    await db_session.commit()
    owner = await sign_in(client, db_session, "owner@northwind.io")
    created = await client.post(
        "/api/snippets", json={"title": "Greeting", "content": "Hi!"}, headers=owner
    )

    response = await client.delete(
        f"/api/snippets/{created.json()['id']}", headers=intruder
    )

    assert response.status_code == 404
