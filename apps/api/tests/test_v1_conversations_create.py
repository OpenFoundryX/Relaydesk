import asyncio

import sqlalchemy as sa

from relaydesk.models import (
    ActivityEvent,
    ActivityKind,
    ApiKeyScope,
    Channel,
    Contact,
    Conversation,
    Message,
    MessageDirection,
    MessageRole,
)
from relaydesk.services import api_keys
from tests.factories import make_workspace

BODY = {
    "customer_email": "customer@example.com",
    "customer_name": "Priya Raman",
    "subject": "Help with order",
    "message": "I need help with my recent order.",
    "priority": "high",
    "external_id": "ticket-123",
    "metadata": {"order_id": "ord_456", "plan": "growth"},
}


async def writer(db_session, workspace, name="Production ingest"):
    token, key = await api_keys.mint(
        db_session,
        workspace.id,
        name=name,
        scopes=[ApiKeyScope.conversations_write],
        created_by_user_id=None,
    )
    return {"Authorization": f"Bearer {token}"}, key


async def test_the_published_code_sample_works_verbatim(client, db_session) -> None:
    """The exact body ``components/settings/code-sample.tsx`` publishes."""
    workspace = await make_workspace(db_session)
    headers, _ = await writer(db_session, workspace)

    response = await client.post("/v1/conversations", json=BODY, headers=headers)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["subject"] == "Help with order"
    assert body["priority"] == "high"
    assert body["channel"] == "api"
    assert body["external_id"] == "ticket-123"
    assert body["metadata"] == {"order_id": "ord_456", "plan": "growth"}
    assert body["customer"]["email"] == "customer@example.com"
    assert body["customer"]["name"] == "Priya Raman"


