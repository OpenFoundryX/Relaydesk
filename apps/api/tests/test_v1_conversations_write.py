import uuid
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa

from relaydesk.models import (
    ApiKeyScope,
    DeliveryState,
    Message,
    MessageDirection,
    MessageRole,
    Priority,
)
from relaydesk.services import api_keys, conversations
from tests.factories import make_conversation, make_member, make_workspace


async def key_for(db_session, workspace, scopes, name="Integration"):
    token, key = await api_keys.mint(
        db_session,
        workspace.id,
        name=name,
        scopes=scopes,
        created_by_user_id=None,
    )
    return {"Authorization": f"Bearer {token}"}, key


async def test_patch_changes_the_status(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    headers, _ = await key_for(db_session, workspace, [ApiKeyScope.conversations_write])

    response = await client.patch(
        f"/v1/conversations/{conversation.id}",
        json={"status": "resolved"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "resolved"


async def test_patch_changes_the_priority(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(
        db_session, workspace, priority=Priority.low
    )
    headers, _ = await key_for(db_session, workspace, [ApiKeyScope.conversations_write])

    response = await client.patch(
        f"/v1/conversations/{conversation.id}",
        json={"priority": "urgent"},
        headers=headers,
    )

    assert response.json()["priority"] == "urgent"


async def test_patch_assigns_to_a_member(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    member = await make_member(db_session, workspace)
    conversation = await make_conversation(db_session, workspace)
    headers, _ = await key_for(db_session, workspace, [ApiKeyScope.conversations_write])

    response = await client.patch(
        f"/v1/conversations/{conversation.id}",
        json={"assignee_id": str(member.id)},
        headers=headers,
    )

    assert response.json()["assignee_id"] == str(member.id)


async def test_patch_unassigns_with_an_explicit_null(client, db_session) -> None:
    """{"assignee_id": null} must clear the assignee.

    ``ConversationUpdate.assignee_id`` is ``uuid.UUID | None``, so an
    explicit null and an omitted field both arrive as ``None`` on the
    parsed payload -- the only way to tell them apart is
    ``model_fields_set``, exactly as the console's ``patch_conversation``
    already does. Without that check there would be no way to unassign a
    conversation through v1 at all.
    """
    workspace = await make_workspace(db_session)
    member = await make_member(db_session, workspace)
    conversation = await make_conversation(db_session, workspace)
    headers, _ = await key_for(db_session, workspace, [ApiKeyScope.conversations_write])

    assigned = await client.patch(
        f"/v1/conversations/{conversation.id}",
        json={"assignee_id": str(member.id)},
        headers=headers,
    )
    assert assigned.json()["assignee_id"] == str(member.id)

    response = await client.patch(
        f"/v1/conversations/{conversation.id}",
        json={"assignee_id": None},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["assignee_id"] is None


async def test_a_bad_assignee_in_a_combined_patch_commits_nothing(
    client, db_session
) -> None:
    """The whole point of applying assignee before status/priority.

    ``status``/``priority`` are Pydantic-validated enums that cannot fail
    against the database once ``get_conversation`` has already succeeded;
    ``assignee_id`` is the one field whose validity is a database lookup
    (``set_assignee`` 404s on a stranger). If the route applied status
    first, this request would commit the status change and *then* 404 --
    a failed request that nevertheless mutated the resource. Re-reading
    the conversation is the load-bearing assertion: it would still pass
    with the broken ordering if it only checked the response code.
    """
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    headers, _ = await key_for(db_session, workspace, [ApiKeyScope.conversations_write])
    stranger_id = uuid.uuid4()

    response = await client.patch(
        f"/v1/conversations/{conversation.id}",
        json={"status": "resolved", "assignee_id": str(stranger_id)},
        headers=headers,
    )

    assert response.status_code == 404

    reloaded = await conversations.get_conversation(
        db_session, workspace.id, conversation.id
    )
    assert reloaded.status.value == "open"
    assert reloaded.assignee_id is None


async def test_an_empty_patch_changes_nothing(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    headers, _ = await key_for(db_session, workspace, [ApiKeyScope.conversations_write])

    response = await client.patch(
        f"/v1/conversations/{conversation.id}", json={}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["status"] == "open"


async def test_patch_on_another_workspace_answers_404(client, db_session) -> None:
    ours = await make_workspace(db_session, slug="ours")
    theirs = await make_workspace(db_session, slug="theirs")
    hidden = await make_conversation(db_session, theirs)
    headers, _ = await key_for(db_session, ours, [ApiKeyScope.conversations_write])

    response = await client.patch(
        f"/v1/conversations/{hidden.id}", json={"status": "resolved"}, headers=headers
    )

    assert response.status_code == 404


async def test_an_empty_patch_on_another_workspace_still_answers_404(
    client, db_session
) -> None:
    """An empty body must not become a way to probe which ids exist."""
    ours = await make_workspace(db_session, slug="ours")
    theirs = await make_workspace(db_session, slug="theirs")
    hidden = await make_conversation(db_session, theirs)
    headers, _ = await key_for(db_session, ours, [ApiKeyScope.conversations_write])

    response = await client.patch(
        f"/v1/conversations/{hidden.id}", json={}, headers=headers
    )

    assert response.status_code == 404


async def test_a_key_without_conversations_write_cannot_patch(
    client, db_session
) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    headers, _ = await key_for(db_session, workspace, [ApiKeyScope.conversations_read])

    response = await client.patch(
        f"/v1/conversations/{conversation.id}",
        json={"status": "resolved"},
        headers=headers,
    )

    assert response.status_code == 403


async def test_a_reply_is_queued_for_delivery_and_attributed_to_the_key(
    client, db_session
) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    headers, key = await key_for(
        db_session, workspace, [ApiKeyScope.messages_write], name="Support bot"
    )

    response = await client.post(
        f"/v1/conversations/{conversation.id}/messages",
        json={"body": "We have refunded your order."},
        headers=headers,
    )

    assert response.status_code == 201, response.text
    assert response.json()["role"] == "agent"
    assert response.json()["author_name"] == "Support bot"

    message = await db_session.scalar(
        sa.select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.sent_at.desc())
    )
    assert message.role is MessageRole.agent
    assert message.author_api_key_id == key.id
    assert message.author_user_id is None
    assert message.delivery_state is DeliveryState.queued


async def test_conversations_write_alone_cannot_reply(client, db_session) -> None:
    """The whole point of splitting the two scopes (spec D5).

    A triage integration that labels and prioritises must not be one bug
    away from mailing a customer.
    """
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    headers, _ = await key_for(db_session, workspace, [ApiKeyScope.conversations_write])

    response = await client.post(
        f"/v1/conversations/{conversation.id}/messages",
        json={"body": "Hello."},
        headers=headers,
    )

    assert response.status_code == 403
    assert "messages:write" in response.json()["error"]["message"]


async def test_a_blank_reply_is_refused(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    headers, _ = await key_for(db_session, workspace, [ApiKeyScope.messages_write])

    response = await client.post(
        f"/v1/conversations/{conversation.id}/messages",
        json={"body": "   "},
        headers=headers,
    )

    assert response.status_code == 422


async def test_replying_into_another_workspace_answers_404(client, db_session) -> None:
    ours = await make_workspace(db_session, slug="ours")
    theirs = await make_workspace(db_session, slug="theirs")
    hidden = await make_conversation(db_session, theirs)
    headers, _ = await key_for(db_session, ours, [ApiKeyScope.messages_write])

    response = await client.post(
        f"/v1/conversations/{hidden.id}/messages",
        json={"body": "Hello."},
        headers=headers,
    )

    assert response.status_code == 404


async def test_the_reply_response_is_the_reply_not_a_future_dated_inbound(
    client, db_session
) -> None:
    """The 201 body must be the message this call created.

    ``Message.sent_at`` for an inbound message is the sender's own ``Date:``
    header, which ``services/ingest`` trusts up to an hour past
    ``received_at``. A customer whose mail client runs twenty minutes fast
    therefore leaves a row that sorts *after* an agent reply stamped
    ``now()``, for as long as the skew lasts. Serialising "the last message
    by ``sent_at``" hands that customer's id, role, name and body back as
    the reply the caller just created -- deterministically, on every reply
    to that conversation, not as a race.

    It is a scope leak as well as a wrong answer: this route requires only
    ``messages:write``, which does not imply ``conversations:read`` (spec
    D5), so the body of a customer message is something this principal is
    not entitled to read at all.
    """
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    skewed = Message(
        workspace_id=workspace.id,
        conversation_id=conversation.id,
        role=MessageRole.customer,
        direction=MessageDirection.inbound,
        author_name="Priya Raman",
        to_address="support@chronon.co",
        body="Sent from a clock that runs fast.",
        sent_at=datetime.now(UTC) + timedelta(minutes=20),
    )
    db_session.add(skewed)
    await db_session.commit()
    headers, _ = await key_for(
        db_session, workspace, [ApiKeyScope.messages_write], name="Support bot"
    )

    response = await client.post(
        f"/v1/conversations/{conversation.id}/messages",
        json={"body": "We have refunded your order."},
        headers=headers,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["id"] != str(skewed.id)
    assert body["role"] == "agent"
    assert body["direction"] == "outbound"
    assert body["author_name"] == "Support bot"
    assert body["body"] == "We have refunded your order."
