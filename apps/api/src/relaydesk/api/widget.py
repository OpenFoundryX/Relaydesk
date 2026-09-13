"""Anonymous routes the embedded widget calls, addressed by widget key.

A second front door onto `relaydesk.api.public`, not new domain logic. The
KB reads below resolve the key to a workspace and then call public.py's own
route functions by slug, so the mapping from domain objects to schemas has
exactly one implementation. The difference between the two doors is only
how the workspace is named -- by key rather than by slug, so an embed
survives a workspace being renamed (spec D3).

Mounted at its own `/widget` prefix rather than under `/public`, so it adds
no fixed first path segment there and needs no entry in `RESERVED_SLUGS`.

Route order is load-bearing: FastAPI matches in declaration order, so every
fixed segment must be declared above the `{path:path}` catch-all or it is
swallowed as an article path.
"""

import json
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile, status
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import EmailStr

from relaydesk.api import public
from relaydesk.api.deps import DbSession
from relaydesk.config import get_settings
from relaydesk.email_parse.normalize import ParsedAttachment
from relaydesk.errors import Invalid, NotFound, TooManyRequests
from relaydesk.models.ai_call import AiCall, AiOutcome
from relaydesk.models.ai_config import AiConfig, DEFAULT_MODEL
from relaydesk.schemas.kb import (
    PublicArticleSummary,
    PublicCollectionOut,
    PublicNodeOut,
    PublicSearchEntryOut,
    TicketSubmittedOut,
)
from relaydesk.schemas.widget import (
    TRANSCRIPT_MAX_CHARS,
    WidgetAskIn,
    WidgetBootstrapOut,
    WidgetEventIn,
)
from relaydesk.services import (
    ai_answers,
    ai_retrieval,
    client_ip,
    kb_public,
    ratelimit,
    tickets,
    widget_keys,
    widget_origins,
    widget_sessions,
)
from relaydesk.services.ai_provider import Turn

logger = logging.getLogger(__name__)
# Kept in step with `SEPARATOR` in apps/web/components/inbox/message-body.tsx,
# which splits an escalated ticket's body on it.
_SEPARATOR_LITERAL = "--- Before contacting support ---"
# Same words, two dashes instead of three: recognisable to a person
# reading the ticket, not a match for the split above.
_SEPARATOR_DEFANGED = "-- Before contacting support --"


router = APIRouter()


@router.get("/{key}", response_model=WidgetBootstrapOut)
async def bootstrap(key: str, session: DbSession) -> WidgetBootstrapOut:
    """Everything the frame needs for its first paint, in one call.

    ``article_count`` is here rather than behind a second request because
    the empty-knowledge-base rendering (spec D7) is a different screen, not
    a different state of the same one -- fetching it later would show a
    search field for one frame and then take it away.

    It comes from ``kb_public.count()``, built on the same ``_visible()``
    predicate ``searchable()`` uses, so "the knowledge base is empty" still
    means exactly "search would find nothing", by construction rather than
    by two queries agreeing -- without paying to materialise every
    published article and its ancestor chain on the one endpoint every
    panel open hits, which is all the frame ever did with that result.
    """
    widget_key = await widget_keys.resolve(session, key)
    await widget_keys.touch(session, widget_key)
    await session.commit()
    workspace = widget_key.workspace
    article_count = await kb_public.count(session, workspace.id)

    config = await session.get(AiConfig, workspace.id)
    return WidgetBootstrapOut(
        workspace_name=workspace.name,
        monogram=workspace.monogram,
        settings=widget_key.settings,
        article_count=article_count,
        ai_enabled=bool(config and config.enabled and config.api_key),
    )


@router.get("/{key}/kb", response_model=list[PublicCollectionOut])
async def kb_index(key: str, session: DbSession) -> list[PublicCollectionOut]:
    widget_key = await widget_keys.resolve(session, key)
    return await public.read_kb_index(slug=widget_key.workspace.slug, session=session)


@router.get("/{key}/kb/search/index", response_model=list[PublicSearchEntryOut])
async def kb_search_index(key: str, session: DbSession) -> list[PublicSearchEntryOut]:
    """The whole searchable set, for scoring in the browser.

    Unused by the frame today: D8 reversed an earlier draft of that
    decision once instant search here was weighed against the loader's
    under-3-KB pitch (spec D6) -- the frame instead submits each query to
    `kb_search` below, server-side, so there is no per-keystroke request to
    avoid in the first place. This route is retained because the public
    help site already calls it, and because it is what a future
    instant-search pass over the frame would adopt for workspaces whose
    index is small enough to be worth shipping whole. It discloses nothing
    new either way -- every entry is a published, externally-scoped article
    already served in full on the public help site.
    """
    widget_key = await widget_keys.resolve(session, key)
    return await public.read_kb_search_index(
        slug=widget_key.workspace.slug, session=session
    )


