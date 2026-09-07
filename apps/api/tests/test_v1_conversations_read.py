from datetime import UTC, datetime, timedelta

from relaydesk.models import ApiKeyScope, ConversationStatus, Priority
from relaydesk.services import api_keys
from tests.factories import make_conversation, make_label, make_workspace


async def setup_key(db_session, workspace, scopes=None):
    token, _ = await api_keys.mint(
        db_session,
        workspace.id,
        name="Integration",
        scopes=scopes or [ApiKeyScope.conversations_read],
        created_by_user_id=None,
    )
    return {"Authorization": f"Bearer {token}"}


async def test_list_returns_this_workspaces_conversations(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace, subject="Refund")
    headers = await setup_key(db_session, workspace)

    response = await client.get("/v1/conversations", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert [item["subject"] for item in body["data"]] == ["Refund"]
    assert body["next_cursor"] is None
    item = body["data"][0]
    assert item["id"] == str(conversation.id)
    assert item["number"] == conversation.number
    assert item["status"] == "open"
    assert item["external_id"] is None
    assert item["metadata"] == {}
    assert item["customer"]["email"] == "priya@northwind.io"


async def test_the_response_carries_no_console_only_fields(client, db_session) -> None:
    """v1 must not inherit the inbox's rendering decisions (spec D6)."""
    workspace = await make_workspace(db_session)
    await make_conversation(db_session, workspace)
    headers = await setup_key(db_session, workspace)

    item = (await client.get("/v1/conversations", headers=headers)).json()["data"][0]

    for console_only in ("age", "date", "hasDraft", "has_draft", "unread"):
        assert console_only not in item


async def test_the_response_is_snake_case(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    await make_conversation(db_session, workspace)
    headers = await setup_key(db_session, workspace)

    item = (await client.get("/v1/conversations", headers=headers)).json()["data"][0]

    assert "last_message_at" in item
    assert "lastMessageAt" not in item


async def test_list_filters_by_status(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    await make_conversation(db_session, workspace, subject="Open one")
    await make_conversation(
        db_session, workspace, subject="Resolved one",
        status=ConversationStatus.resolved,
    )
    headers = await setup_key(db_session, workspace)

    response = await client.get(
        "/v1/conversations", params={"status": "resolved"}, headers=headers
    )

    assert [item["subject"] for item in response.json()["data"]] == ["Resolved one"]


async def test_list_filters_by_priority(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    await make_conversation(db_session, workspace, subject="Urgent one")
    await make_conversation(
        db_session, workspace, subject="Low one", priority=Priority.low
    )
    headers = await setup_key(db_session, workspace)

    response = await client.get(
        "/v1/conversations", params={"priority": "low"}, headers=headers
    )

    assert [item["subject"] for item in response.json()["data"]] == ["Low one"]


async def test_list_filters_by_updated_since(client, db_session) -> None:
    """What makes a polling sync possible before webhooks exist."""
    workspace = await make_workspace(db_session)
    stale = await make_conversation(db_session, workspace, subject="Stale")
    headers = await setup_key(
        db_session,
        workspace,
        scopes=[ApiKeyScope.conversations_read, ApiKeyScope.conversations_write],
    )
    boundary = datetime.now(UTC)

    fresh = await make_conversation(db_session, workspace, subject="Fresh")
    fresh.updated_at = boundary + timedelta(seconds=5)
    stale.updated_at = boundary - timedelta(hours=1)
    await db_session.commit()

    response = await client.get(
        "/v1/conversations",
        params={"updated_since": boundary.isoformat()},
        headers=headers,
    )

    assert [item["subject"] for item in response.json()["data"]] == ["Fresh"]


async def test_list_rejects_a_naive_updated_since(client, db_session) -> None:
    """A naive value must be refused, not silently read as server-local time.

    ``Conversation.updated_at`` is timezone-aware; asyncpg encodes a naive
    Python ``datetime`` by assuming the *server's* local timezone, not UTC.
    A shifted boundary in a sync cursor silently skips records -- exactly
    what this parameter exists to prevent -- so a naive ISO-8601 string
    (what a third-party client sends by default) is a 422, not a guess.
    """
    workspace = await make_workspace(db_session)
    headers = await setup_key(db_session, workspace)

    response = await client.get(
        "/v1/conversations",
        params={"updated_since": "2026-01-01T00:00:00"},
        headers=headers,
    )

    assert response.status_code == 422


async def test_list_rejects_an_unknown_status(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await setup_key(db_session, workspace)

    response = await client.get(
        "/v1/conversations", params={"status": "banana"}, headers=headers
    )

    assert response.status_code == 422


async def test_list_paginates_by_cursor(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    for index in range(3):
        await make_conversation(
            db_session, workspace, subject=f"Ticket {index}", minutes_ago=index + 1
        )
    headers = await setup_key(db_session, workspace)

    first = await client.get(
        "/v1/conversations", params={"limit": 2}, headers=headers
    )
    cursor = first.json()["next_cursor"]
    assert cursor is not None

    second = await client.get(
        "/v1/conversations", params={"limit": 2, "cursor": cursor}, headers=headers
    )

    seen = [item["id"] for item in first.json()["data"]] + [
        item["id"] for item in second.json()["data"]
    ]
    assert len(seen) == len(set(seen)) == 3


async def test_get_returns_one_conversation_with_its_labels(
    client, db_session
) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    label = await make_label(db_session, workspace)
    # ``conversation`` was constructed directly, not loaded through a
    # ``select()`` -- so ``labels`` (lazy="selectin") is unpopulated on this
    # AsyncSession, and a synchronous ``.append()`` would try to lazy-load it
    # outside of any greenlet context. An explicit async refresh loads it
    # first so the mutation below is a plain in-memory list operation.
    await db_session.refresh(conversation, ["labels"])
    conversation.labels.append(label)
    await db_session.commit()
    headers = await setup_key(db_session, workspace)

    response = await client.get(
        f"/v1/conversations/{conversation.id}", headers=headers
    )

    assert response.status_code == 200
    assert response.json()["label_ids"] == [str(label.id)]


async def test_get_answers_404_for_an_unknown_id(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await setup_key(db_session, workspace)

    response = await client.get(
        "/v1/conversations/00000000-0000-0000-0000-000000000000", headers=headers
    )

    assert response.status_code == 404


async def test_messages_are_returned_oldest_first(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    headers = await setup_key(db_session, workspace)

    response = await client.get(
        f"/v1/conversations/{conversation.id}/messages", headers=headers
    )

    assert response.status_code == 200
    messages = response.json()
    assert len(messages) == 1
    assert messages[0]["role"] == "customer"
    assert messages[0]["direction"] == "inbound"
    assert messages[0]["author_name"] == "Priya Raman"


async def test_messages_for_another_workspace_answer_404(client, db_session) -> None:
    ours = await make_workspace(db_session, slug="ours")
    theirs = await make_workspace(db_session, slug="theirs")
    hidden = await make_conversation(db_session, theirs)
    headers = await setup_key(db_session, ours)

    response = await client.get(
        f"/v1/conversations/{hidden.id}/messages", headers=headers
    )

    assert response.status_code == 404