async def test_the_first_message_is_the_customers(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers, _ = await writer(db_session, workspace)

    created = (
        await client.post("/v1/conversations", json=BODY, headers=headers)
    ).json()

    stored = list(
        await db_session.scalars(
            sa.select(Message).where(Message.conversation_id == created["id"])
        )
    )
    assert len(stored) == 1
    assert stored[0].role is MessageRole.customer
    assert stored[0].direction is MessageDirection.inbound
    assert stored[0].body == "I need help with my recent order."
    assert stored[0].author_name == "Priya Raman"


async def test_creation_is_recorded_against_the_key(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers, key = await writer(db_session, workspace)

    created = (
        await client.post("/v1/conversations", json=BODY, headers=headers)
    ).json()

    event = await db_session.scalar(
        sa.select(ActivityEvent).where(
            ActivityEvent.conversation_id == created["id"],
            ActivityEvent.kind == ActivityKind.created,
        )
    )
    assert event is not None
    assert event.actor_api_key_id == key.id
    assert event.actor_user_id is None
    assert event.actor_name == "Production ingest"


async def test_a_repeated_external_id_returns_the_first_conversation(
    client, db_session
) -> None:
    workspace = await make_workspace(db_session)
    headers, _ = await writer(db_session, workspace)

    first = await client.post("/v1/conversations", json=BODY, headers=headers)
    second = await client.post("/v1/conversations", json=BODY, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]

    total = await db_session.scalar(
        sa.select(sa.func.count())
        .select_from(Conversation)
        .where(Conversation.workspace_id == workspace.id)
    )
    assert total == 1


async def test_two_workspaces_may_use_the_same_external_id(client, db_session) -> None:
    ours = await make_workspace(db_session, slug="ours")
    theirs = await make_workspace(db_session, slug="theirs")
    our_headers, _ = await writer(db_session, ours)
    their_headers, _ = await writer(db_session, theirs, name="Theirs")

    first = await client.post("/v1/conversations", json=BODY, headers=our_headers)
    second = await client.post("/v1/conversations", json=BODY, headers=their_headers)

    assert (first.status_code, second.status_code) == (201, 201)
    assert first.json()["id"] != second.json()["id"]


async def test_a_creation_without_an_external_id_is_never_deduplicated(
    client, db_session
) -> None:
    workspace = await make_workspace(db_session)
    headers, _ = await writer(db_session, workspace)
    body = {key: value for key, value in BODY.items() if key != "external_id"}

    first = await client.post("/v1/conversations", json=body, headers=headers)
    second = await client.post("/v1/conversations", json=body, headers=headers)

    assert (first.status_code, second.status_code) == (201, 201)
    assert first.json()["id"] != second.json()["id"]


async def test_a_blank_external_id_is_never_deduplicated(client, db_session) -> None:
    """``""`` means "no external id", the same as omitting the field.

    Before normalisation, ``''`` is a real, non-NULL value covered by the
    partial unique index -- a first create would silently store it, and a
    second would hit the index and 500 through the ``IntegrityError``
    handler's ``if not external_id: raise``. Asserting the stored value is
    ``None`` (not ``''``) is what proves normalisation happened rather than
    the dedup lookup merely missing an empty string by luck.
    """
    workspace = await make_workspace(db_session)
    headers, _ = await writer(db_session, workspace)
    body = {**BODY, "external_id": ""}

    first = await client.post("/v1/conversations", json=body, headers=headers)
    second = await client.post("/v1/conversations", json=body, headers=headers)

    assert (first.status_code, second.status_code) == (201, 201)
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["external_id"] is None
    assert second.json()["external_id"] is None

    stored = list(
        await db_session.scalars(
            sa.select(Conversation.external_id).where(
                Conversation.workspace_id == workspace.id
            )
        )
    )
    assert stored == [None, None]


async def test_a_whitespace_only_external_id_is_never_deduplicated(
    client, db_session
) -> None:
    workspace = await make_workspace(db_session)
    headers, _ = await writer(db_session, workspace)
    body = {**BODY, "external_id": "   "}

    first = await client.post("/v1/conversations", json=body, headers=headers)
    second = await client.post("/v1/conversations", json=body, headers=headers)

    assert (first.status_code, second.status_code) == (201, 201)
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["external_id"] is None
    assert second.json()["external_id"] is None


async def test_a_repeat_reuses_the_contact(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers, _ = await writer(db_session, workspace)
    body = {key: value for key, value in BODY.items() if key != "external_id"}

    await client.post("/v1/conversations", json=body, headers=headers)
    await client.post("/v1/conversations", json=body, headers=headers)

    total = await db_session.scalar(
        sa.select(sa.func.count())
        .select_from(Contact)
        .where(Contact.workspace_id == workspace.id)
    )
    assert total == 1


async def test_a_blank_message_is_refused(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers, _ = await writer(db_session, workspace)

    response = await client.post(
        "/v1/conversations",
        json={**BODY, "message": "   ", "external_id": "blank"},
        headers=headers,
    )

    assert response.status_code == 422


async def test_oversized_metadata_is_refused(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers, _ = await writer(db_session, workspace)

    response = await client.post(
        "/v1/conversations",
        json={**BODY, "external_id": "big", "metadata": {"blob": "x" * 9000}},
        headers=headers,
    )

    assert response.status_code == 422


async def test_too_many_metadata_keys_are_refused(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers, _ = await writer(db_session, workspace)

    response = await client.post(
        "/v1/conversations",
        json={
            **BODY,
            "external_id": "many",
            "metadata": {f"k{index}": index for index in range(51)},
        },
        headers=headers,
    )

    assert response.status_code == 422


async def test_a_read_only_key_cannot_create(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    token, _ = await api_keys.mint(
        db_session,
        workspace.id,
        name="Reporting",
        scopes=[ApiKeyScope.conversations_read],
        created_by_user_id=None,
    )

    response = await client.post(
        "/v1/conversations",
        json=BODY,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert "conversations:write" in response.json()["error"]["message"]


async def test_two_concurrent_creates_with_one_external_id_make_one_row(
    engine,
) -> None:
    """The savepoint in ``create_from_api``, exercised.

    Both callers miss the lookup, both insert, and the partial unique index
    refuses the loser. The loser must return the winner's conversation, not
    an unhandled IntegrityError -> 500.

    This test opens its own sessions against ``engine`` -- rather than using
    the ``db_session`` fixture -- to create its workspace and key, and
    commits genuinely. ``db_session`` binds to a connection inside an outer
    transaction using ``join_transaction_mode="create_savepoint"``; its
    ``commit()`` only releases a savepoint, so the outer transaction stays
    open and rolls back at teardown, and no other connection would ever see
    those rows. The two concurrent sessions below are separate connections,
    so the key's workspace and the key itself have to be real, committed
    rows or every concurrent insert would fail its foreign key. Because
    these writes are real and are not rolled back by any fixture, the test
    cleans up after itself at the end.
    """
    from sqlalchemy.ext.asyncio import AsyncSession

    from relaydesk.models import Priority, Workspace
    from relaydesk.services import tickets
    from relaydesk.services.actors import Actor

    async with AsyncSession(bind=engine, expire_on_commit=False) as setup_session:
        workspace = await make_workspace(setup_session, slug="race-conditions")
        _, key = await api_keys.mint(
            setup_session,
            workspace.id,
            name="Importer",
            scopes=[ApiKeyScope.conversations_write],
            created_by_user_id=None,
        )
        await setup_session.commit()
        workspace_id = workspace.id

    async def create_once():
        async with AsyncSession(bind=engine, expire_on_commit=False) as session:
            conversation, created = await tickets.create_from_api(
                session,
                workspace_id,
                email="customer@example.com",
                name="Priya Raman",
                subject="Help with order",
                message="I need help with my recent order.",
                priority=Priority.high,
                external_id="race-1",
                metadata={},
                actor=Actor.for_key(key),
            )
            return str(conversation.id), created

    try:
        results = await asyncio.gather(create_once(), create_once())

        assert len({identifier for identifier, _ in results}) == 1
        assert sorted(created for _, created in results) == [False, True]
    finally:
        async with AsyncSession(bind=engine, expire_on_commit=False) as cleanup_session:
            await cleanup_session.execute(
                sa.delete(Workspace).where(Workspace.id == workspace_id)
            )
            await cleanup_session.commit()


async def test_the_conversation_is_channel_api(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers, _ = await writer(db_session, workspace)

    created = (
        await client.post("/v1/conversations", json=BODY, headers=headers)
    ).json()

    stored = await db_session.scalar(
        sa.select(Conversation).where(Conversation.id == created["id"])
    )
    assert stored.channel is Channel.api