@router.get("/{key}/kb/search", response_model=list[PublicArticleSummary])
async def kb_search(
    key: str, session: DbSession, q: str = ""
) -> list[PublicArticleSummary]:
    """Server-side search, for indexes too large to ship whole (spec D8)."""
    widget_key = await widget_keys.resolve(session, key)
    return await public.search_kb(slug=widget_key.workspace.slug, session=session, q=q)


@router.post("/{key}/tickets", response_model=TicketSubmittedOut, status_code=201)
async def submit(
    key: str,
    session: DbSession,
    request: Request,
    email: Annotated[EmailStr, Form()],
    message: Annotated[str, Form()],
    name: Annotated[str, Form()] = "",
    subject: Annotated[str, Form()] = "",
    company: Annotated[str, Form()] = "",
    transcript: Annotated[str, Form()] = "",
    files: Annotated[list[UploadFile] | None, File()] = None,
) -> TicketSubmittedOut:
    widget_key = await widget_keys.resolve(session, key)

    uploads = files or []
    if len(uploads) > get_settings().ticket_attachment_max_count:
        raise Invalid("Too many attachments.")

    parsed = [
        ParsedAttachment(
            filename=upload.filename or "attachment",
            content_type=upload.content_type or "application/octet-stream",
            content=await upload.read(),
            inline=False,
            content_id=None,
        )
        for upload in uploads
    ]

    tickets.validate(message, parsed)

    within_ip = await ratelimit.check(
        session,
        "tickets",
        client_ip.resolve(request),
        limit=get_settings().ticket_ip_hourly_cap,
        window=timedelta(hours=1),
    )
    if not within_ip:
        raise TooManyRequests("We could not accept that just now.")

    # The per-embed cap, on the same exception and message as the one above:
    # a caller who can tell which fired learns how to route around it.
    within_key = await ratelimit.check(
        session,
        "widget",
        str(widget_key.id),
        limit=get_settings().widget_key_hourly_cap,
        window=timedelta(hours=1),
    )
    if not within_key:
        raise TooManyRequests("We could not accept that just now.")

    # The per-email cap, on the same exception and message again.
    if await tickets.over_email_cap(session, widget_key.workspace_id, str(email)):
        raise TooManyRequests("We could not accept that just now.")

    # The honeypot, last -- after every control above has run identically
    # for this caller and a real one. `company` is hidden by the form's
    # stylesheet, so anything in it came from something filling fields
    # blindly. Answered with the same 201 a real submission gets: the only
    # difference is whether rows get written, which is the one thing the
    # caller cannot observe.
    if company.strip():
        return TicketSubmittedOut(received=True)

    # The agent must see what the visitor was already told. Answering a
    # question the AI has already answered differently is worse than never
    # having answered it (spec D8). Truncated, not refused -- see
    # `TRANSCRIPT_MAX_CHARS` -- and it is the transcript that yields, never
    # the ticket: the visitor wrote `message`, the widget only generated
    # `transcript`, and `tickets.submit` re-validates the combined body
    # against `ticket_message_max_chars`. Losing the transcript is a
    # degradation; losing the whole ticket to a length limit neither side
    # of this call chose is a failure.
    # The separator below is how the agent-facing renderer finds where the
    # visitor's own words end and the bot transcript begins, and it finds
    # the FIRST one. `message` is visitor-authored, so a visitor who typed
    # the literal themselves could move that boundary -- opening a message
    # with it left the visitor's half empty and swallowed their entire
    # request into a panel that renders collapsed, so the agent opened the
    # ticket and saw nothing. Defanged here rather than rejected: a
    # visitor must never have a ticket refused over the characters in it,
    # and the dashes are cosmetic.
    message = message.replace(_SEPARATOR_LITERAL, _SEPARATOR_DEFANGED)

    body = message
    stripped_transcript = transcript.strip()
    if stripped_transcript:
        separator = f"\n\n{_SEPARATOR_LITERAL}\n"
        room = get_settings().ticket_message_max_chars - len(message) - len(separator)
        allowed = max(0, min(TRANSCRIPT_MAX_CHARS, room))
        if allowed > 0:
            clipped = stripped_transcript[-allowed:]
            body = f"{message}{separator}{clipped}"
        # else: no room left at all -- drop the transcript entirely rather
        # than refuse the ticket itself.

        # One `AiCall` row per escalation, so a deflection query can tell
        # "asked the AI, gave up, asked a human" apart from "never asked at
        # all" -- see `ai_answers._record` for the pattern this follows.
        # Written for every non-blank `transcript`, even one dropped above
        # for lack of room: what happened is still an escalation from an
        # AI conversation, whatever became of the transcript text itself.
        config = await session.get(AiConfig, widget_key.workspace_id)
        session.add(
            AiCall(
                workspace_id=widget_key.workspace_id,
                widget_key_id=widget_key.id,
                model=config.model if config else DEFAULT_MODEL,
                input_tokens=0,
                output_tokens=0,
                cost_micros=0,
                latency_ms=0,
                outcome=AiOutcome.escalated,
            )
        )

    await tickets.submit(
        session,
        widget_key.workspace_id,
        email=str(email),
        name=name,
        subject=subject,
        message=body,
        attachments=parsed,
    )
    # Required, and easy to miss: `get_session` has no commit-on-exit and
    # there is no commit-on-success middleware, so an uncommitted flush is
    # rolled back by `AsyncSession.close()` when the request ends and the
    # ticket silently never exists. `public.py:332` does exactly this, for
    # exactly this reason.
    await session.commit()
    return TicketSubmittedOut(received=True)


