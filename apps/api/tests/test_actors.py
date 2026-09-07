import uuid

import sqlalchemy as sa

from relaydesk.models import ActivityEvent, ApiKeyScope, ConversationStatus, Message
from relaydesk.services import api_keys, conversations
from relaydesk.services.actors import Actor
from tests.factories import make_conversation, make_member, make_workspace


def test_an_actor_for_a_user_carries_the_users_name_and_id() -> None:
    from relaydesk.models import User

    user = User(email="sara@relaydesk.dev", name="Sara Ali", monogram="SA")
    # `id` is a column default applied at flush, not construction, so an
    # unflushed User's id is None. Assign one directly so this stays a pure
    # unit test of Actor rather than needing a session round-trip.
    user.id = uuid.uuid4()
    actor = Actor.for_user(user)

    assert actor.name == "Sara Ali"
    assert actor.user_id == user.id
    assert actor.api_key_id is None


async def test_an_actor_for_a_key_carries_the_keys_name(db_session) -> None:
    workspace = await make_workspace(db_session)
    _, key = await api_keys.mint(
        db_session,
        workspace.id,
        name="Zapier integration",
        scopes=[ApiKeyScope.conversations_write],
        created_by_user_id=None,
    )

    actor = Actor.for_key(key)

    assert actor.name == "Zapier integration"
    assert actor.api_key_id == key.id
    assert actor.user_id is None


async def test_a_key_driven_status_change_is_attributed_to_the_key(
    db_session,
) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    _, key = await api_keys.mint(
        db_session,
        workspace.id,
        name="Zapier integration",
        scopes=[ApiKeyScope.conversations_write],
        created_by_user_id=None,
    )

    await conversations.set_status(
        db_session,
        workspace.id,
        conversation.id,
        ConversationStatus.resolved,
        Actor.for_key(key),
    )

    event = await db_session.scalar(
        sa.select(ActivityEvent)
        .where(ActivityEvent.conversation_id == conversation.id)
        .order_by(ActivityEvent.at.desc())
    )
    assert event.actor_user_id is None
    assert event.actor_api_key_id == key.id
    assert event.actor_name == "Zapier integration"


async def test_a_user_driven_status_change_still_names_the_user(db_session) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    conversation = await make_conversation(db_session, workspace)

    await conversations.set_status(
        db_session,
        workspace.id,
        conversation.id,
        ConversationStatus.resolved,
        Actor.for_user(user),
    )

    event = await db_session.scalar(
        sa.select(ActivityEvent)
        .where(ActivityEvent.conversation_id == conversation.id)
        .order_by(ActivityEvent.at.desc())
    )
    assert event.actor_user_id == user.id
    assert event.actor_api_key_id is None


async def test_a_key_driven_reply_is_attributed_to_the_key(db_session) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    _, key = await api_keys.mint(
        db_session,
        workspace.id,
        name="Zapier integration",
        scopes=[ApiKeyScope.messages_write],
        created_by_user_id=None,
    )

    await conversations.add_reply(
        db_session, workspace.id, conversation.id, "On its way.", Actor.for_key(key)
    )

    message = await db_session.scalar(
        sa.select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.sent_at.desc())
    )
    assert message.author_user_id is None
    assert message.author_api_key_id == key.id
    assert message.author_name == "Zapier integration"
