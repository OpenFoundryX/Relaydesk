"""One answer attempt, from question to citations, with every exit recorded.

The order here is the design. Retrieval gates the model; the budget gates
the call; the provider's failure and its refusal are the same outcome to a
visitor; and every path -- including the ones that never reach a provider --
writes exactly one ``AiCall`` row, because a deflection number computed from
a table with holes in it is worse than no number.

Every failure degrades to the widget that already works (spec D4). None of
them is an error, and none of them tells the visitor why: that a workspace
has exhausted its AI budget is not a visitor's business.
"""

import time
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.db.session import async_session_factory
from relaydesk.models.ai_call import AiCall, AiOutcome
from relaydesk.models.ai_config import AiConfig
from relaydesk.models.widget_key import WidgetKey
from relaydesk.models.workspace import Workspace
from relaydesk.services import ai_budget, ai_redact, ai_retrieval
from relaydesk.services.ai_provider import Provider, ProviderUnavailable, for_config
from relaydesk.services.ai_retrieval import Source

SYSTEM = """You answer questions for {workspace} using only the numbered \
help articles below. If they do not contain the answer, say so plainly in \
one sentence and do not guess.

Cite every article you use as [n], matching its number. Never cite a number \
that is not listed. Keep the answer under 120 words.

{context}"""


@dataclass
class Attempt:
    """What came of one question.

    ``degraded`` is checked before streaming begins, which is why this is an
    object rather than a generator: a generator cannot report that there is
    nothing to stream without being started first.
    """

    degraded: bool
    reason: str | None = None
    stream: AsyncIterator[str] | None = None
    sources: list[Source] = field(default_factory=list)


async def _record(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    widget_key_id: uuid.UUID | None,
    *,
    model: str,
    outcome: AiOutcome,
    reason: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    latency_ms: int = 0,
) -> None:
    session.add(
        AiCall(
            workspace_id=workspace_id,
            widget_key_id=widget_key_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_micros=0,
            latency_ms=latency_ms,
            outcome=outcome,
            reason=reason,
        )
    )
    await session.flush()


async def answer(
    session: AsyncSession,
    workspace: Workspace,
    widget_key: WidgetKey,
    question: str,
    *,
    provider: Provider | None = None,
    audit_sessions: Callable[[], AbstractAsyncContextManager[AsyncSession]] | None = None,
) -> Attempt:
    """Answer from the knowledge base, or say why this attempt degraded.

    ``audit_sessions`` is a seam, defaulting to the real session factory.
    The streaming generator cannot borrow the request's session (see
    ``stream`` below), so it opens its own; a test that wants to observe
    the audit row inside its own uncommitted transaction passes a factory
    that hands back the test session instead. Same reason ``provider`` is
    injectable: the alternative is a module that can only be exercised
    against live infrastructure.
    """
    audit_factory = audit_sessions or async_session_factory
    config = await session.get(AiConfig, workspace.id)
    model = config.model if config else "claude-opus-5"

    async def degrade(reason: str) -> Attempt:
        """Record the degrade, commit it, and hand back the reason.

        **This commits**, on the request's own session, for the same reason
        ``ratelimit.check`` does: ``get_session`` rolls back any session
        that ends without an explicit commit, so a row merely added here
        would vanish when the request ends. ``not_configured``,
        ``over_budget`` and ``no_sources`` are the exits a real deployment
        hits most often, and a deflection table missing exactly those is
        worse than no table.

        The request's session rather than a fresh one because this runs
        INSIDE the handler, while that session is still open -- unlike
        ``stream()`` below, which outlives the request and therefore cannot
        borrow it.
        """
        await _record(
            session,
            workspace.id,
            widget_key.id,
            model=model,
            outcome=AiOutcome.degraded,
            reason=reason,
        )
        await session.commit()
        return Attempt(degraded=True, reason=reason)

    if config is None:
        return await degrade("not_configured")

    resolved = provider or for_config(config)
    if resolved is None:
        return await degrade("not_configured")

    if not await ai_budget.within_budget(session, config):
        return await degrade("over_budget")

    if await ai_budget.breaker_open(session, workspace.id):
        return await degrade("breaker_open")

    sources = await ai_retrieval.retrieve(session, workspace.id, question)
    if not sources:
        return await degrade("no_sources")

    # Skipped when the workspace points at inference it hosts itself: the
    # text never leaves their deployment, and redacting it would cost
    # answer quality for nothing (spec D6).
    asked = question if config.base_url else ai_redact.redact(question)
    system = SYSTEM.format(
        workspace=workspace.name, context=ai_retrieval.render_context(sources)
    )

    started = time.monotonic()

    async def stream() -> AsyncIterator[str]:
        """The answer, streamed, with its audit row written at the end.

        The two writes below each open their own session rather than
        closing over the request's. This generator is handed to a
        ``StreamingResponse``, whose body runs AFTER the handler has
        returned and after FastAPI has torn down ``get_session`` -- so the
        request's session is closed by the time the stream ends. Borrowing
        it would fail at the end of a stream the visitor has already read,
        and no test under the shared-session fixture would show it.

        The degrade paths above this point run inside the handler, while
        the request's session is still open, and correctly use it.
        """
        try:
            async for chunk in resolved.complete(
                system=system, question=asked, model=model
            ):
                yield chunk
        except ProviderUnavailable:
            # Its own session, not the request's -- see the docstring above.
            async with audit_factory() as audit:
                await _record(
                    audit,
                    workspace.id,
                    widget_key.id,
                    model=model,
                    outcome=AiOutcome.degraded,
                    reason="provider_unavailable",
                    latency_ms=int((time.monotonic() - started) * 1000),
                )
                await audit.commit()
            return

        usage = resolved.usage()
        cited = ai_retrieval.resolve_citations(usage.text, sources)
        async with audit_factory() as audit:
            await _record(
                audit,
                workspace.id,
                widget_key.id,
                model=model,
                outcome=AiOutcome.answered if cited else AiOutcome.refused,
                reason=None if cited else "no_citation",
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                latency_ms=int((time.monotonic() - started) * 1000),
            )
            await audit.commit()

    return Attempt(degraded=False, stream=stream(), sources=sources)
