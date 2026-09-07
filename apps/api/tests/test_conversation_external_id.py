import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from relaydesk.models import Conversation
from tests.factories import make_conversation, make_workspace


async def test_external_id_defaults_to_null_and_metadata_to_empty(db_session) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)

    stored = await db_session.scalar(
        sa.select(Conversation).where(Conversation.id == conversation.id)
    )

    assert stored.external_id is None
    assert stored.meta == {}


async def test_metadata_round_trips_as_json(db_session) -> None:
    workspace = await make_workspace(db_session)
    conversation = await make_conversation(db_session, workspace)
    conversation.meta = {"order_id": "ord_456", "plan": "growth", "seats": 12}
    await db_session.commit()

    stored = await db_session.scalar(
        sa.select(Conversation).where(Conversation.id == conversation.id)
    )

    assert stored.meta == {"order_id": "ord_456", "plan": "growth", "seats": 12}


async def test_one_external_id_per_workspace(db_session) -> None:
    workspace = await make_workspace(db_session)
    first = await make_conversation(db_session, workspace, subject="First")
    second = await make_conversation(db_session, workspace, subject="Second")
    first.external_id = "ticket-123"
    await db_session.commit()

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            second.external_id = "ticket-123"
            await db_session.flush()


async def test_two_workspaces_may_use_the_same_external_id(db_session) -> None:
    ours = await make_workspace(db_session, slug="ours")
    theirs = await make_workspace(db_session, slug="theirs")
    mine = await make_conversation(db_session, ours)
    yours = await make_conversation(db_session, theirs)

    mine.external_id = "ticket-123"
    yours.external_id = "ticket-123"
    await db_session.commit()  # does not raise


async def test_many_conversations_may_have_no_external_id(db_session) -> None:
    """The index is partial for exactly this reason.

    Postgres treats NULLs as distinct, so a plain unique index would appear
    to constrain while permitting unlimited duplicate (workspace, NULL)
    rows -- which is every conversation that did not arrive through the API.
    """
    workspace = await make_workspace(db_session)
    for index in range(3):
        await make_conversation(db_session, workspace, subject=f"Ticket {index}")

    total = await db_session.scalar(
        sa.select(sa.func.count())
        .select_from(Conversation)
        .where(
            Conversation.workspace_id == workspace.id,
            Conversation.external_id.is_(None),
        )
    )
    assert total == 3