@router.get("/{key}/embed-policy", response_class=PlainTextResponse)
async def embed_policy(key: str, session: DbSession) -> str:
    """The frame's ``frame-ancestors`` value, and nothing else.

    An unknown or inactive key answers ``'none'`` rather than 404: the frame
    must refuse to render either way, and a 404 here would tell a caller
    which keys exist -- the same reasoning as ``resolve()`` itself, just
    surfacing through a header instead of an error envelope.
    """
    try:
        widget_key = await widget_keys.resolve(session, key)
    except NotFound:
        return "frame-ancestors 'none'"
    return widget_origins.frame_ancestors(widget_key.allowed_origins)


@router.post("/{key}/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def record_event(
    key: str, session_id: uuid.UUID, body: WidgetEventIn, session: DbSession
) -> None:
    """Record how far one panel open got. Never fails visibly to the visitor.

    Rate-limited on the widget key, the way `submit` below is: this is
    otherwise uncapped, unauthenticated row creation, and the row being
    created is the one this whole feature exists to trust -- a caller who
    can read the customer's page source can poison the deflection baseline
    for free. A refusal here stays as silent as any other failure on this
    route; the visitor must never learn a cap exists.
    """
    widget_key = await widget_keys.resolve(session, key)

    within_key = await ratelimit.check(
        session,
        "widget_sessions",
        str(widget_key.id),
        limit=get_settings().widget_session_hourly_cap,
        window=timedelta(hours=1),
    )
    if not within_key:
        return

    await widget_sessions.record(session, widget_key, session_id, body.kind)
    # `get_session` has no commit-on-exit and nothing commits on success, so
    # an uncommitted flush is rolled back by `AsyncSession.close()` when the
    # request ends and the counter silently never moves. Two earlier routes
    # in this slice shipped exactly that defect; `public.py:332` is the
    # pattern every mutating route here follows.
    await session.commit()


