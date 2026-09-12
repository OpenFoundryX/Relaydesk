from contextlib import asynccontextmanager

from unittest import mock

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from relaydesk.models.ai_call import AiCall, AiOutcome
from relaydesk.models.ai_config import AiConfig
from relaydesk.services import widget_keys
from relaydesk.services import ai_answers
from relaydesk.services.ai_answers import Attempt, answer
from relaydesk.services.ai_provider import (
    Completion,
    FakeProvider,
    ProviderUnavailable,
)
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


async def test_the_stream_reaches_for_its_own_session(db_session) -> None:
    """The stream's audit row must not go through the request's session.

    A StreamingResponse body runs after the handler returns and after
    FastAPI tears `get_session` down, so the request's session is closed by
    then -- a write borrowing it would fail at the end of a stream the
    visitor has already read, and no test under a shared-session fixture
    would show it.

    This observes the reach for `async_session_factory` rather than its
    consequences. An earlier version asserted an `IntegrityError` instead,
    on the reasoning that the real factory points at the `relaydesk`
    database while the suite runs against `relaydesk_test`. That worked,
    but it pinned the guarantee to an environmental coincidence -- the real
    database happening to be migrated by the api container's entrypoint --
    rather than to the mechanism. A spy says the same thing and keeps
    saying it on a machine configured differently.
    """
    workspace, config, key = await _setup(db_session)
    await _publish(db_session, workspace)

    with mock.patch.object(
        ai_answers, "async_session_factory", wraps=_audit_sessions(db_session)
    ) as factory:
        attempt = await answer(
            db_session, workspace, key, "refund",
            provider=FakeProvider(chunks=["Within 14 days [1]."]),
        )
        [chunk async for chunk in attempt.stream]

    assert factory.called, "the stream borrowed the request's session"


async def test_a_provider_that_fails_after_yielding_still_records_once(
    db_session,
) -> None:
    """Partial text reaches the visitor, and exactly one row is still written.

    `complete()` may raise after chunks have gone out -- a mid-stream error,
    or the refusal check that runs once the stream ends. The visitor keeps
    what they already saw; the audit must not end up with zero rows or two.
    """

    class YieldsThenFails:
        def __init__(self):
            self._usage = Completion()

        async def complete(self, *, system, question, model):
            yield "Within 14 days"
            raise ProviderUnavailable("dropped mid-stream")

        def usage(self):
            return self._usage

    workspace, config, key = await _setup(db_session)
    await _publish(db_session, workspace)

    attempt = await answer(
        db_session, workspace, key, "refund", provider=YieldsThenFails(),
        audit_sessions=_audit_sessions(db_session),
    )
    received = [chunk async for chunk in attempt.stream]

    assert received == ["Within 14 days"], "the visitor lost text they had already seen"
    rows = list(await db_session.scalars(sa.select(AiCall)))
    assert len(rows) == 1
    assert rows[0].outcome == AiOutcome.degraded
    assert rows[0].reason == "provider_unavailable"


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
