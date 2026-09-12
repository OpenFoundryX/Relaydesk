import sqlalchemy as sa

from relaydesk.models.ai_call import AiCall, AiOutcome
from relaydesk.models.ai_config import AiConfig
from relaydesk.services import widget_keys
from relaydesk.services.ai_answers import Attempt, answer
from relaydesk.services.ai_provider import FakeProvider
from tests.factories import make_workspace


async def _setup(db_session, *, enabled=True, budget=200_000):
    workspace = await make_workspace(db_session)
    config = AiConfig(
        workspace_id=workspace.id,
        api_key="sk-test",
        enabled=enabled,
        daily_token_budget=budget,
    )
    db_session.add(config)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    await db_session.flush()
    return workspace, config, key


async def test_no_key_degrades_without_calling_anything(db_session) -> None:
    workspace, config, key = await _setup(db_session)
    config.api_key = None
    await db_session.flush()

    attempt = await answer(db_session, workspace, key, "how do refunds work")

    assert attempt.degraded is True
    assert attempt.reason == "not_configured"


async def test_empty_knowledge_base_degrades_without_calling_the_model(db_session) -> None:
    """Retrieval is the gate. A model with no sources answers from training data."""
    workspace, config, key = await _setup(db_session)
    provider = FakeProvider(chunks=["should never run"])

    attempt = await answer(
        db_session, workspace, key, "how do refunds work", provider=provider
    )

    assert attempt.degraded is True
    assert attempt.reason == "no_sources"
    assert provider.usage().output_tokens == 0


async def test_exhausted_budget_degrades(db_session) -> None:
    workspace, config, key = await _setup(db_session, budget=1)
    db_session.add(
        AiCall(
            workspace_id=workspace.id,
            model="claude-opus-5",
            input_tokens=10,
            output_tokens=0,
            cost_micros=0,
            latency_ms=1,
            outcome=AiOutcome.answered,
        )
    )
    await db_session.flush()

    attempt = await answer(db_session, workspace, key, "anything")

    assert attempt.degraded is True
    assert attempt.reason == "over_budget"


async def test_every_degradation_writes_exactly_one_audit_row(db_session) -> None:
    workspace, config, key = await _setup(db_session)
    config.api_key = None
    await db_session.flush()

    await answer(db_session, workspace, key, "how do refunds work")

    rows = list(await db_session.scalars(sa.select(AiCall)))
    assert len(rows) == 1
    assert rows[0].outcome == AiOutcome.degraded
    assert rows[0].reason == "not_configured"


async def _publish(db_session, workspace):
    """One published article, so retrieval has something to find.

    Follow `tests/test_kb_public.py` if these constructors have moved; the
    requirement is only that the article is published and externally
    scoped, because `_visible()` is what retrieval filters on.
    """
    from relaydesk.models.kb import ArticleStatus, KbArticle, KbCategory, KbScope

    category = KbCategory(
        workspace_id=workspace.id, name="Billing", slug="billing",
        scope=KbScope.external, position=0,
    )
    db_session.add(category)
    await db_session.flush()
    article = KbArticle(
        workspace_id=workspace.id, category_id=category.id,
        title="Requesting a refund", slug="refunds",
        excerpt="We refund any plan in full within 14 days of a charge.",
        doc={"type": "doc", "content": []},
        status=ArticleStatus.published,
    )
    db_session.add(article)
    await db_session.flush()
    return article


async def test_a_provider_failure_mid_stream_is_recorded_and_silent(db_session) -> None:
    workspace, config, key = await _setup(db_session)
    await _publish(db_session, workspace)

    attempt = await answer(
        db_session, workspace, key, "refund", provider=FakeProvider(fails=True)
    )
    assert attempt.degraded is False  # retrieval succeeded; the failure is downstream
    assert [chunk async for chunk in attempt.stream] == []

    rows = list(await db_session.scalars(sa.select(AiCall)))
    assert len(rows) == 1
    assert rows[0].outcome == AiOutcome.degraded
    assert rows[0].reason == "provider_unavailable"


async def test_a_cited_answer_is_recorded_as_answered(db_session) -> None:
    workspace, config, key = await _setup(db_session)
    await _publish(db_session, workspace)

    attempt = await answer(
        db_session, workspace, key, "refund",
        provider=FakeProvider(chunks=["Within 14 days [1]."]),
    )
    text = "".join([chunk async for chunk in attempt.stream])

    assert "[1]" in text
    row = await db_session.scalar(sa.select(AiCall))
    assert row.outcome == AiOutcome.answered


async def test_an_uncited_answer_is_recorded_as_refused(db_session) -> None:
    """No citation means nothing to link, which is indistinguishable from not knowing."""
    workspace, config, key = await _setup(db_session)
    await _publish(db_session, workspace)

    attempt = await answer(
        db_session, workspace, key, "refund",
        provider=FakeProvider(chunks=["I am not sure."]),
    )
    [chunk async for chunk in attempt.stream]

    row = await db_session.scalar(sa.select(AiCall))
    assert row.outcome == AiOutcome.refused
    assert row.reason == "no_citation"