@router.post("/{key}/ask")
async def ask(
    key: str, body: WidgetAskIn, session: DbSession, request: Request
) -> StreamingResponse:
    """Answer from the knowledge base, or say plainly that this degraded.

    Always 200 once the key resolves. Every failure inside is a degradation
    to the widget that already works (spec D4), not an error -- a visitor
    who asked a question should never see a stack trace, and a workspace
    that has not configured AI should see no change at all.

    That promise is enforced, not assumed: everything from the rate-limit
    check through the pre-stream half of `ai_answers.answer` runs under a
    catch-all, because an unexpected exception there is otherwise exactly
    as visible to the visitor as a genuine one -- both are a 500 through
    `main.py`'s generic handler, breaking the SSE contract Task 10 is
    built against. The exception is logged, not swallowed silently, so an
    operator can still see it; the visitor only ever sees a degraded frame.
    """
    widget_key = await widget_keys.resolve(session, key)

    try:
        # The per-address cap, ahead of the per-key one below -- same order
        # `submit` above uses, and the same reason: the key is public, so it
        # alone bounds the workspace but not any one caller. Each of these
        # calls spends the workspace's money, unlike `submit`'s rows, which
        # is why this cap exists at all rather than relying on the ticket
        # route's precedent going unfollowed here.
        within_ip = await ratelimit.check(
            session,
            "widget_ask_ip",
            client_ip.resolve(request),
            limit=get_settings().widget_ask_ip_hourly_cap,
            window=timedelta(hours=1),
        )
        if not within_ip:
            return _degraded("rate_limited")

        within = await ratelimit.check(
            session,
            "widget_ask",
            str(widget_key.id),
            limit=get_settings().widget_ask_hourly_cap,
            window=timedelta(hours=1),
        )
        if not within:
            return _degraded("rate_limited")

        history = [Turn(role=turn.role, text=turn.text) for turn in body.history]
        attempt = await ai_answers.answer(
            session,
            widget_key.workspace,
            widget_key,
            body.question.strip(),
            history=history,
        )
    except Exception:
        logger.exception("widget ask: unexpected failure before streaming")
        return _degraded("error")

    if attempt.degraded:
        return _degraded(attempt.reason or "unavailable")

    async def events() -> AsyncIterator[str]:
        assert attempt.stream is not None
        answer_text = ""
        try:
            async for chunk in attempt.stream:
                answer_text += chunk
                yield f"event: text\ndata: {json.dumps({'text': chunk})}\n\n"
        except Exception:
            # Anything other than `ProviderUnavailable` -- that one is
            # already caught inside `ai_answers.stream`, which ends the
            # generator cleanly rather than raising. A client mid-stream
            # cannot tell an exception here from a network drop unless
            # this still ends with a `done` frame, the same as every
            # other failure this route reports (Task 10 depends on it).
            logger.exception("widget ask: mid-stream failure")
            yield f"event: done\ndata: {json.dumps({'outcome': 'degraded'})}\n\n"
            return

        # `attempt.sources` is empty in exactly two shapes: retrieval found
        # nothing, so `ai_answers.answer` called the model in clarify-only
        # mode (see its docstring) -- the citation concept does not apply,
        # and any non-blank text back is `clarified`, telling the frontend
        # not to offer a ticket over a question the bot just asked back.
        # Blank text back (a stream that produced nothing) has no home in
        # the three named outcomes and falls through to `degraded`, the
        # same as every other unnamed shape on this route.
        if attempt.sources:
            cited = ai_retrieval.resolve_citations(answer_text, attempt.sources)
            outcome = "answered" if cited else "refused"
        elif answer_text.strip():
            cited = []
            outcome = "clarified"
        else:
            cited = []
            outcome = "degraded"
        payload = {
            "outcome": outcome,
            "citations": [
                # `number` travels with the citation because the answer text
                # carries inline `[n]` markers, and without it the browser
                # cannot tell which article `[4]` meant -- it would render a
                # dangling number beside a list of links it cannot join to.
                {"number": source.number, "title": source.title, "path": source.path}
                for source in cited
            ],
        }
        yield f"event: done\ndata: {json.dumps(payload)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


def _degraded(reason: str) -> StreamingResponse:
    """One terminal event and nothing else.

    `reason` is not read here, and not sent to the client -- the whole
    point is that a visitor cannot tell a rate limit from an unconfigured
    workspace from an outage. It exists purely so each call site names,
    for a reader, what it is degrading because of; it is not written to
    an audit row by this function (the caller already has, or never had
    one to write -- rate limiting has no `AiCall` row at all).
    """

    async def once() -> AsyncIterator[str]:
        yield f"event: done\ndata: {json.dumps({'outcome': 'degraded'})}\n\n"

    return StreamingResponse(once(), media_type="text/event-stream")


# Declared last: `{path:path}` matches anything, including the fixed
# segments above, so moving it up silently 404s them as missing articles.
@router.get("/{key}/kb/{path:path}", response_model=PublicNodeOut)
async def kb_node(key: str, path: str, session: DbSession) -> PublicNodeOut:
    widget_key = await widget_keys.resolve(session, key)
    return await public.read_kb_path(
        slug=widget_key.workspace.slug, path=path, session=session
    )
