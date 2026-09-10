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

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import EmailStr

from relaydesk.api import public
from relaydesk.api.deps import DbSession
from relaydesk.config import get_settings
from relaydesk.email_parse.normalize import ParsedAttachment
from relaydesk.errors import Invalid, NotFound, TooManyRequests
from relaydesk.schemas.kb import (
    PublicArticleSummary,
    PublicCollectionOut,
    PublicNodeOut,
    PublicSearchEntryOut,
    TicketSubmittedOut,
)
from relaydesk.schemas.widget import WidgetBootstrapOut
from relaydesk.services import (
    client_ip,
    kb_public,
    ratelimit,
    tickets,
    widget_keys,
    widget_origins,
)

router = APIRouter()


@router.get("/{key}", response_model=WidgetBootstrapOut)
async def bootstrap(key: str, session: DbSession) -> WidgetBootstrapOut:
    """Everything the frame needs for its first paint, in one call.

    ``article_count`` is here rather than behind a second request because
    the empty-knowledge-base rendering (spec D7) is a different screen, not
    a different state of the same one -- fetching it later would show a
    search field for one frame and then take it away.

    It is the length of ``searchable()`` rather than its own COUNT query so
    that "the knowledge base is empty" means exactly "search would find
    nothing", by construction rather than by two queries agreeing.
    """
    widget_key = await widget_keys.resolve(session, key)
    await widget_keys.touch(session, widget_key)
    await session.commit()
    workspace = widget_key.workspace
    entries = await kb_public.searchable(session, workspace.id)

    return WidgetBootstrapOut(
        workspace_name=workspace.name,
        monogram=workspace.monogram,
        settings=widget_key.settings,
        article_count=len(entries),
    )


@router.get("/{key}/kb", response_model=list[PublicCollectionOut])
async def kb_index(key: str, session: DbSession) -> list[PublicCollectionOut]:
    widget_key = await widget_keys.resolve(session, key)
    return await public.read_kb_index(slug=widget_key.workspace.slug, session=session)


@router.get("/{key}/kb/search/index", response_model=list[PublicSearchEntryOut])
async def kb_search_index(key: str, session: DbSession) -> list[PublicSearchEntryOut]:
    """The whole searchable set, fetched once and searched in the browser.

    This is what removes search from the rate-limit surface entirely (spec
    D8). It discloses nothing new -- every entry is a published,
    externally-scoped article already served in full on the public help site.
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

    await tickets.submit(
        session,
        widget_key.workspace_id,
        email=str(email),
        name=name,
        subject=subject,
        message=message,
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


# Declared last: `{path:path}` matches anything, including the fixed
# segments above, so moving it up silently 404s them as missing articles.
@router.get("/{key}/kb/{path:path}", response_model=PublicNodeOut)
async def kb_node(key: str, path: str, session: DbSession) -> PublicNodeOut:
    widget_key = await widget_keys.resolve(session, key)
    return await public.read_kb_path(
        slug=widget_key.workspace.slug, path=path, session=session
    )
