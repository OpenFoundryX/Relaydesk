"""Anonymous, read-only routes for the customer-facing portal.

Everything here is reachable without a session by design -- a published
knowledge base is public. That makes the rule for this module simple and
absolute: return display information and published content, never anything
about tickets, members, plans, or usage.
"""

import uuid
from datetime import timedelta
from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, File, Form, Request, Response, UploadFile
from pydantic import EmailStr

from relaydesk.api.deps import DbSession
from relaydesk.config import get_settings
from relaydesk.email_parse.normalize import ParsedAttachment
from relaydesk.errors import Invalid, NotFound, TooManyRequests
from relaydesk.models.kb import KbArticle
from relaydesk.models.workspace import Workspace
from relaydesk.schemas.kb import (
    PublicArticleOut,
    PublicArticleSummary,
    PublicCategoryOut,
    PublicWorkspaceOut,
    TicketSubmittedOut,
)
from relaydesk.services import client_ip, kb_public, ratelimit, tickets
from relaydesk.services.attachments import INLINE_SAFE_TYPES, safe_content_type
from relaydesk.services.workspaces import RESERVED_SLUGS

router = APIRouter()


async def resolve_workspace(session: DbSession, slug: str) -> Workspace:
    """Shared by every public route. A reserved label is a 404, not a lookup."""
    if slug.lower() in RESERVED_SLUGS:
        raise NotFound("No such workspace.")
    workspace = await session.scalar(
        sa.select(Workspace).where(Workspace.slug == slug.lower())
    )
    if workspace is None:
        raise NotFound("No such workspace.")
    return workspace


# Every route below adds one more fixed first path segment under `/public`
# (`workspaces`, `kb` reads through `{slug}/kb...`, ...). Each one is a
# potential collision with a workspace slug that happens to match it -- see
# `RESERVED_SLUGS` in `relaydesk.services.workspaces`, which both
# `resolve_workspace` above and `create_workspace` consult. Any new fixed
# first segment added here must be added to that set too.
@router.get("/workspaces/{slug}", response_model=PublicWorkspaceOut)
async def read_workspace(slug: str, session: DbSession) -> PublicWorkspaceOut:
    workspace = await resolve_workspace(session, slug)
    return PublicWorkspaceOut(name=workspace.name, monogram=workspace.monogram)


def _article_summary(article: KbArticle) -> PublicArticleSummary:
    return PublicArticleSummary(
        id=str(article.id),
        title=article.title,
        slug=article.slug,
        excerpt=article.excerpt,
    )


def _article_out(article: KbArticle) -> PublicArticleOut:
    return PublicArticleOut(
        id=str(article.id),
        title=article.title,
        slug=article.slug,
        excerpt=article.excerpt,
        doc=article.doc,
        published_at=article.published_at,
    )


@router.get("/{slug}/kb", response_model=list[PublicCategoryOut])
async def read_kb_index(slug: str, session: DbSession) -> list[PublicCategoryOut]:
    workspace = await resolve_workspace(session, slug)
    rows = await kb_public.index(session, workspace.id)
    return [
        PublicCategoryOut(
            id=str(category.id),
            name=category.name,
            slug=category.slug,
            articles=[_article_summary(article) for article in articles],
        )
        for category, articles in rows
    ]


@router.get("/{slug}/kb/search", response_model=list[PublicArticleSummary])
async def search_kb(
    slug: str, session: DbSession, q: str = ""
) -> list[PublicArticleSummary]:
    workspace = await resolve_workspace(session, slug)
    articles = await kb_public.search(session, workspace.id, q)
    return [_article_summary(article) for article in articles]


@router.get("/{slug}/kb/images/{image_id}")
async def read_kb_image(slug: str, image_id: uuid.UUID, session: DbSession) -> Response:
    workspace = await resolve_workspace(session, slug)
    row, content = await kb_public.image(session, workspace.id, image_id)
    headers = {"X-Content-Type-Options": "nosniff"}
    if row.content_type.lower() not in INLINE_SAFE_TYPES:
        headers["Content-Disposition"] = "attachment"
    return Response(
        content=content,
        media_type=safe_content_type(row.content_type),
        headers=headers,
    )


