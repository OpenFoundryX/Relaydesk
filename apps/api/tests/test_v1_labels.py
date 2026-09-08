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


async def test_a_new_label_is_201_and_a_repeat_is_200(client, db_session) -> None:
    """The status code is the only thing that distinguishes the two.

    ``POST /v1/conversations`` already answers 201 for a genuine create and
    200 when ``external_id`` matched something the workspace had. This route
    is equally idempotent, so it has to report the outcome the same way: an
    importer creating labels and conversations in one pass and counting
    creations by status code would otherwise log "created 40 labels" on
    every re-run, with no way to learn that 39 already existed.

    Case-insensitively, too -- ``labels.name`` is CITEXT, so "refunds" is a
    replay of "Refunds", not a second label.
    """
    workspace = await make_workspace(db_session)
    headers = await key_for(db_session, workspace, [ApiKeyScope.labels_write])

    first = await client.post("/v1/labels", json={"name": "Refunds"}, headers=headers)
    second = await client.post("/v1/labels", json={"name": "Refunds"}, headers=headers)
    variant = await client.post("/v1/labels", json={"name": "refunds"}, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert variant.status_code == 200
    assert first.json() == second.json() == variant.json()


async def test_the_openapi_document_declares_the_idempotent_200(client) -> None:
    """A generated SDK must know 200 is a valid answer to this POST.

    Without the ``responses={200: ...}`` declaration the route advertises
    only its ``status_code=201``, and a strict client treats the replay as
    an unexpected response.
    """
    from relaydesk.main import app

    operation = app.openapi()["paths"]["/v1/labels"]["post"]

    assert "200" in operation["responses"]
    assert "201" in operation["responses"]


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
