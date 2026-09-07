"""The v1 response shapes, pinned.

This is not a behaviour test. It exists so that a change to a v1 response --
a renamed field, a dropped one, a console refactor that leaks through --
fails a test in the same commit that makes it, rather than a third party's
integration some weeks later. Adding a field is compatible and should update
the expected set here; removing or renaming one is a breaking change and
should require a v2.
"""

from relaydesk.models import ApiKeyScope
from relaydesk.services import api_keys
from tests.factories import make_conversation, make_label, make_workspace

CONVERSATION_FIELDS = {
    "id",
    "number",
    "subject",
    "preview",
    "status",
    "priority",
    "channel",
    "customer",
    "assignee_id",
    "label_ids",
    "external_id",
    "metadata",
    "created_at",
    "updated_at",
    "last_message_at",
}
CONTACT_FIELDS = {"id", "email", "name"}
MESSAGE_FIELDS = {
    "id",
    "conversation_id",
    "role",
    "direction",
    "author_name",
    "body",
    "sent_at",
}
LABEL_FIELDS = {"id", "name", "color"}


async def all_scopes_key(db_session, workspace):
    token, _ = await api_keys.mint(
        db_session,
        workspace.id,
        name="Contract",
        scopes=list(ApiKeyScope),
        created_by_user_id=None,
    )
    return {"Authorization": f"Bearer {token}"}


async def test_the_conversation_shape_is_exactly_this(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    await make_conversation(db_session, workspace)
    headers = await all_scopes_key(db_session, workspace)

    page = (await client.get("/v1/conversations", headers=headers)).json()

    assert set(page) == {"data", "next_cursor"}
    assert set(page["data"][0]) == CONVERSATION_FIELDS
    assert set(page["data"][0]["customer"]) == CONTACT_FIELDS


async def test_the_message_shape_is_exactly_this(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    headers = await all_scopes_key(db_session, workspace)

    messages = (
        await client.get(
            f"/v1/conversations/{conversation.id}/messages", headers=headers
        )
    ).json()

    assert set(messages[0]) == MESSAGE_FIELDS


async def test_the_label_shape_is_exactly_this(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    await make_label(db_session, workspace)
    headers = await all_scopes_key(db_session, workspace)

    labels = (await client.get("/v1/labels", headers=headers)).json()

    assert set(labels[0]) == LABEL_FIELDS


async def test_the_contact_page_shape_is_exactly_this(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    await make_conversation(db_session, workspace)
    headers = await all_scopes_key(db_session, workspace)

    page = (await client.get("/v1/contacts", headers=headers)).json()

    assert set(page) == {"data", "next_cursor"}
    assert set(page["data"][0]) == CONTACT_FIELDS


def test_every_v1_route_is_under_the_v1_prefix() -> None:
    """No public endpoint may hide under /api, and no console route may
    appear under /v1 -- the prefix is the whole signal of which surface a
    route belongs to.

    ``app.routes`` is no use here: ``include_router`` does not flatten a
    sub-router's routes into it on this FastAPI version, so an included
    router shows up as a single opaque entry with no usable ``.path``.
    ``app.openapi()["paths"]`` is what a generated SDK actually consumes, so
    pinning it is a truer contract than pinning an internal attribute -- and
    unlike a bare set of paths, it also catches a dropped or added *method*
    on a path that already exists.

    Adding a path or a method here is a compatible change and should update
    this mapping in the same commit; removing or renaming one is a breaking
    change and should require a v2.
    """
    from relaydesk.main import app

    schema = app.openapi()
    v1_methods = {
        path: sorted(
            method
            for method in operations
            if method in {"get", "post", "put", "patch", "delete"}
        )
        for path, operations in schema["paths"].items()
        if path.startswith("/v1")
    }

    assert v1_methods == {
        "/v1/contacts": ["get"],
        "/v1/contacts/{contact_id}": ["get"],
        "/v1/conversations": ["get", "post"],
        "/v1/conversations/{conversation_id}": ["get", "patch"],
        "/v1/conversations/{conversation_id}/labels/{label_id}": [
            "delete",
            "put",
        ],
        "/v1/conversations/{conversation_id}/messages": ["get", "post"],
        "/v1/labels": ["get", "post"],
    }
