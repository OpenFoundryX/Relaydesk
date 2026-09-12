from contextlib import asynccontextmanager

from unittest import mock

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from relaydesk.models.ai_call import AiCall, AiOutcome
from relaydesk.models.ai_config import AiConfig
from relaydesk.services import widget_keys
from relaydesk.services.ai_answers import Attempt, answer
from relaydesk.services.ai_provider import FakeProvider
from tests.factories import make_workspace


def _audit_sessions(session):
    """Hand the streaming generator's audit write the test's own session.

    In production ``stream()`` opens a fresh session, because it outlives
    the request (see ``ai_answers.answer``'s docstring). Under this
    fixture nothing the test does is committed, so a fresh session cannot
    see the workspace the test just created -- the audit insert fails on
    its foreign key. Injecting the test session here keeps assertions
    about WHAT ``stream()`` recorded meaningful for the tests that are not
    about the session seam itself;
    ``test_the_stream_audit_write_does_not_borrow_the_request_session``
    below is the one that exercises the real seam.
    """

    @asynccontextmanager
    async def factory():
        yield session

    return factory


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

    attempt = await answer(
        db_session, workspace, key, "how do refunds work",
    )

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

    attempt = await answer(
        db_session, workspace, key, "anything",
    )

    assert attempt.degraded is True
    assert attempt.reason == "over_budget"


async def test_every_degradation_writes_exactly_one_audit_row(db_session) -> None:
    workspace, config, key = await _setup(db_session)
    config.api_key = None
    await db_session.flush()

    await answer(
        db_session, workspace, key, "how do refunds work",
    )

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
        db_session, workspace, key, "refund", provider=FakeProvider(fails=True),
        audit_sessions=_audit_sessions(db_session),
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
        audit_sessions=_audit_sessions(db_session),
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
        audit_sessions=_audit_sessions(db_session),
    )
    [chunk async for chunk in attempt.stream]

    row = await db_session.scalar(sa.select(AiCall))
    assert row.outcome == AiOutcome.refused
    assert row.reason == "no_citation"


async def test_the_stream_audit_write_does_not_borrow_the_request_session(
    db_session,
) -> None:
    """The stream's audit row must outlive the request, so it is written on
    its own session -- not the pre-stream degrade paths, which run inside
    the handler while the request's session is still open and correctly
    use it.

    `get_session` has no commit on exit, and the streaming generator runs
    after FastAPI has torn it down -- so a row merely added to the
    request's session would be rolled back, and the module's promise that
    every exit writes exactly one `AiCall` row would be false.

    Asserting that structurally is awkward, because a shared-session
    fixture cannot see the difference: both designs leave a visible row.
    This test uses the test harness's own separation as the instrument
    instead. Retrieval must succeed here (hence `_publish`) so the attempt
    reaches `stream()` rather than degrading beforehand.

    Called WITHOUT the `audit_sessions` seam, the stream's write goes
    through the real `async_session_factory`, which is built from
    `settings.database_url` and therefore connects to the `relaydesk`
    database -- while this test runs against `relaydesk_test` (see
    `conftest.TEST_DATABASE`). The workspace `_setup` just created does not
    exist over there at all, so the insert fails its foreign key the moment
    the stream is consumed.

    That failure IS the evidence, and it is evidence of exactly one thing:
    the write did not go through `db_session`. Revert the fix -- have
    `stream()` close over `session` again -- and `pytest.raises` would not
    fire; the row would land unremarkably in `db_session`. Note the
    mechanism is the two DATABASES diverging, not merely two transactions;
    committing this test's setup would not make the row visible to the
    other one.
    """
    workspace, config, key = await _setup(db_session)
    await _publish(db_session, workspace)

    attempt = await answer(
        db_session, workspace, key, "refund",
        provider=FakeProvider(chunks=["Within 14 days [1]."]),
    )
    assert attempt.degraded is False

    with pytest.raises(IntegrityError):
        [chunk async for chunk in attempt.stream]


async def test_a_degrade_commits_its_audit_row(db_session) -> None:
    """`degrade()` must commit, not merely add.

    `get_session` has no commit on exit, so a row only added to the
    request's session is rolled back when the request ends -- and
    `not_configured`, `over_budget` and `no_sources` are the exits a real
    deployment hits most. Slice 8 shipped this exact defect: console routes
    that added rows and never committed, with a green suite.

    Committed-ness is not observable under a fixture that rolls everything
    back, so this observes the call instead. That is testing an
    implementation detail on purpose: "this must commit" is a statement
    about the call, and it is the only assertion that fails when the commit
    is removed.
    """
    workspace, config, key = await _setup(db_session)
    config.api_key = None
    await db_session.flush()

    with mock.patch.object(
        db_session, "commit", wraps=db_session.commit
    ) as committed:
        attempt = await answer(db_session, workspace, key, "how do refunds work")

    assert attempt.degraded is True
    assert committed.called, "the degrade row was added but never committed"
