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

    page = (
        await client.get(
            f"/v1/conversations/{conversation.id}/messages", headers=headers
        )
    ).json()

    assert set(page) == {"data", "next_cursor"}
    assert set(page["data"][0]) == MESSAGE_FIELDS


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


async def test_the_response_enums_are_enumerated_in_the_openapi_document(
    client, db_session
) -> None:
    """A generated SDK gets a typed response field, not a bare string.

    The route's query filters are already typed ``ConversationStatus`` and
    ``Priority``; the response fields for the same concepts were plain
    ``str``, so a client got a typed filter argument and an untyped field
    back. These are ``StrEnum`` members, so this changes the OpenAPI document
    and *not* the wire values -- which the next test is there to hold.
    """
    from relaydesk.main import app

    schema = app.openapi()
    components = schema["components"]["schemas"]
    conversation = components["relaydesk__schemas__v1__ConversationOut"]
    message = components["relaydesk__schemas__v1__MessageOut"]

    def enumerated(properties: dict, field: str) -> list[str]:
        reference = properties[field]["$ref"].rsplit("/", 1)[-1]
        return components[reference]["enum"]

    assert enumerated(conversation["properties"], "status") == [
        "open",
        "pending",
        "resolved",
        "on_hold",
        "ignored",
        "trash",
    ]
    assert enumerated(conversation["properties"], "priority") == [
        "urgent",
        "high",
        "medium",
        "low",
    ]
    assert enumerated(conversation["properties"], "channel") == [
        "email",
        "discord",
        "portal",
        "api",
    ]
    assert enumerated(message["properties"], "role") == [
        "customer",
        "agent",
        "ai",
        "system",
    ]
    assert enumerated(message["properties"], "direction") == ["inbound", "outbound"]


async def test_the_enum_fields_are_still_plain_strings_on_the_wire(
    client, db_session
) -> None:
    """Typing the fields as enums must not change a single byte of JSON.

    ``StrEnum`` members serialise to their values, so this is the assertion
    that makes the typing change safe for third parties already integrated.
    """
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    headers = await all_scopes_key(db_session, workspace)

    item = (await client.get("/v1/conversations", headers=headers)).json()["data"][0]
    message = (
        await client.get(
            f"/v1/conversations/{conversation.id}/messages", headers=headers
        )
    ).json()["data"][0]

    for field, expected in (
        ("status", "open"),
        ("priority", "urgent"),
        ("channel", "email"),
    ):
        assert isinstance(item[field], str)
        assert item[field] == expected
    for field, expected in (("role", "customer"), ("direction", "inbound")):
        assert isinstance(message[field], str)
        assert message[field] == expected


def test_the_openapi_document_declares_the_idempotent_conversation_200() -> None:
    """Spec section 6 makes the replay first-class, so it must be published.

    With only ``status_code=201`` on the decorator the document says nothing
    about the 200 a matched ``external_id`` earns, and a strict generated
    client treats a safe re-run of an interrupted import as an unexpected
    response.
    """
    from relaydesk.main import app

    operation = app.openapi()["paths"]["/v1/conversations"]["post"]

    assert "200" in operation["responses"]
    assert "201" in operation["responses"]
