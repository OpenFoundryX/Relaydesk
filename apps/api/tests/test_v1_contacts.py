from relaydesk.models import ApiKeyScope, Contact
from relaydesk.services import api_keys
from tests.factories import make_conversation, make_workspace


async def key_for(db_session, workspace, scopes=None):
    token, _ = await api_keys.mint(
        db_session,
        workspace.id,
        name="Integration",
        scopes=scopes or [ApiKeyScope.contacts_read],
        created_by_user_id=None,
    )
    return {"Authorization": f"Bearer {token}"}


async def test_contacts_are_listed(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    await make_conversation(db_session, workspace)
    headers = await key_for(db_session, workspace)

    response = await client.get("/v1/contacts", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert [item["email"] for item in body["data"]] == ["priya@northwind.io"]
    assert body["next_cursor"] is None


async def test_only_this_workspaces_contacts_are_listed(client, db_session) -> None:
    ours = await make_workspace(db_session, slug="ours")
    theirs = await make_workspace(db_session, slug="theirs")
    await make_conversation(db_session, ours, contact_email="ours@example.com")
    await make_conversation(db_session, theirs, contact_email="theirs@example.com")
    headers = await key_for(db_session, ours)

    response = await client.get("/v1/contacts", headers=headers)

    assert [item["email"] for item in response.json()["data"]] == ["ours@example.com"]


async def test_contacts_paginate(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    for index in range(3):
        db_session.add(
            Contact(
                workspace_id=workspace.id,
                email=f"person{index}@example.com",
                name=f"Person {index}",
            )
        )
    await db_session.commit()
    headers = await key_for(db_session, workspace)

    first = await client.get("/v1/contacts", params={"limit": 2}, headers=headers)
    cursor = first.json()["next_cursor"]
    assert cursor is not None

    second = await client.get(
        "/v1/contacts", params={"limit": 2, "cursor": cursor}, headers=headers
    )

    seen = [item["id"] for item in first.json()["data"]] + [
        item["id"] for item in second.json()["data"]
    ]
    assert len(seen) == len(set(seen)) == 3


async def test_one_contact_is_returned(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    headers = await key_for(db_session, workspace)

    response = await client.get(
        f"/v1/contacts/{conversation.contact_id}", headers=headers
    )

    assert response.status_code == 200
    assert response.json()["email"] == "priya@northwind.io"


async def test_another_workspaces_contact_answers_404(client, db_session) -> None:
    ours = await make_workspace(db_session, slug="ours")
    theirs = await make_workspace(db_session, slug="theirs")
    hidden = await make_conversation(db_session, theirs)
    headers = await key_for(db_session, ours)

    response = await client.get(
        f"/v1/contacts/{hidden.contact_id}", headers=headers
    )

    assert response.status_code == 404


async def test_a_key_without_contacts_read_is_refused(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await key_for(db_session, workspace, [ApiKeyScope.labels_read])

    response = await client.get("/v1/contacts", headers=headers)

    assert response.status_code == 403
    assert "contacts:read" in response.json()["error"]["message"]