@router.get(
    "/{slug}/kb/{category_slug}/{article_slug}", response_model=PublicArticleOut
)
async def read_kb_article(
    slug: str, category_slug: str, article_slug: str, session: DbSession
) -> PublicArticleOut:
    workspace = await resolve_workspace(session, slug)
    article = await kb_public.article(
        session, workspace.id, category_slug, article_slug
    )
    return _article_out(article)


# `/{slug}/tickets` adds no new fixed first segment -- the first segment is
# the slug itself, resolved the same way every other route here resolves it
# -- so it needs no entry in `RESERVED_SLUGS`.
@router.post("/{slug}/tickets", response_model=TicketSubmittedOut, status_code=201)
async def submit_ticket(
    session: DbSession,
    request: Request,
    slug: str,
    email: Annotated[EmailStr, Form()],
    message: Annotated[str, Form()],
    name: Annotated[str, Form()] = "",
    subject: Annotated[str, Form()] = "",
    company: Annotated[str, Form()] = "",
    files: Annotated[list[UploadFile] | None, File()] = None,
) -> TicketSubmittedOut:
    workspace = await resolve_workspace(session, slug)

    uploads = files or []
    if len(uploads) > get_settings().ticket_attachment_max_count:
        raise Invalid("Too many attachments.")

    # A cheap check on the declared sizes before pulling any body into
    # memory. `upload.size` is a client-supplied multipart header, so this
    # only saves work on the honest case and is not the guard;
    # `tickets.validate` below re-checks the very same budget against the
    # bytes actually read, and that check is the authoritative one. Both
    # spend `attachment_max_bytes` the way `attachments.store` does -- as
    # one total shared across the submission, not a per-file allowance.
    declared = sum(upload.size for upload in uploads if upload.size is not None)
    if declared > get_settings().attachment_max_bytes:
        raise Invalid("Those files are too large.")

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

    # Input validation first, every abuse control after it. Ordering is the
    # whole point here: a control that fires ahead of validation answers
    # 201 or 429 where validation would have answered 422, and a bot that
    # posts one deliberately invalid payload twice -- once with a candidate
    # field filled, once without -- reads the honeypot's identity straight
    # off the two status codes. The same trick names the IP cap. With
    # validation first, both callers have been refused for the same reasons
    # in the same order before any control speaks.
    tickets.validate(message, parsed)

    # The IP cap. First control to run and the only one that charges, so a
    # caller pays for every call that got this far -- honeypot or not,
    # refused further down or not. `ratelimit.check` commits the charge
    # itself; see its docstring for why that is not left to this call site.
    within = await ratelimit.check(
        session,
        "tickets",
        client_ip.resolve(request),
        limit=get_settings().ticket_ip_hourly_cap,
        window=timedelta(hours=1),
    )
    if not within:
        raise TooManyRequests("We could not accept that just now.")

    # The per-email cap, raised with the exact exception and message the IP
    # cap uses above: a caller who can tell the two apart learns which one
    # fired and how to route around it.
    if await tickets.over_email_cap(session, workspace.id, str(email)):
        raise TooManyRequests("We could not accept that just now.")

    # The honeypot, last -- after everything above has run identically for
    # this caller and a real one. `company` is hidden from humans by the
    # form's stylesheet, so anything in it came from something filling
    # fields blindly. Answered with the same 201 a real submission gets:
    # telling a bot it was caught only teaches it which field to leave
    # alone. Because every control that can fire has already fired, the
    # only thing this decides is whether rows get written -- which is the
    # one difference the caller cannot observe.
    if company.strip():
        return TicketSubmittedOut(received=True)

    await tickets.submit(
        session,
        workspace.id,
        email=str(email),
        name=name,
        subject=subject,
        message=message,
        attachments=parsed,
    )
    await session.commit()
    return TicketSubmittedOut(received=True)
