import sqlalchemy as sa

from relaydesk.models.ai_call import AiCall, AiOutcome
from relaydesk.services import widget_keys
from tests.factories import make_workspace


async def test_cost_is_integer_micros(db_session) -> None:
    """Money in a float is a rounding argument waiting to happen."""
    workspace = await make_workspace(db_session)
    db_session.add(
        AiCall(
            workspace_id=workspace.id,
            model="claude-opus-5",
            input_tokens=1200,
            output_tokens=300,
            cost_micros=13_500,
            latency_ms=1840,
            outcome=AiOutcome.answered,
        )
    )
    await db_session.flush()

    stored = await db_session.scalar(sa.select(AiCall.cost_micros))
    assert stored == 13_500
    assert isinstance(stored, int)


async def test_revoking_an_embed_keeps_the_record_of_what_it_spent(db_session) -> None:
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    db_session.add(
        AiCall(
            workspace_id=workspace.id,
            widget_key_id=key.id,
            model="claude-opus-5",
            input_tokens=10,
            output_tokens=5,
            cost_micros=100,
            latency_ms=200,
            outcome=AiOutcome.answered,
        )
    )
    await db_session.flush()

    await widget_keys.delete(db_session, workspace.id, key.id)

    # Expunge all objects to ensure a genuine row load from the database,
    # not a cached identity-mapped object. Without this, the test would pass
    # by accident if the object was garbage-collected before re-select.
    db_session.expunge_all()

    row = await db_session.scalar(sa.select(AiCall))
    assert row is not None
    assert row.widget_key_id is None
