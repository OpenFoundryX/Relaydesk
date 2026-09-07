from relaydesk.models import ApiKeyScope
from relaydesk.services import api_keys
from tests.factories import make_conversation, make_label, make_workspace


async def key_for(db_session, workspace, scopes):
    token, _ = await api_keys.mint(
        db_session,
        workspace.id,
        name="Integration",
        scopes=scopes,
        created_by_user_id=None,
    )
    return {"Authorization": f"Bearer {token}"}


async def test_labels_are_listed(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    await make_label(db_session, workspace, name="Billing")
    headers = await key_for(db_session, workspace, [ApiKeyScope.labels_read])

    response = await client.get("/v1/labels", headers=headers)

    assert response.status_code == 200
    assert [item["name"] for item in response.json()] == ["Billing"]


async def test_only_this_workspaces_labels_are_listed(client, db_session) -> None:
    ours = await make_workspace(db_session, slug="ours")
    theirs = await make_workspace(db_session, slug="theirs")
    await make_label(db_session, ours, name="Ours")
    await make_label(db_session, theirs, name="Theirs")
    headers = await key_for(db_session, ours, [ApiKeyScope.labels_read])

    response = await client.get("/v1/labels", headers=headers)

    assert [item["name"] for item in response.json()] == ["Ours"]


async def test_a_label_is_created(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await key_for(db_session, workspace, [ApiKeyScope.labels_write])

    response = await client.post(
        "/v1/labels", json={"name": "Refunds"}, headers=headers
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Refunds"


async def test_creating_the_same_label_twice_returns_the_first(
    client, db_session
) -> None:
    workspace = await make_workspace(db_session)
    headers = await key_for(db_session, workspace, [ApiKeyScope.labels_write])

    first = await client.post("/v1/labels", json={"name": "Refunds"}, headers=headers)
    second = await client.post("/v1/labels", json={"name": "refunds"}, headers=headers)

    assert first.json()["id"] == second.json()["id"]


async def test_labels_read_alone_cannot_create(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await key_for(db_session, workspace, [ApiKeyScope.labels_read])

    response = await client.post("/v1/labels", json={"name": "X"}, headers=headers)

    assert response.status_code == 403


async def test_a_label_is_applied_and_removed(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    label = await make_label(db_session, workspace)
    headers = await key_for(db_session, workspace, [ApiKeyScope.labels_write])

    applied = await client.put(
        f"/v1/conversations/{conversation.id}/labels/{label.id}", headers=headers
    )
    assert applied.status_code == 200
    assert applied.json()["label_ids"] == [str(label.id)]

    removed = await client.delete(
        f"/v1/conversations/{conversation.id}/labels/{label.id}", headers=headers
    )
    assert removed.status_code == 200
    assert removed.json()["label_ids"] == []


async def test_applying_another_workspaces_label_answers_404(
    client, db_session
) -> None:
    ours = await make_workspace(db_session, slug="ours")
    theirs = await make_workspace(db_session, slug="theirs")
    conversation = await make_conversation(db_session, ours)
    foreign = await make_label(db_session, theirs, name="Theirs")
    headers = await key_for(db_session, ours, [ApiKeyScope.labels_write])

    response = await client.put(
        f"/v1/conversations/{conversation.id}/labels/{foreign.id}", headers=headers
    )

    assert response.status_code == 404
