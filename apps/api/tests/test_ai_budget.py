from datetime import UTC, datetime, timedelta

from relaydesk.models.ai_call import AiCall, AiOutcome
from relaydesk.models.ai_config import AiConfig
from relaydesk.services.ai_budget import within_budget
from tests.factories import make_workspace


async def _spend(db_session, workspace_id, tokens: int, *, days_ago: int = 0) -> None:
    call = AiCall(
        workspace_id=workspace_id,
        model="claude-opus-5",
        input_tokens=tokens,
        output_tokens=0,
        cost_micros=0,
        latency_ms=1,
        outcome=AiOutcome.answered,
    )
    db_session.add(call)
    await db_session.flush()
    if days_ago:
        call.created_at = datetime.now(UTC) - timedelta(days=days_ago)
        await db_session.flush()


async def test_a_fresh_workspace_is_within_budget(db_session) -> None:
    workspace = await make_workspace(db_session)
    config = AiConfig(workspace_id=workspace.id, daily_token_budget=1000)
    db_session.add(config)
    await db_session.flush()

    assert await within_budget(db_session, config) is True


async def test_spending_the_budget_closes_it(db_session) -> None:
    workspace = await make_workspace(db_session)
    config = AiConfig(workspace_id=workspace.id, daily_token_budget=1000)
    db_session.add(config)
    await db_session.flush()
    await _spend(db_session, workspace.id, 1000)

    assert await within_budget(db_session, config) is False


async def test_yesterdays_spend_does_not_count(db_session) -> None:
    """A daily ceiling that never rolls over is not a daily ceiling."""
    workspace = await make_workspace(db_session)
    config = AiConfig(workspace_id=workspace.id, daily_token_budget=1000)
    db_session.add(config)
    await db_session.flush()
    await _spend(db_session, workspace.id, 5000, days_ago=2)

    assert await within_budget(db_session, config) is True


async def test_another_workspace_spend_does_not_count(db_session) -> None:
    one = await make_workspace(db_session, slug="one")
    two = await make_workspace(db_session, slug="two")
    config = AiConfig(workspace_id=one.id, daily_token_budget=1000)
    db_session.add(config)
    await db_session.flush()
    await _spend(db_session, two.id, 5000)

    assert await within_budget(db_session, config) is True
